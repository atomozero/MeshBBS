#!/usr/bin/env python3
"""
MeshBBS Unified Launcher.

Starts both the BBS radio service and the web administration
interface in a single process using a shared asyncio event loop.

MIT License - Copyright (c) 2026 MeshBBS Contributors

Usage:
    python launcher.py                         # BBS + Web (default)
    python launcher.py --web-only              # Web server only
    python launcher.py --bbs-only              # BBS radio only
    python launcher.py --web-port 9090         # Custom web port
    python launcher.py -p /dev/ttyACM0 --debug # Custom serial port
"""

import asyncio
import argparse
import signal
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import Config, set_config
from utils.logger import setup_logger, get_logger

logger = None

# Global reference to BBSCore for API control
_bbs_instance = None


def get_bbs_instance():
    """Get the running BBSCore instance (used by web API for control)."""
    return _bbs_instance


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="MeshBBS - BBS + Web Admin unified launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launcher.py                          # Start everything
  python launcher.py --web-only               # Web server only
  python launcher.py --bbs-only               # BBS radio only
  python launcher.py -p /dev/ttyACM0 --debug  # Custom port + debug
  python launcher.py --web-port 9090          # Custom web port
        """,
    )

    # Connection mode
    parser.add_argument("--tcp", action="store_true",
                        help="Use TCP connection instead of serial")
    parser.add_argument("--tcp-host", default="192.168.1.100",
                        help="TCP host for companion radio (default: 192.168.1.100)")
    parser.add_argument("--tcp-port", type=int, default=5000,
                        help="TCP port for companion radio (default: 5000)")

    # Serial options (default mode)
    parser.add_argument("-p", "--port", default="/dev/ttyUSB0",
                        help="Serial port for companion radio (default: /dev/ttyUSB0)")
    parser.add_argument("-b", "--baud", type=int, default=115200,
                        help="Baud rate (default: 115200)")

    # BBS options
    parser.add_argument("-d", "--database", default="data/bbs.db",
                        help="Database path (default: data/bbs.db)")
    parser.add_argument("-n", "--name", default="MeshCore BBS",
                        help="BBS name (default: MeshCore BBS)")

    # Web options
    parser.add_argument("--web-host", default="0.0.0.0",
                        help="Web server bind address (default: 0.0.0.0)")
    parser.add_argument("--web-port", type=int, default=8080,
                        help="Web server port (default: 8080)")

    # Mode selection
    parser.add_argument("--web-only", action="store_true",
                        help="Start web server only (no BBS radio)")
    parser.add_argument("--bbs-only", action="store_true",
                        help="Start BBS radio only (no web server)")

    # Common options
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--log-file", default="logs/bbs.log",
                        help="Log file path (default: logs/bbs.log)")
    parser.add_argument("--version", action="version",
                        version="MeshBBS v1.5.0")

    return parser.parse_args()


async def run_web_server(host: str, port: int, debug: bool):
    """Run the lightweight bottle web server in a background thread."""
    from web_light.server import start_server

    start_server(host=host, port=port, debug=debug)

    # Keep the coroutine alive while the server thread runs
    while True:
        await asyncio.sleep(60)


async def run_bbs(config: Config):
    """Run the BBS radio service."""
    global _bbs_instance

    from bbs.core import BBSCore

    bbs = BBSCore(config)
    _bbs_instance = bbs

    try:
        await bbs.start()
        await bbs.run()
    finally:
        await bbs.stop()
        _bbs_instance = None


async def run_all(args, config: Config):
    """Run BBS and web server concurrently."""
    global logger

    tasks = []

    if not args.web_only:
        logger.info("Starting BBS radio service...")
        tasks.append(asyncio.create_task(
            run_bbs(config),
            name="bbs",
        ))

    if not args.bbs_only:
        logger.info(f"Starting web server on {args.web_host}:{args.web_port}...")
        tasks.append(asyncio.create_task(
            run_web_server(args.web_host, args.web_port, args.debug),
            name="web",
        ))

    if not tasks:
        logger.error("No services to start (both --web-only and --bbs-only specified)")
        return

    # Wait for any task to complete (or fail)
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    # If one service stops, stop the others
    for task in pending:
        logger.info(f"Stopping {task.get_name()}...")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Check for errors in completed tasks
    for task in done:
        if task.exception():
            logger.error(f"Service {task.get_name()} failed: {task.exception()}")


def main():
    """Main entry point."""
    global logger

    args = parse_args()

    # Configure logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logger(name="meshbbs", log_file=args.log_file, level=log_level)
    logger = get_logger("meshbbs.launcher")

    logger.info("=" * 50)
    logger.info("MeshBBS v1.5.0 - Unified Launcher")
    logger.info("=" * 50)

    # Create BBS configuration
    config = Config(
        connection_mode="tcp" if args.tcp else "serial",
        serial_port=args.port,
        baud_rate=args.baud,
        tcp_host=args.tcp_host,
        tcp_port=args.tcp_port,
        database_path=args.database,
        log_path=args.log_file,
        log_level=log_level,
        bbs_name=args.name,
    )
    config.ensure_directories()
    set_config(config)

    # Set web config
    from web.config import WebConfig, set_web_config
    web_config = WebConfig(
        host=args.web_host,
        port=args.web_port,
        debug=args.debug,
    )
    set_web_config(web_config)

    # Log configuration
    mode = "BBS only" if args.bbs_only else "Web only" if args.web_only else "BBS + Web"
    logger.info(f"Mode: {mode}")
    if not args.web_only:
        if args.tcp:
            logger.info(f"Radio: TCP {config.tcp_host}:{config.tcp_port}")
        else:
            logger.info(f"Radio: Serial {config.serial_port} @ {config.baud_rate}")
    if not args.bbs_only:
        logger.info(f"Web: http://{args.web_host}:{args.web_port}")
    logger.info(f"Database: {config.database_path}")

    # Initialize database before starting services
    from bbs.models.base import init_database
    init_database(config.database_path)

    # Initialize MQTT (optional)
    from utils.mqtt import get_mqtt_client
    mqtt = get_mqtt_client()
    if mqtt.config.enabled:
        logger.info(f"MQTT: {mqtt.config.host}:{mqtt.config.port}")

    # Run
    try:
        asyncio.run(run_all(args, config))
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)

    logger.info("MeshBBS stopped. Goodbye!")


if __name__ == "__main__":
    main()
