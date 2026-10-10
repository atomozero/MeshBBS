"""
Core BBS logic and message handling.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional

from bbs.models.base import get_session, init_database
from bbs.models.activity_log import ActivityLog, EventType, log_activity
from bbs.commands.dispatcher import CommandDispatcher
from bbs.rate_limiter import RateLimiter
from bbs.services.user_keys import canonical_user_key, normalize_user_keys
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


# Max payload per radio message, in UTF-8 bytes (safe limit under the
# LoRa MTU, ~180 bytes including MeshCore headers)
MAX_CHUNK_BYTES = 140


def _utf8_len(text: str) -> int:
    return len(text.encode("utf-8"))


def _hard_split(word: str, max_bytes: int) -> List[str]:
    """Split a word longer than max_bytes on character boundaries."""
    pieces: List[str] = []
    current = ""
    current_bytes = 0
    for ch in word:
        ch_bytes = _utf8_len(ch)
        if current and current_bytes + ch_bytes > max_bytes:
            pieces.append(current)
            current, current_bytes = ch, ch_bytes
        else:
            current += ch
            current_bytes += ch_bytes
    if current:
        pieces.append(current)
    return pieces


def _split_long_line(line: str, max_bytes: int) -> List[str]:
    """Split a single line by words so each part fits max_bytes."""
    parts: List[str] = []
    part = ""
    for word in line.split(" "):
        if _utf8_len(word) > max_bytes:
            if part:
                parts.append(part)
            pieces = _hard_split(word, max_bytes)
            parts.extend(pieces[:-1])
            part = pieces[-1] if pieces else ""
            continue
        candidate = f"{part} {word}" if part else word
        if part and _utf8_len(candidate) > max_bytes:
            parts.append(part)
            part = word
        else:
            part = candidate
    if part:
        parts.append(part)
    return parts


def split_utf8_chunks(text: str, max_bytes: int = MAX_CHUNK_BYTES) -> List[str]:
    """
    Split a response into radio-sized chunks.

    Lines are packed together while they fit; longer lines are split by
    words, and words longer than the limit are hard-split. Sizes are
    measured in UTF-8 bytes (accented letters and emoji take 2-4 bytes)
    and a multi-byte character is never cut.
    """
    chunks: List[str] = []
    current = ""

    for line in text.split("\n"):
        if _utf8_len(line) > max_bytes:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_line(line, max_bytes))
            continue

        candidate = f"{current}\n{line}" if current else line
        if _utf8_len(candidate) > max_bytes:
            chunks.append(current)
            current = line
        else:
            current = candidate

    if current:
        chunks.append(current)

    return chunks


class BBSCore:
    """
    Main BBS application core.

    Coordinates between MeshCore connection, command processing,
    and database operations.
    """

    # Watchdog: how often the link state is checked
    WATCHDOG_CHECK_INTERVAL = 30
    # Active liveness probe of the companion (independent of traffic)
    PROBE_INTERVAL = 150
    # Delay before re-probing once after a failed probe
    PROBE_RETRY_DELAY = 5
    # Reconnect backoff (seconds): 5, 10, 20, ... up to 5 minutes
    RECONNECT_INITIAL_DELAY = 5
    RECONNECT_MAX_DELAY = 300
    # Pending replies kept per destination (oldest dropped beyond this)
    SEND_QUEUE_MAXSIZE = 10

    def __init__(
        self,
        config: Optional[Config] = None,
        connection: Optional[BaseMeshCoreConnection] = None,
        use_mock_fallback: bool = False,
    ):
        """
        Initialize the BBS core.

        Args:
            config: Configuration object (uses global config if None)
            connection: MeshCore connection (creates default if None)
            use_mock_fallback: Allow falling back to a simulated radio when
                the real one is unreachable (development only: in
                production the BBS keeps retrying the real radio)
        """
        self.config = config or get_config()
        if connection:
            self.connection = connection
        elif self.config.connection_mode == "tcp":
            self.connection = TCPMeshCoreConnection(
                host=self.config.tcp_host,
                port=self.config.tcp_port,
                use_mock_fallback=use_mock_fallback,
            )
        else:
            self.connection = MeshCoreConnection(
                port=self.config.serial_port,
                baud_rate=self.config.baud_rate,
                use_mock_fallback=use_mock_fallback,
            )
        self.state_manager = get_state_manager()

        # One long-lived rate limiter shared by every dispatch
        self.rate_limiter = RateLimiter()

        self._running = False
        self._advert_task: Optional[asyncio.Task] = None
        self.ops = None  # bbs.services.ops.OpsServices (MQTT, backup, WAL)
        self._ws_status_task: Optional[asyncio.Task] = None
        self._beacon_task: Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None
        self._retention_task: Optional[asyncio.Task] = None
        self._last_message_time: Optional[datetime] = None
        self._link_lost_event: Optional[asyncio.Event] = None
        self._send_queues: Dict[str, asyncio.Queue] = {}
        self._send_workers: Dict[str, asyncio.Task] = {}
        self.repeater_monitor = None

    def _connection_label(self) -> str:
        """Radio endpoint shown in the dashboard (host:port or serial port)."""
        if self.config.connection_mode == "tcp":
            return f"{self.config.tcp_host}:{self.config.tcp_port}"
        return self.config.serial_port

    async def start(self) -> None:
        """
        Start the BBS system.

        Initializes database, connects to companion radio, and starts
        the main processing loop. If the radio is unreachable the BBS
        still starts: the watchdog keeps retrying with backoff.
        """
        logger.info(f"Starting {self.config.bbs_name}...")

        # Initialize database
        logger.info("Initializing database...")
        init_database(self.config.database_path)

        # Log startup
        with get_session() as session:
            log_activity(session, EventType.BBS_STARTED, details=self.config.bbs_name)

        # Migrate users stored with full 64-char keys to the canonical form
        try:
            with get_session() as session:
                normalize_user_keys(session)
        except Exception as e:
            logger.error(f"User key normalisation failed: {e}")

        self._running = True
        self._link_lost_event = asyncio.Event()
        if hasattr(self.connection, "set_link_lost_callback"):
            self.connection.set_link_lost_callback(self._on_link_lost)

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
        try:
            connected = await self.connection.connect()
        except Exception as e:
            logger.error(f"Connection error: {e}")
            connected = False

        if connected:
            await self._on_connected(advert_details="Avvio BBS")
        else:
            logger.error(
                "Failed to connect to companion radio — "
                "will keep retrying in background"
            )
            await self.state_manager.set_error("Could not connect to companion radio")
            # Wake the watchdog immediately to start the reconnect loop
            self._link_lost_event.set()

        # Start periodic advert task
        self._advert_task = asyncio.create_task(self._periodic_advert())

        # MQTT bridge, nightly backup, WAL checkpoint
        from bbs.services.ops import start_ops_services
        self.ops = await start_ops_services(self)

        # Start periodic WebSocket status broadcasting
        self._ws_status_task = asyncio.create_task(self._periodic_ws_status())

        # Start periodic beacon broadcast
        self._beacon_task = asyncio.create_task(self._periodic_beacon())

        # Start connection watchdog
        self._watchdog_task = asyncio.create_task(self._connection_watchdog())

        # Start retention cleanup scheduler
        self._retention_task = asyncio.create_task(self._periodic_retention_cleanup())

        # Start repeater telemetry monitor (if configured)
        if getattr(self.config, "repeater_monitor_enabled", False):
            from meshbbs_radio.repeater_monitor import RepeaterMonitor, load_targets_from_config
            targets = load_targets_from_config(self.config)
            if targets:
                self.repeater_monitor = RepeaterMonitor(
                    bbs=self,
                    targets=targets,
                    interval_seconds=self.config.repeater_monitor_interval_minutes * 60,
                    jsonl_path=self.config.repeater_monitor_jsonl_path,
                )
                self.repeater_monitor.start()

        logger.info(f"{self.config.bbs_name} is now online!")

    async def _on_connected(self, advert_details: Optional[str] = None) -> None:
        """Update state and announce ourselves after a (re)connection."""
        self._last_message_time = datetime.utcnow()

        is_mock = getattr(self.connection, 'is_using_mock', False)
        await self.state_manager.set_connected(
            public_key=self.connection.identity.public_key,
            name=self.connection.identity.name,
            port=self._connection_label(),
            baud_rate=self.config.baud_rate,
            is_mock=is_mock,
        )

        logger.info(
            f"Connected! Identity: {self.connection.identity.name} "
            f"({self.connection.identity.short_key}...)"
        )
        await self._sync_node_status(query=True)

        logger.info("Sending advertisement...")
        advert_ok = await self.connection.send_advert(flood=True)
        if advert_ok and advert_details:
            with get_session() as session:
                log_activity(session, EventType.ADVERT_SENT, details=advert_details)
        elif not advert_ok:
            logger.warning("Advertisement after connect failed")

    def _on_link_lost(self, reason: str) -> None:
        """Called by the connection when the transport reports a disconnect."""
        logger.warning(f"Radio link lost ({reason}) — waking watchdog")
        if self._link_lost_event is not None:
            self._link_lost_event.set()

    async def stop(self) -> None:
        """
        Stop the BBS system gracefully.
        """
        logger.info("Stopping BBS...")
        self._running = False

        if self.repeater_monitor is not None:
            await self.repeater_monitor.stop()

        if self.ops is not None:
            await self.ops.stop()

        # Cancel background tasks (including pending reply senders)
        tasks = [self._advert_task, self._ws_status_task,
                 self._beacon_task, self._watchdog_task, self._retention_task]
        tasks.extend(self._send_workers.values())
        for task in tasks:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.debug(f"Task ended with error during stop: {e}")
        self._send_workers.clear()
        self._send_queues.clear()

        # Log shutdown
        with get_session() as session:
            log_activity(session, EventType.BBS_STOPPED)

        # Disconnect
        if hasattr(self.connection, "set_link_lost_callback"):
            self.connection.set_link_lost_callback(None)
        await self.connection.disconnect()
        await self.state_manager.set_disconnected()
        logger.info("BBS stopped")

    async def run(self) -> None:
        """
        Main processing loop.

        Receives messages and dispatches them to command handlers.
        Replies are sent by per-destination background workers, so a long
        multi-chunk reply never blocks other users.
        """
        logger.info("Entering main loop...")

        while self._running:
            try:
                # Receive message
                message = await self.connection.receive()

                if message:
                    # Process the message
                    response = await self.handle_message(message)

                    if response and message.sender_key:
                        # handle_message() leaves the canonical key of the
                        # sender (also resolved for channel messages) in
                        # message.sender_key: the connection resolves it
                        # to the contact when sending.
                        self._queue_response(message.sender_key, response)

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
        # Message bodies are user content: only metadata at INFO level
        logger.info(
            f"Received {msg_type} from {message.sender_short} "
            f"(hops={message.hops}, len={len(message.text)})"
        )
        logger.debug(f"Message text from {message.sender_short}: {message.text[:200]}")

        # Update activity timestamp
        self._last_message_time = datetime.utcnow()
        await self.state_manager.update_activity()
        if self.ops is not None:
            self.ops.on_message(message)

        # Notify WebSocket clients of new message
        await self._ws_notify_message(message)

        # For channel messages, only respond to !bbs
        text = message.text
        if message.is_channel:
            # Channel messages arrive as "NodeName: message"; the radio
            # layer already splits the name into message.sender_name
            sender_name = message.sender_name or ""
            if message.sender_name is None and ": " in text:
                sender_name, text = text.split(": ", 1)
            text = text.strip()

            # Only respond to exact "!bbs" on channel — anything longer
            # (e.g. "!bbs ciao a tutti") is treated as normal chatter and
            # ignored, to avoid accidental triggers that cost mesh airtime.
            if text.lower().strip() != "!bbs":
                return None

            # Override text to !help so dispatcher sends command list
            text = "!help"

            resolved_key = await self._resolve_channel_sender(message, sender_name)
            if not resolved_key:
                return None
            message.sender_key = resolved_key

        # One canonical user key everywhere (12-hex prefix, as in DMs)
        sender_key = canonical_user_key(message.sender_key)
        if not sender_key:
            logger.warning("Message without sender key ignored")
            return None
        message.sender_key = sender_key

        # Create database session and dispatcher
        with get_session() as session:
            dispatcher = CommandDispatcher(
                session=session,
                response_prefix=self.config.response_prefix,
                rate_limiter=self.rate_limiter,
            )

            # Dispatch command
            response = await dispatcher.dispatch(
                message=text,
                sender_key=sender_key,
                hops=message.hops,
                rssi=message.rssi,
            )

            if response:
                logger.debug(f"Response to {sender_key[:8]}: {len(response)} chars")
                logger.debug(f"Response: {response[:50]}...")
            else:
                logger.debug("No response (not a command)")

            return response

    async def _resolve_channel_sender(self, message: Message, sender_name: str) -> Optional[str]:
        """
        Resolve the sender of a channel message to a canonical user key.

        Channel messages carry only the sender name: look it up in the
        companion contacts (by key prefix first, if any, then by name).
        """
        mc = getattr(self.connection, "_meshcore", None)
        if not mc:
            logger.warning("Channel !bbs but no meshcore connection")
            return None

        # Refresh contacts first (a new node may have just advertised)
        try:
            if hasattr(self.connection, "refresh_contacts"):
                await self.connection.refresh_contacts(force=True)
            else:
                await mc.commands.get_contacts()
        except Exception:
            pass

        contact = None
        how = ""
        if message.sender_key:
            contact = mc.get_contact_by_key_prefix(message.sender_key)
            how = "key"
        if not contact and sender_name:
            contact = mc.get_contact_by_name(sender_name)
            how = "name"

        if not contact:
            # Log available contact names for debug
            names = [v.get("adv_name", "") or v.get("name", "?") for v in mc.contacts.values()]
            logger.warning(f"Channel !bbs from '{sender_name}' -> not found. Contacts: {names[:10]}")
            return None

        pk = contact.get("public_key", "") or message.sender_key or ""
        if isinstance(pk, bytes):
            pk = pk.hex()
        key = canonical_user_key(pk)
        logger.info(f"Channel !bbs from {sender_name} -> resolved by {how} {key}")
        return key

    def _queue_response(self, destination: str, text: str) -> None:
        """
        Queue a reply for background sending to one destination.

        Each destination has its own FIFO and worker task: replies to the
        same user stay ordered, while different users are served
        concurrently (the radio layer serialises the actual commands).
        """
        queue = self._send_queues.get(destination)
        if queue is None:
            queue = asyncio.Queue(maxsize=self.SEND_QUEUE_MAXSIZE)
            self._send_queues[destination] = queue

        if queue.full():
            try:
                queue.get_nowait()
                logger.warning(
                    f"Send queue for {destination[:8]} full: dropped oldest reply"
                )
            except asyncio.QueueEmpty:
                pass
        queue.put_nowait(text)

        worker = self._send_workers.get(destination)
        if worker is None or worker.done():
            self._send_workers[destination] = asyncio.create_task(
                self._send_worker(destination, queue)
            )

    async def _send_worker(self, destination: str, queue: asyncio.Queue) -> None:
        """Send queued replies for one destination, then exit."""
        try:
            while True:
                try:
                    text = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                try:
                    await self._send_response(destination=destination, text=text)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"Error sending reply to {destination[:8]}: {e}")
        finally:
            # No await between the empty check and this cleanup, so no
            # reply can be queued in between and get stranded.
            if self._send_workers.get(destination) is asyncio.current_task():
                del self._send_workers[destination]
                if self._send_queues.get(destination) is queue and queue.empty():
                    del self._send_queues[destination]

    async def _send_response(self, destination: str, text: str) -> bool:
        """
        Send a response, chunking to fit LoRa MTU (~180 bytes).

        Splits by newlines first, then by length (UTF-8 bytes) if a single
        chunk exceeds the limit. Adds delays between chunks and stops at
        the first chunk that cannot be delivered.

        Returns:
            True if every chunk was sent
        """
        delay = self.config.send_delay
        chunks = split_utf8_chunks(text, MAX_CHUNK_BYTES)

        # Send chunks with delay
        for i, chunk in enumerate(chunks):
            sent = await self.connection.send_message(
                destination=destination,
                text=chunk,
            )
            if not sent:
                remaining = len(chunks) - i - 1
                logger.warning(
                    f"Chunk {i+1}/{len(chunks)} to {destination[:8]} failed"
                    + (f", {remaining} remaining chunk(s) dropped" if remaining else "")
                )
                return False
            if i < len(chunks) - 1:
                logger.debug(f"Chunk {i+1}/{len(chunks)} sent, waiting {delay}s")
                await asyncio.sleep(delay)
        return True

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

    def _is_link_up(self) -> bool:
        """Whether the radio link looks up (without talking to the radio)."""
        if not self.connection.connected:
            return False
        if getattr(self.connection, "is_using_mock", False):
            return True
        if not hasattr(self.connection, "probe") or not hasattr(self.connection, "_build_meshcore"):
            # Simulated / custom connection: trust its connected flag
            return True
        mc = getattr(self.connection, "_meshcore", None)
        return mc is not None and bool(getattr(mc, "is_connected", False))

    async def _probe_link(self) -> bool:
        """
        Actively check that the companion answers (one retry).

        meshcore returns an ERROR event (no exception) when a command
        times out, so a dead TCP link is only detected this way.
        """
        probe = getattr(self.connection, "probe", None)
        if probe is None:
            return self.connection.connected
        if await probe():
            return True
        logger.info(f"Keepalive probe failed, retrying in {self.PROBE_RETRY_DELAY}s")
        await asyncio.sleep(self.PROBE_RETRY_DELAY)
        return await probe()

    async def _wait_watchdog_tick(self, timeout: float) -> None:
        """Sleep until the next check, or until a link loss is reported."""
        event = self._link_lost_event
        if event is None:
            await asyncio.sleep(timeout)
            return
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        event.clear()

    def _housekeeping(self) -> None:
        """Periodic memory housekeeping (called after a good probe)."""
        try:
            dropped = self.connection.flush_pending_contacts() if hasattr(
                self.connection, "flush_pending_contacts") else 0
            if dropped:
                logger.debug(f"Flushed {dropped} pending contact(s)")
        except Exception as e:
            logger.debug(f"flush_pending_contacts failed: {e}")
        try:
            self.rate_limiter.cleanup_old_entries(max_age_hours=1)
        except Exception as e:
            logger.debug(f"Rate limiter cleanup failed: {e}")

    async def _connection_watchdog(self) -> None:
        """
        Monitor connection health and auto-reconnect on failure.

        Checks every 30 seconds if the connection is alive (immediately
        when the transport reports a disconnect). Every ~2.5 minutes the
        companion is actively probed, regardless of traffic, so a dead
        link (commands timing out) triggers a reconnect too.
        """
        last_probe = time.monotonic()

        while self._running:
            try:
                await self._wait_watchdog_tick(self.WATCHDOG_CHECK_INTERVAL)

                if not self._running:
                    break

                # Check 1: transport up
                if not self._is_link_up():
                    logger.warning("Connection lost — attempting reconnect...")
                    await self._do_reconnect(self.RECONNECT_MAX_DELAY)
                    last_probe = time.monotonic()
                    continue

                # Check 2: active keepalive probe
                if time.monotonic() - last_probe >= self.PROBE_INTERVAL:
                    last_probe = time.monotonic()
                    if not await self._probe_link():
                        logger.warning("Keepalive failed — reconnecting...")
                        await self._do_reconnect(self.RECONNECT_MAX_DELAY)
                        last_probe = time.monotonic()
                        continue
                    logger.debug("Keepalive OK")
                    self._housekeeping()
                    await self._sync_node_status()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watchdog error: {e}")

    async def _sync_node_status(self, query: bool = False) -> None:
        """
        Copy battery (and, after a connect, model/firmware) into the state.

        The battery value comes for free from the keepalive probe (get_bat);
        query=True also asks the companion for its device info.
        """
        try:
            if query and hasattr(self.connection, "query_device_info"):
                await self.connection.query_device_info()
            device = getattr(self.connection, "device_info", None)
            if isinstance(device, dict):
                await self.state_manager.update_device_info(
                    device.get("model"), device.get("firmware"))
            battery = getattr(self.connection, "last_battery", None)
            if isinstance(battery, dict) and "level" in battery:
                await self.state_manager.update_battery(
                    battery.get("level"), battery.get("used_kb"), battery.get("total_kb"))
        except Exception as e:
            logger.debug(f"Node status update failed: {e}")

    async def _do_reconnect(self, max_backoff: int = RECONNECT_MAX_DELAY) -> bool:
        """
        Disconnect and reconnect the real radio with exponential backoff.

        Retries forever (5s, 10s, ... up to max_backoff) while the BBS runs.

        Returns:
            True once reconnected, False if the BBS stopped meanwhile
        """
        delay = self.RECONNECT_INITIAL_DELAY

        # Disconnect cleanly
        try:
            await self.connection.disconnect()
        except Exception:
            pass

        self.connection.connected = False
        await self.state_manager.set_disconnected("Reconnecting...")

        attempt = 0
        while self._running:
            attempt += 1
            try:
                await self.state_manager.set_reconnecting(attempt)
                logger.info(f"Reconnecting in {delay}s (attempt {attempt})...")
                await asyncio.sleep(delay)
                if not self._running:
                    break

                success = await self.connection.connect()
                if success:
                    logger.info("Reconnected successfully!")
                    await self._on_connected()
                    if self._link_lost_event is not None:
                        self._link_lost_event.clear()
                    return True

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Reconnect attempt failed: {e}")

            delay = min(delay * 2, max_backoff)

        return False

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

                if self._running and self.connection.connected:
                    logger.info("Sending periodic advertisement...")
                    if await self.connection.send_advert(flood=True):
                        with get_session() as session:
                            log_activity(session, EventType.ADVERT_SENT)
                    else:
                        logger.warning("Periodic advertisement failed")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error sending advert: {e}")

    def _beacon_text(self) -> str:
        """Render the beacon template; a broken template falls back to raw text."""
        template = str(self.config.beacon_message or "")
        try:
            return template.format(name=self.config.bbs_name)
        except (KeyError, IndexError, ValueError, AttributeError) as e:
            logger.warning(f"Invalid beacon template ({e}), sending it unformatted")
            return template

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

        while self._running:
            try:
                await asyncio.sleep(interval)

                if self._running and self.connection.connected:
                    beacon_text = self._beacon_text()
                    if not beacon_text:
                        continue
                    logger.info(f"Sending beacon: {beacon_text[:50]}...")
                    sender = getattr(self.connection, "send_channel_message", None)
                    if sender is None:
                        logger.warning("Beacon not supported by this connection")
                        continue
                    if await sender(0, beacon_text):
                        logger.info("Beacon sent on channel")
                    else:
                        logger.warning("Beacon send failed")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error sending beacon: {e}")


async def run_bbs(config: Optional[Config] = None, use_mock_fallback: bool = False) -> None:
    """
    Convenience function to run the BBS.

    Args:
        config: Optional configuration
        use_mock_fallback: Allow the simulated radio (development only)
    """
    bbs = BBSCore(config, use_mock_fallback=use_mock_fallback)

    try:
        await bbs.start()
        await bbs.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await bbs.stop()
