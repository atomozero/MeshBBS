"""
DM notifications for new PMs, mails, replies and @mentions.

MIT License - Copyright (c) 2026 MeshBBS Contributors

Commands call notify_event() while they run (inside the dispatcher's DB
session); the events are only buffered in memory. After the session is
committed the BBS core hands them to NotificationService.process_events(),
which:

- drops events for the sender themself, for users who opted out
  (!notifiche off) and for users active in the last ACTIVE_WINDOW (they
  will see the news anyway);
- aggregates them in ONE pending_notifications row per user (counts only,
  never message text; ephemeral PMs leave no sender name);
- delivers at most one notice per user every RATE_WINDOW, as a short DM
  ("[BBS] Nuovo PM da X: !inbox" or "[BBS] 3 novità (...): !inbox");
- when the user was not heard recently, or the DM is not acknowledged,
  keeps the notice until the user is heard again (advert or message),
  for at most PENDING_TTL.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Dict, List, Optional, Set

from bbs.models.base import get_session
from bbs.models.node_sighting import NodeSighting
from bbs.models.user import User
from bbs.models.user_prefs import PendingNotification, UserPrefs

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.notify")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("meshbbs.notify")


KIND_PM = "pm"
KIND_MAIL = "mail"
KIND_REPLY = "reply"
KIND_MENTION = "mention"

_KIND_FIELD = {
    KIND_PM: "pm_count",
    KIND_MAIL: "mail_count",
    KIND_REPLY: "reply_count",
    KIND_MENTION: "mention_count",
}

MAX_NOTICE_BYTES = 140
# Events buffered between two process_events() calls (defensive bound)
MAX_BUFFERED_EVENTS = 200


@dataclass
class NotificationEvent:
    recipient_key: str
    kind: str
    sender_key: Optional[str] = None
    sender_name: Optional[str] = None
    ref: Optional[int] = None
    ephemeral: bool = False


# ----------------------------------------------------------------------
# Module-level buffer used by the commands
# ----------------------------------------------------------------------

_service: Optional["NotificationService"] = None
_buffer: List[NotificationEvent] = []


def set_notification_service(service: Optional["NotificationService"]) -> None:
    """Register the running service (None disables notifications)."""
    global _service
    _service = service
    _buffer.clear()


def get_notification_service() -> Optional["NotificationService"]:
    return _service


def notify_event(
    recipient_key: str,
    kind: str,
    sender_key: Optional[str] = None,
    sender_name: Optional[str] = None,
    ref: Optional[int] = None,
    ephemeral: bool = False,
) -> None:
    """
    Record that recipient_key has something new (buffer only, no I/O).

    Safe to call from any command: it does nothing when no BBS core is
    running (tests, tools) and never raises.
    """
    if _service is None or not recipient_key or kind not in _KIND_FIELD:
        return
    if len(_buffer) >= MAX_BUFFERED_EVENTS:
        return
    _buffer.append(NotificationEvent(
        recipient_key=str(recipient_key),
        kind=kind,
        sender_key=sender_key,
        # Ephemeral PMs must not leak anything: no sender, no reference
        sender_name=None if ephemeral else sender_name,
        ref=None if ephemeral else ref,
        ephemeral=ephemeral,
    ))


def take_events() -> List[NotificationEvent]:
    """Return and clear the buffered events."""
    events = list(_buffer)
    _buffer.clear()
    return events


def discard_events() -> None:
    _buffer.clear()


# ----------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------

def _fit(text: str, max_bytes: int = MAX_NOTICE_BYTES) -> str:
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text
    return data[:max_bytes].decode("utf-8", errors="ignore")


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def render_notice(row: PendingNotification, prefix: str = "[BBS]") -> str:
    """Build the (≤140 bytes) notice text for a pending row."""
    counts = {f: int(getattr(row, f) or 0) for f in PendingNotification.COUNT_FIELDS}
    total = sum(counts.values())
    who = (row.last_sender or "").strip()[:16]
    ref = row.last_ref

    if total == 1:
        if counts["pm_count"]:
            text = f"{prefix} Nuovo PM da {who}: !inbox" if who else f"{prefix} Nuovo PM: !inbox"
        elif counts["mail_count"]:
            text = f"{prefix} Nuova mail da {who}: !mailbox" if who else f"{prefix} Nuova mail: !mailbox"
        elif counts["reply_count"]:
            target = f"!read {ref}" if ref else "!list"
            text = (f"{prefix} {who} ha risposto al tuo post: {target}" if who
                    else f"{prefix} Nuova risposta al tuo post: {target}")
        else:
            target = f"!read {ref}" if ref else "!inbox"
            text = (f"{prefix} {who} ti ha menzionato: {target}" if who
                    else f"{prefix} Nuova menzione: {target}")
        return _fit(text)

    parts = []
    if counts["pm_count"]:
        parts.append(f"{counts['pm_count']} PM")
    if counts["mail_count"]:
        parts.append(f"{counts['mail_count']} mail")
    if counts["reply_count"]:
        parts.append(_plural(counts["reply_count"], "risposta", "risposte"))
    if counts["mention_count"]:
        parts.append(_plural(counts["mention_count"], "menzione", "menzioni"))
    return _fit(f"{prefix} {total} novità ({', '.join(parts)}): !inbox")


# ----------------------------------------------------------------------
# Service
# ----------------------------------------------------------------------

SendFunc = Callable[[str, str], Awaitable[bool]]


class NotificationService:
    """Rate-limited, aggregated, deferred DM notifications."""

    # Max one notice per user in this window (events in between aggregate)
    RATE_WINDOW = timedelta(minutes=10)
    # Users active this recently are not notified (they'll see the news)
    ACTIVE_WINDOW = timedelta(minutes=2)
    # Users not heard for longer than this are not called over the radio:
    # the notice waits until they are heard again
    HEARD_WINDOW = timedelta(hours=6)
    # Undelivered notices are dropped after this
    PENDING_TTL = timedelta(days=7)
    # How often due (rate-limited) notices are retried
    TICK_INTERVAL = 60.0
    # Delay before delivering a waiting notice to a user just heard, so
    # the reply to their own command goes out first
    HEARD_DELAY = 3.0

    def __init__(
        self,
        send: SendFunc,
        prefix: str = "[BBS]",
        clock: Callable[[], datetime] = datetime.utcnow,
    ):
        self._send = send
        self.prefix = prefix
        self._clock = clock
        self._last_sent: Dict[str, datetime] = {}
        self._heard: Dict[str, datetime] = {}
        self._pending_keys: Set[str] = set()
        self._inflight: Set[str] = set()
        self._tasks: Set[asyncio.Task] = set()
        self._tick_task: Optional[asyncio.Task] = None
        self._last_expire: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load the keys of users with a waiting notice (at startup)."""
        try:
            with get_session() as session:
                self.expire(session)
                self._pending_keys = {
                    k for (k,) in session.query(PendingNotification.user_key).all()
                }
        except Exception as e:
            logger.warning(f"Could not load pending notifications: {e}")

    def start(self) -> None:
        self.load()
        if self._tick_task is None or self._tick_task.done():
            self._tick_task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        tasks = list(self._tasks)
        if self._tick_task is not None:
            tasks.append(self._tick_task)
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks.clear()
        self._tick_task = None

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _tick_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.TICK_INTERVAL)
                await self.tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Notification tick error: {e}")

    async def tick(self) -> None:
        """Retry notices whose rate window elapsed; expire old ones hourly."""
        now = self._clock()
        if self._last_expire is None or now - self._last_expire >= timedelta(hours=1):
            self._last_expire = now
            with get_session() as session:
                self.expire(session)
        for key in list(self._pending_keys):
            await self.flush(key)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def process_events(self, events: List[NotificationEvent]) -> int:
        """
        Apply filters, aggregate into pending rows and schedule delivery.

        Must be called outside any open write transaction.

        Returns:
            Number of events kept
        """
        if not events:
            return 0
        now = self._clock()
        touched: Set[str] = set()
        kept = 0
        try:
            with get_session() as session:
                for ev in events:
                    key = ev.recipient_key
                    if ev.sender_key and ev.sender_key == key:
                        continue
                    prefs = session.get(UserPrefs, key)
                    if prefs is not None and not prefs.notify:
                        continue
                    user = session.query(User).filter(User.public_key == key).first()
                    if user is None or user.is_banned:
                        continue
                    if user.last_seen and now - user.last_seen < self.ACTIVE_WINDOW:
                        continue

                    row = (
                        session.query(PendingNotification)
                        .filter(PendingNotification.user_key == key)
                        .first()
                    )
                    if row is None:
                        row = PendingNotification(
                            user_key=key, pm_count=0, mail_count=0, reply_count=0,
                            mention_count=0, wait_heard=False, attempts=0,
                            created_at=now, updated_at=now,
                        )
                        session.add(row)
                    field = _KIND_FIELD[ev.kind]
                    setattr(row, field, int(getattr(row, field) or 0) + 1)
                    row.last_sender = (ev.sender_name or None) and str(ev.sender_name)[:32]
                    row.last_ref = ev.ref
                    row.updated_at = now
                    touched.add(key)
                    kept += 1
        except Exception as e:
            logger.error(f"Notification processing failed: {e}")
            return 0

        self._pending_keys |= touched
        for key in touched:
            self._spawn(self.flush(key))
        return kept

    def on_heard(self, key: Optional[str], delay: Optional[float] = None) -> None:
        """
        A user/node was heard on the mesh (advert or message).

        Wakes a waiting notice for that user, if any (in-memory check only).
        """
        if not key:
            return
        key = str(key).lower()[:12]
        self._heard[key] = self._clock()
        if len(self._heard) > 2000:
            cutoff = self._clock() - self.HEARD_WINDOW
            self._heard = {k: v for k, v in self._heard.items() if v >= cutoff}
        if key in self._pending_keys and key not in self._inflight:
            self._spawn(self._wake(key, self.HEARD_DELAY if delay is None else delay))

    async def _wake(self, key: str, delay: float) -> None:
        if delay > 0:
            await asyncio.sleep(delay)
        with get_session() as session:
            row = self._row(session, key)
            if row is not None and row.wait_heard:
                row.wait_heard = False
        await self.flush(key)

    # ------------------------------------------------------------------
    # Delivery
    # ------------------------------------------------------------------

    @staticmethod
    def _row(session, key: str) -> Optional[PendingNotification]:
        return (
            session.query(PendingNotification)
            .filter(PendingNotification.user_key == key)
            .first()
        )

    def _heard_recently(self, session, key: str, now: datetime) -> bool:
        last = self._heard.get(key)
        user = session.query(User).filter(User.public_key == key).first()
        if user is not None and user.last_seen and (last is None or user.last_seen > last):
            last = user.last_seen
        node = session.get(NodeSighting, key[:12])
        if node is not None and node.last_seen and (last is None or node.last_seen > last):
            last = node.last_seen
        return last is not None and now - last < self.HEARD_WINDOW

    async def flush(self, key: str) -> bool:
        """
        Try to deliver the pending notice of one user now.

        Returns:
            True if a notice was delivered
        """
        if key in self._inflight:
            return False
        now = self._clock()
        with get_session() as session:
            row = self._row(session, key)
            if row is None:
                self._pending_keys.discard(key)
                return False
            if now - row.created_at > self.PENDING_TTL or row.total <= 0:
                session.delete(row)
                self._pending_keys.discard(key)
                return False
            if row.wait_heard:
                return False
            last = self._last_sent.get(key)
            if last is not None and now - last < self.RATE_WINDOW:
                return False  # the tick retries after the window
            if not self._heard_recently(session, key, now):
                row.wait_heard = True
                logger.debug(f"Notice for {key[:8]} deferred (not heard recently)")
                return False
            text = render_notice(row, self.prefix)
            sent_counts = {f: int(getattr(row, f) or 0) for f in row.COUNT_FIELDS}

        self._last_sent[key] = now
        self._inflight.add(key)
        try:
            ok = await self._send(key, text)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Notice to {key[:8]} failed: {e}")
            ok = False
        finally:
            self._inflight.discard(key)

        with get_session() as session:
            row = self._row(session, key)
            if row is None:
                self._pending_keys.discard(key)
                return ok
            if ok:
                for f, n in sent_counts.items():
                    setattr(row, f, max(0, int(getattr(row, f) or 0) - n))
                if row.total <= 0:
                    session.delete(row)
                    self._pending_keys.discard(key)
                logger.info(f"Notice delivered to {key[:8]}")
            else:
                row.wait_heard = True
                row.attempts = int(row.attempts or 0) + 1
                logger.info(f"Notice to {key[:8]} not acknowledged: waiting for the user")
        return ok

    def expire(self, session) -> int:
        """Delete notices older than PENDING_TTL."""
        cutoff = self._clock() - self.PENDING_TTL
        expired = [
            k for (k,) in session.query(PendingNotification.user_key)
            .filter(PendingNotification.created_at < cutoff).all()
        ]
        if expired:
            session.query(PendingNotification).filter(
                PendingNotification.created_at < cutoff
            ).delete(synchronize_session=False)
            self._pending_keys.difference_update(expired)
        return len(expired)


# ----------------------------------------------------------------------
# Preferences
# ----------------------------------------------------------------------


def set_user_notify(session, user_key: str, enabled: bool) -> None:
    """Store the notification preference of a user (creating the row)."""
    prefs = session.get(UserPrefs, user_key)
    if prefs is None:
        prefs = UserPrefs(user_key=user_key, notify=enabled)
        session.add(prefs)
    else:
        prefs.notify = enabled
    if not enabled:
        # Opting out also drops what was waiting
        session.query(PendingNotification).filter(
            PendingNotification.user_key == user_key
        ).delete(synchronize_session=False)
        if _service is not None:
            _service._pending_keys.discard(user_key)


def get_user_notify(session, user_key: str) -> bool:
    prefs = session.get(UserPrefs, user_key)
    return True if prefs is None else bool(prefs.notify)
