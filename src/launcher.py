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
import copy
import os
import signal
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import Config, set_config
from utils.logger import setup_logger, get_logger

logger = None

# Re-export from bbs.runtime for backward compatibility
from bbs.runtime import get_bbs_instance, get_event_loop


def _build_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
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
  python launcher.py --mock                   # Dev: simulated radio fallback
        """,
    )

    # Connection mode
    parser.add_argument("--tcp", action="store_true",
                        help="Use TCP connection instead of serial")
    parser.add_argument("--tcp-host", default="192.168.1.100",
                        help="TCP host for companion radio (default: 192.168.1.100)")
    parser.add_argument("--tcp-port", type=int, default=5000,
                        help="TCP port for companion radio (default: 5000)")
    parser.add_argument("--mock", action="store_true",
                        help="Development only: use a simulated radio if the "
                             "real one is unreachable (never in production)")

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
                        version="MeshBBS v1.6.0")

    return parser


def _explicit_dests(parser: argparse.ArgumentParser, argv) -> set:
    """Names of the options actually given on the command line."""
    probe = copy.deepcopy(parser)
    for action in probe._actions:
        action.default = argparse.SUPPRESS
    namespace, _ = probe.parse_known_args(argv)
    return set(vars(namespace))


def parse_args(argv=None):
    """
    Parse command line arguments.

    The returned namespace also carries ``explicit``: the options given on
    the command line, which take precedence over environment variables
    and settings.json (see utils.config).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.explicit = _explicit_dests(parser, argv)
    return args


def build_config(args) -> Config:
    """
    Build the BBS configuration.

    Precedence: command line > BBS_* env vars > legacy env vars
    (DATABASE_PATH, LOG_FILE, ...) > settings.json > defaults.
    """
    explicit = getattr(args, "explicit", set())
    cli_fields = {
        "port": "serial_port",
        "baud": "baud_rate",
        "database": "database_path",
        "name": "bbs_name",
        "log_file": "log_path",
        "tcp_host": "tcp_host",
        "tcp_port": "tcp_port",
    }
    overrides = {
        field: getattr(args, dest)
        for dest, field in cli_fields.items()
        if dest in explicit
    }
    if args.tcp:
        overrides["connection_mode"] = "tcp"
    if args.debug:
        overrides["log_level"] = "DEBUG"
    return Config.from_env(overrides)


async def run_web_server(host: str, port: int, debug: bool):
    """Run the lightweight bottle web server in a background thread."""
    from web_light.server import start_server

    start_server(host=host, port=port, debug=debug)

    # Keep the coroutine alive while the server thread runs
    while True:
        await asyncio.sleep(60)


async def run_bbs(config: Config, use_mock: bool = False):
    """
    Run the BBS radio service.

    Args:
        config: BBS configuration
        use_mock: Allow falling back to a simulated radio (--mock).
            Without it the BBS keeps retrying the real radio.
    """
    from bbs.core import BBSCore
    from bbs.runtime import set_bbs_instance

    bbs = BBSCore(config, use_mock_fallback=use_mock)
    set_bbs_instance(bbs)

    try:
        await bbs.start()
        await bbs.run()
    finally:
        await bbs.stop()
        # A web-triggered restart may already have installed a new instance:
        # only clear the shared reference if it still points to this one.
        from bbs.runtime import get_bbs_instance as _current_bbs
        if _current_bbs() is bbs:
            set_bbs_instance(None)


async def run_all(args, config: Config):
    """Run BBS and web server concurrently."""
    global logger

    from bbs.runtime import set_event_loop
    set_event_loop(asyncio.get_running_loop())

    tasks = []

    if not args.web_only:
        logger.info("Starting BBS radio service...")
        if getattr(args, "mock", False):
            logger.warning("Mock radio fallback enabled (--mock): development only")
            bbs_coro = run_bbs(config, use_mock=True)
        else:
            bbs_coro = run_bbs(config)
        tasks.append(asyncio.create_task(
            bbs_coro,
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

    # Configuration: CLI > environment > settings.json > defaults
    config = build_config(args)

    # Configure logging
    setup_logger(name="meshbbs", log_file=config.log_path, level=config.log_level)
    logger = get_logger("meshbbs.launcher")

    logger.info("=" * 50)
    logger.info("MeshBBS v1.6.0 - Unified Launcher")
    logger.info("=" * 50)

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
