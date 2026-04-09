"""
Core BBS logic and message handling.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
from datetime import datetime
from typing import Optional

from bbs.models.base import get_session, init_database
from bbs.models.activity_log import ActivityLog, EventType, log_activity
from bbs.commands.dispatcher import CommandDispatcher
from meshcore.connection import BaseMeshCoreConnection, MeshCoreConnection, TCPMeshCoreConnection
from meshcore.messages import Message
from meshcore.state import get_state_manager
from utils.config import Config, get_config

try:
    from utils.logger import get_logger, setup_logger
    logger = get_logger("meshbbs.core")
except ImportError:
    import logging
    logger = logging.getLogger("meshbbs.core")
    setup_logger = None


class BBSCore:
    """
    Main BBS application core.

    Coordinates between MeshCore connection, command processing,
    and database operations.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        connection: Optional[BaseMeshCoreConnection] = None,
    ):
        """
        Initialize the BBS core.

        Args:
            config: Configuration object (uses global config if None)
            connection: MeshCore connection (creates default if None)
        """
        self.config = config or get_config()
        if connection:
            self.connection = connection
        elif self.config.connection_mode == "tcp":
            self.connection = TCPMeshCoreConnection(
                host=self.config.tcp_host,
                port=self.config.tcp_port,
            )
        else:
            self.connection = MeshCoreConnection(
                port=self.config.serial_port,
                baud_rate=self.config.baud_rate,
            )
        self.state_manager = get_state_manager()

        self._running = False
        self._advert_task: Optional[asyncio.Task] = None
        self._stats_task: Optional[asyncio.Task] = None
        self._ws_status_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """
        Start the BBS system.

        Initializes database, connects to companion radio, and starts
        the main processing loop.
        """
        logger.info(f"Starting {self.config.bbs_name}...")

        # Initialize database
        logger.info("Initializing database...")
        init_database(self.config.database_path)

        # Log startup
        with get_session() as session:
            log_activity(session, EventType.BBS_STARTED, details=self.config.bbs_name)

        # Connect to companion radio
        if self.config.connection_mode == "tcp":
            conn_info = f"TCP {self.config.tcp_host}:{self.config.tcp_port}"
        else:
            conn_info = f"Serial {self.config.serial_port}"
        logger.info(f"Connecting to companion radio via {conn_info}...")
        await self.state_manager.set_connecting(
            conn_info,
            self.config.baud_rate
        )
        connected = await self.connection.connect()

        if not connected:
            logger.error("Failed to connect to companion radio")
            await self.state_manager.set_error("Could not connect to companion radio")
            raise ConnectionError("Could not connect to companion radio")

        # Update connection state
        is_mock = getattr(self.connection, 'is_using_mock', False)
        await self.state_manager.set_connected(
            public_key=self.connection.identity.public_key,
            name=self.connection.identity.name,
            port=self.config.serial_port,
            baud_rate=self.config.baud_rate,
            is_mock=is_mock,
        )

        logger.info(
            f"Connected! Identity: {self.connection.identity.name} "
            f"({self.connection.identity.short_key}...)"
        )

        # Send initial advert
        logger.info("Sending initial advertisement...")
        await self.connection.send_advert(flood=True)

        # Start periodic advert task
        self._advert_task = asyncio.create_task(self._periodic_advert())

        # Start periodic MQTT stats publishing (if MQTT enabled)
        self._stats_task = asyncio.create_task(self._periodic_stats_publish())

        # Start periodic WebSocket status broadcasting
        self._ws_status_task = asyncio.create_task(self._periodic_ws_status())

        self._running = True
        logger.info(f"{self.config.bbs_name} is now online!")

    async def stop(self) -> None:
        """
        Stop the BBS system gracefully.
        """
        logger.info("Stopping BBS...")
        self._running = False

        # Cancel background tasks
        for task in (self._advert_task, self._stats_task, self._ws_status_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Log shutdown
        with get_session() as session:
            log_activity(session, EventType.BBS_STOPPED)

        # Disconnect
        await self.connection.disconnect()
        await self.state_manager.set_disconnected()
        logger.info("BBS stopped")

    async def run(self) -> None:
        """
        Main processing loop.

        Receives messages and dispatches them to command handlers.
        """
        logger.info("Entering main loop...")

        while self._running:
            try:
                # Receive message
                message = await self.connection.receive()

                if message:
                    # Process the message
                    response = await self.handle_message(message)

                    if response:
                        # Send response back to sender, chunking multi-line
                        # responses to avoid message loss over slow radio links
                        await self._send_response(
                            destination=message.sender_key,
                            text=response,
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in main loop: {e}")
                await asyncio.sleep(1)  # Prevent tight error loop

    async def handle_message(self, message: Message) -> Optional[str]:
        """
        Handle an incoming message.

        Args:
            message: Received MeshCore message

        Returns:
            Response string or None
        """
        logger.info(
            f"Received from {message.sender_short} "
            f"(hops={message.hops}): {message.text[:50]}..."
        )

        # Update activity timestamp
        await self.state_manager.update_activity()

        # Notify WebSocket clients of new message
        await self._ws_notify_message(message)

        # Create database session and dispatcher
        with get_session() as session:
            dispatcher = CommandDispatcher(
                session=session,
                response_prefix=self.config.response_prefix,
            )

            # Dispatch command
            response = await dispatcher.dispatch(
                message=message.text,
                sender_key=message.sender_key,
                hops=message.hops,
                rssi=message.rssi,
            )

            if response:
                logger.info(f"Response: {response[:50]}...")
            else:
                logger.debug("No response (not a command)")

            return response

    async def _send_response(self, destination: str, text: str) -> None:
        """
        Send a response, chunking multi-line messages with delays.

        Long multi-line responses (e.g. from /list) are split and sent
        one chunk at a time with a configurable delay between sends,
        to avoid message loss over slow LoRa radio links.
        """
        lines = text.split("\n")

        # Single-line responses: send directly
        if len(lines) <= 2:
            await self.connection.send_message(
                destination=destination,
                text=text,
            )
            return

        # Multi-line responses: send in chunks with delay
        # First line is usually the header (e.g. "[BBS]"), group it with the first content line
        delay = self.config.send_delay
        chunk_lines = []

        for i, line in enumerate(lines):
            chunk_lines.append(line)

            # Send chunks of 2 lines at a time (header+content or content pairs)
            if len(chunk_lines) >= 2 or i == len(lines) - 1:
                chunk = "\n".join(chunk_lines)
                success = await self.connection.send_message(
                    destination=destination,
                    text=chunk,
                )
                chunk_lines = []

                # Wait between chunks (but not after the last one)
                if success and i < len(lines) - 1:
                    logger.debug(f"Chunk sent, waiting {delay}s before next")
                    await asyncio.sleep(delay)

    async def _ws_notify_message(self, message: Message) -> None:
        """Notify WebSocket clients about a new incoming message."""
        try:
            from web.websocket.manager import get_connection_manager, EventType as WSEventType

            manager = get_connection_manager()
            if manager.connection_count == 0:
                return

            await manager.broadcast_message_event(
                WSEventType.NEW_MESSAGE,
                {
                    "sender_key": message.sender_key,
                    "sender_short": message.sender_short,
                    "text": message.text[:100],
                    "hops": message.hops,
                    "rssi": message.rssi,
                },
            )
        except Exception:
            pass  # WebSocket not available

    async def _periodic_ws_status(self) -> None:
        """
        Periodically broadcast radio status and stats to WebSocket clients.

        Runs every 30 seconds. Does nothing if no clients are connected
        or if the FastAPI WebSocket module is not available (light mode).
        """
        interval = 30

        # Check if WebSocket manager is available (not in light mode)
        try:
            from web.websocket.manager import get_connection_manager
        except ImportError:
            logger.debug("WebSocket manager not available (light mode), skipping periodic status")
            return

        while self._running:
            try:
                await asyncio.sleep(interval)

                manager = get_connection_manager()
                if manager.connection_count == 0:
                    continue

                # Broadcast radio status
                state_dict = self.state_manager.to_dict()
                await manager.broadcast_system_status(state_dict)

                # Broadcast stats update
                with get_session() as session:
                    from bbs.services.stats_collector import StatsCollector
                    collector = StatsCollector(session)
                    stats = collector.collect()

                await manager.broadcast_stats_update(stats)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error broadcasting WebSocket status: {e}")

    async def _periodic_advert(self) -> None:
        """
        Periodically send advertisements.
        """
        interval = self.config.advert_interval_minutes * 60

        while self._running:
            try:
                await asyncio.sleep(interval)

                if self._running:
                    logger.info("Sending periodic advertisement...")
                    await self.connection.send_advert(flood=True)

                    with get_session() as session:
                        log_activity(session, EventType.ADVERT_SENT)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error sending advert: {e}")

    async def _periodic_stats_publish(self) -> None:
        """
        Periodically collect and publish stats via MQTT.

        Runs every 5 minutes. Silently does nothing if MQTT is disabled.
        """
        from utils.mqtt import get_mqtt_client
        from bbs.services.stats_collector import StatsCollector

        interval = self.config.stats_publish_interval

        while self._running:
            try:
                await asyncio.sleep(interval)

                mqtt_client = get_mqtt_client()
                if not mqtt_client.is_connected:
                    continue

                with get_session() as session:
                    collector = StatsCollector(session)
                    stats = collector.collect()

                await mqtt_client.publish_stats(stats)
                logger.debug("MQTT stats published")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error publishing MQTT stats: {e}")


async def run_bbs(config: Optional[Config] = None) -> None:
    """
    Convenience function to run the BBS.

    Args:
        config: Optional configuration
    """
    bbs = BBSCore(config)

    try:
        await bbs.start()
        await bbs.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await bbs.stop()
