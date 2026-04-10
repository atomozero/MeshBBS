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
from meshbbs_radio.connection import BaseMeshCoreConnection, MeshCoreConnection, TCPMeshCoreConnection
from meshbbs_radio.messages import Message
from meshbbs_radio.state import get_state_manager
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
        self._beacon_task: Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None
        self._retention_task: Optional[asyncio.Task] = None
        self._last_message_time: Optional[datetime] = None

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

        with get_session() as session:
            log_activity(session, EventType.ADVERT_SENT, details="Avvio BBS")

        # Start periodic advert task
        self._advert_task = asyncio.create_task(self._periodic_advert())

        # Start periodic MQTT stats publishing (if MQTT enabled)
        self._stats_task = asyncio.create_task(self._periodic_stats_publish())

        # Start periodic WebSocket status broadcasting
        self._ws_status_task = asyncio.create_task(self._periodic_ws_status())

        # Start periodic beacon broadcast
        self._beacon_task = asyncio.create_task(self._periodic_beacon())

        # Start connection watchdog
        self._watchdog_task = asyncio.create_task(self._connection_watchdog())

        # Start retention cleanup scheduler
        self._retention_task = asyncio.create_task(self._periodic_retention_cleanup())

        self._running = True
        logger.info(f"{self.config.bbs_name} is now online!")

    async def stop(self) -> None:
        """
        Stop the BBS system gracefully.
        """
        logger.info("Stopping BBS...")
        self._running = False

        # Cancel background tasks
        for task in (self._advert_task, self._stats_task, self._ws_status_task,
                     self._beacon_task, self._watchdog_task, self._retention_task):
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
        msg_type = "channel" if message.is_channel else "private"
        logger.info(
            f"Received {msg_type} from {message.sender_short} "
            f"(hops={message.hops}): {message.text[:50]}..."
        )

        # Update activity timestamp
        self._last_message_time = datetime.utcnow()
        await self.state_manager.update_activity()

        # Notify WebSocket clients of new message
        await self._ws_notify_message(message)

        # For channel messages, only respond to !help from known contacts
        text = message.text
        if message.is_channel:
            # Channel messages often arrive as "NodeName: message"
            if ": " in text:
                text = text.split(": ", 1)[1]
            text = text.strip()

            # Only respond to !help on channel
            if not text.lower().startswith("!help"):
                return None

        # Create database session and dispatcher
        with get_session() as session:
            dispatcher = CommandDispatcher(
                session=session,
                response_prefix=self.config.response_prefix,
            )

            # Dispatch command
            response = await dispatcher.dispatch(
                message=text,
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
        Send a response, chunking to fit LoRa MTU (~180 bytes).

        Splits by newlines first, then by length if a single chunk
        exceeds the MTU. Adds delays between chunks.
        """
        MAX_CHUNK = 140  # safe limit under LoRa MTU
        delay = self.config.send_delay

        # Split into lines first
        lines = text.split("\n")

        # Build chunks that fit within MAX_CHUNK
        chunks = []
        current = ""

        for line in lines:
            # If a single line exceeds MAX_CHUNK, split it by words
            if len(line) > MAX_CHUNK:
                if current:
                    chunks.append(current)
                    current = ""
                words = line.split(" ")
                part = ""
                for word in words:
                    if part and len(part) + 1 + len(word) > MAX_CHUNK:
                        chunks.append(part)
                        part = word
                    else:
                        part = f"{part} {word}" if part else word
                if part:
                    chunks.append(part)
                continue

            # Try adding to current chunk
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) > MAX_CHUNK:
                # Current chunk is full, start new one
                chunks.append(current)
                current = line
            else:
                current = candidate

        if current:
            chunks.append(current)

        # Send chunks with delay
        for i, chunk in enumerate(chunks):
            await self.connection.send_message(
                destination=destination,
                text=chunk,
            )
            if i < len(chunks) - 1:
                logger.debug(f"Chunk {i+1}/{len(chunks)} sent, waiting {delay}s")
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

    async def _connection_watchdog(self) -> None:
        """
        Monitor connection health and auto-reconnect on failure.

        Checks every 30 seconds if the connection is alive.
        If disconnected, attempts to reconnect with exponential backoff.
        Also detects silent failures (no messages for a long time).
        """
        check_interval = 30
        max_backoff = 120
        stale_timeout = 600  # 10 minutes without any message = suspicious

        while self._running:
            try:
                await asyncio.sleep(check_interval)

                if not self._running:
                    break

                mc = self.connection._meshcore

                # Check 1: meshcore object exists and is connected
                is_alive = (
                    mc is not None
                    and self.connection.connected
                    and hasattr(mc, 'is_connected')
                    and mc.is_connected
                )

                if not is_alive:
                    logger.warning("Connection lost — attempting reconnect...")
                    await self.state_manager.set_reconnecting(
                        self.state_manager.state.reconnect_attempts + 1
                    )
                    await self._do_reconnect(max_backoff)
                    continue

                # Check 2: Stale connection detection (heartbeat)
                if self._last_message_time:
                    idle_seconds = (datetime.utcnow() - self._last_message_time).total_seconds()
                    if idle_seconds > stale_timeout:
                        logger.warning(
                            f"No messages for {int(idle_seconds)}s — "
                            f"connection may be stale, sending test..."
                        )
                        # Try to get contacts as a keepalive
                        try:
                            await mc.commands.get_contacts()
                            logger.debug("Keepalive OK — connection still alive")
                        except Exception:
                            logger.warning("Keepalive failed — reconnecting...")
                            await self._do_reconnect(max_backoff)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watchdog error: {e}")

    async def _do_reconnect(self, max_backoff: int) -> None:
        """Disconnect and reconnect with exponential backoff."""
        delay = 5

        # Disconnect cleanly
        try:
            await self.connection.disconnect()
        except Exception:
            pass

        self.connection.connected = False
        await self.state_manager.set_disconnected("Reconnecting...")

        while self._running:
            try:
                logger.info(f"Reconnecting in {delay}s...")
                await asyncio.sleep(delay)

                success = await self.connection.connect()
                if success:
                    logger.info("Reconnected successfully!")
                    self._last_message_time = datetime.utcnow()

                    # Update state
                    is_mock = getattr(self.connection, 'is_using_mock', False)
                    await self.state_manager.set_connected(
                        public_key=self.connection.identity.public_key,
                        name=self.connection.identity.name,
                        port=self.config.tcp_host if self.config.connection_mode == "tcp" else self.config.serial_port,
                        baud_rate=self.config.baud_rate,
                        is_mock=is_mock,
                    )

                    # Re-send advert after reconnect
                    await self.connection.send_advert(flood=True)
                    logger.info("Post-reconnect advert sent")
                    return

            except Exception as e:
                logger.error(f"Reconnect attempt failed: {e}")

            delay = min(delay * 2, max_backoff)

    async def _periodic_retention_cleanup(self) -> None:
        """
        Periodically clean up old private messages and activity logs.

        Runs once per day (24h interval).
        """
        interval = 86400  # 24 hours

        # Wait 5 minutes after startup before first run
        await asyncio.sleep(300)

        while self._running:
            try:
                logger.info("Running retention cleanup...")

                from bbs.privacy import RetentionManager

                with get_session() as session:
                    manager = RetentionManager(session)
                    pms_deleted, logs_deleted = manager.run_cleanup(
                        pm_retention_days=self.config.pm_retention_days,
                        log_retention_days=self.config.activity_log_retention_days,
                    )

                if pms_deleted > 0 or logs_deleted > 0:
                    logger.info(
                        f"Retention cleanup: {pms_deleted} PM, {logs_deleted} log eliminati"
                    )
                else:
                    logger.debug("Retention cleanup: nulla da eliminare")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retention cleanup error: {e}")

            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break

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

    async def _periodic_beacon(self) -> None:
        """
        Periodically broadcast a beacon message on the mesh.

        Announces the BBS presence so users know it exists.
        Interval and message configurable. Set interval to 0 to disable.
        """
        interval = self.config.beacon_interval * 60  # config is in minutes
        if interval <= 0:
            logger.debug("Beacon disabled (interval=0)")
            return

        beacon_text = self.config.beacon_message.format(
            name=self.config.bbs_name,
        )

        while self._running:
            try:
                await asyncio.sleep(interval)

                if self._running and self.connection.connected:
                    logger.info(f"Sending beacon: {beacon_text[:50]}...")
                    try:
                        mc = self.connection._meshcore
                        if mc:
                            await mc.commands.send_chan_msg(0, beacon_text)
                            logger.info("Beacon sent on channel")
                    except Exception as e:
                        logger.warning(f"Beacon send failed: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error sending beacon: {e}")

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
