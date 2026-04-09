#!/usr/bin/env python3
"""
MeshCore BBS - Main entry point.

MIT License - Copyright (c) 2026 MeshBBS Contributors

A Bulletin Board System for MeshCore LoRa mesh networks.
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.config import Config, set_config
from utils.logger import setup_logger
from bbs.core import run_bbs


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="MeshCore BBS - Bulletin Board System for LoRa mesh networks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Run with default settings
  python main.py -p /dev/ttyACM0    # Use specific serial port
  python main.py -n "My BBS"        # Set custom BBS name
  python main.py --debug            # Enable debug logging
        """,
    )

    parser.add_argument(
        "-p", "--port",
        default="/dev/ttyUSB0",
        help="Serial port for companion radio (default: /dev/ttyUSB0)",
    )

    parser.add_argument(
        "-b", "--baud",
        type=int,
        default=115200,
        help="Baud rate (default: 115200)",
    )

    parser.add_argument(
        "-d", "--database",
        default="data/bbs.db",
        help="Database path (default: data/bbs.db)",
    )

    parser.add_argument(
        "-n", "--name",
        default="MeshCore BBS",
        help="BBS name (default: MeshCore BBS)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "--log-file",
        default="logs/bbs.log",
        help="Log file path (default: logs/bbs.log)",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="MeshCore BBS v0.1.0",
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Configure logging
    log_level = "DEBUG" if args.debug else "INFO"
    logger = setup_logger(
        name="meshbbs",
        log_file=args.log_file,
        level=log_level,
    )

    logger.info("=" * 50)
    logger.info("MeshCore BBS v0.1.0")
    logger.info("=" * 50)

    # Create configuration
    config = Config(
        serial_port=args.port,
        baud_rate=args.baud,
        database_path=args.database,
        log_path=args.log_file,
        log_level=log_level,
        bbs_name=args.name,
    )

    config.ensure_directories()
    set_config(config)

    logger.info(f"Configuration:")
    logger.info(f"  Serial port: {config.serial_port}")
    logger.info(f"  Database: {config.database_path}")
    logger.info(f"  BBS name: {config.bbs_name}")

    # Run the BBS
    try:
        asyncio.run(run_bbs(config))
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)

    logger.info("Goodbye!")


if __name__ == "__main__":
    main()
