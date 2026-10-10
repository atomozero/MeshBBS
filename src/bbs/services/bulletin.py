"""
Daily channel bulletin.

MIT License - Copyright (c) 2026 MeshBBS Contributors

Once a day, at bulletin_time (server local time), a short message is sent
on bulletin_channel, e.g.:

    MeshBBS: 18C Sereno 12/22C. Ieri 5 post: generale 3, tech 2. !help per i comandi

It always fits MAX_BULLETIN_BYTES (areas, then weather are dropped first).
The date of the last bulletin is persisted next to the database so a
restart never sends it twice; a bulletin is only sent within SEND_WINDOW
after the configured time (a BBS started in the evening does not send
the morning bulletin).
"""

import asyncio
import json
import re
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Tuple

from bbs.models.base import get_session

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.bulletin")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("meshbbs.bulletin")


MAX_BULLETIN_BYTES = 140
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
HELP_TAIL = "!help per i comandi"


def parse_bulletin_time(value) -> Optional[dtime]:
    """Parse "HH:MM" (None if invalid)."""
    m = TIME_RE.match(str(value or "").strip())
    if not m:
        return None
    return dtime(int(m.group(1)), int(m.group(2)))


def _blen(text: str) -> int:
    return len(text.encode("utf-8"))


def _cut(text: str, max_bytes: int) -> str:
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text
    return data[:max_bytes].decode("utf-8", errors="ignore").rstrip()


def format_weather_line(data: Optional[dict]) -> Optional[str]:
    """Compact weather: '18C Sereno 12/22C' (None if unavailable)."""
    if not data:
        return None
    try:
        from bbs.commands.meteo_cmd import _WMO

        cur = data.get("current", {}) or {}
        daily = data.get("daily", {}) or {}
        parts = []
        temp = cur.get("temperature_2m")
        if temp is not None:
            parts.append(f"{round(float(temp))}C")
        code = cur.get("weather_code")
        if code is not None:
            parts.append(_WMO.get(int(code), "?"))
        mins = daily.get("temperature_2m_min") or []
        maxs = daily.get("temperature_2m_max") or []
        if mins and maxs and mins[0] is not None and maxs[0] is not None:
            parts.append(f"{round(float(mins[0]))}/{round(float(maxs[0]))}C")
        return " ".join(parts) or None
    except Exception:
        return None


def build_bulletin(
    name: str,
    weather: Optional[str],
    area_counts: List[Tuple[str, int]],
    max_bytes: int = MAX_BULLETIN_BYTES,
) -> str:
    """
    Compose the bulletin, shrinking it to max_bytes.

    Order of sacrifice: areas (from the least active, replaced by "+N"),
    then the weather, then the name; the final "!help" hint is kept.
    """
    name = (name or "BBS").strip()[:24]
    areas = sorted([(a, n) for a, n in area_counts if n > 0], key=lambda x: (-x[1], x[0]))
    total = sum(n for _, n in areas)

    def posts_part(shown: int) -> str:
        if total == 0:
            return "Nessun post ieri"
        items = [f"{a} {n}" for a, n in areas[:shown]]
        hidden = len(areas) - shown
        if hidden > 0:
            items.append(f"+{hidden}")
        label = "nuovo post" if total == 1 else "nuovi post"
        if not items or (shown == 0 and hidden > 0):
            return f"{total} {label} ieri"
        return f"{total} {label} ieri: {', '.join(items)}"

    def compose(with_name: bool, weather_part: Optional[str], shown: int) -> str:
        segs = []
        head = f"{name}: " if with_name else ""
        if weather_part:
            segs.append(weather_part)
        segs.append(posts_part(shown))
        segs.append(HELP_TAIL)
        return head + ". ".join(segs)

    for with_name in (True, False):
        for weather_part in (weather, None) if weather else (None,):
            for shown in range(len(areas), -1, -1):
                text = compose(with_name, weather_part, shown)
                if _blen(text) <= max_bytes:
                    return text
    return _cut(compose(False, None, 0), max_bytes)


def _local_day_bounds_utc(day: date) -> Tuple[datetime, datetime]:
    """UTC (naive) bounds of a local calendar day."""
    start = datetime.combine(day, dtime.min).astimezone().astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), dtime.min).astimezone().astimezone(timezone.utc)
    return start.replace(tzinfo=None), end.replace(tzinfo=None)


def posts_per_area(session, day: date) -> List[Tuple[str, int]]:
    """Posts per public area on a local day (hidden areas excluded)."""
    from sqlalchemy import func
    from bbs.models.area import Area
    from bbs.models.message import Message

    start, end = _local_day_bounds_utc(day)
    rows = (
        session.query(Area.name, func.count(Message.id))
        .join(Message, Message.area_id == Area.id)
        .filter(Area.is_public.is_(True), Message.timestamp >= start, Message.timestamp < end)
        .group_by(Area.name)
        .all()
    )
    return [(str(a), int(n)) for a, n in rows]


SendChannel = Callable[[int, str], Awaitable[bool]]


class BulletinService:
    """Schedules and sends the daily bulletin."""

    CHECK_INTERVAL = 30.0
    # Only send within this window after the configured time
    SEND_WINDOW = timedelta(hours=2)
    # Pause between attempts after a failed send
    RETRY_DELAY = timedelta(minutes=15)
    MAX_ATTEMPTS_PER_DAY = 3

    def __init__(
        self,
        config,
        send_channel: SendChannel,
        state_path: Optional[str] = None,
        clock: Callable[[], datetime] = datetime.now,
        weather_fetcher: Optional[Callable[[float, float], Optional[dict]]] = None,
    ):
        self.config = config
        self._send_channel = send_channel
        if state_path is None:
            state_path = str(Path(config.database_path).parent / "bulletin_state.json")
        self.state_path = state_path
        self._clock = clock
        self._weather_fetcher = weather_fetcher
        self._attempts: Tuple[Optional[date], int] = (None, 0)
        self._last_attempt: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Persistent state
    # ------------------------------------------------------------------

    def last_run_date(self) -> Optional[date]:
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return date.fromisoformat(json.load(f).get("last_date", ""))
        except Exception:
            return None

    def _save_run_date(self, day: date) -> None:
        try:
            Path(self.state_path).parent.mkdir(parents=True, exist_ok=True)
            tmp = f"{self.state_path}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"last_date": day.isoformat()}, f)
            Path(tmp).replace(self.state_path)
        except Exception as e:
            logger.error(f"Could not save bulletin state: {e}")

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def is_due(self, now: Optional[datetime] = None) -> bool:
        now = now or self._clock()
        if not getattr(self.config, "bulletin_enabled", False):
            return False
        at = parse_bulletin_time(getattr(self.config, "bulletin_time", "08:00"))
        if at is None:
            return False
        scheduled = datetime.combine(now.date(), at)
        if not (scheduled <= now < scheduled + self.SEND_WINDOW):
            return False
        if self.last_run_date() == now.date():
            return False
        day, attempts = self._attempts
        if day == now.date() and attempts >= self.MAX_ATTEMPTS_PER_DAY:
            return False
        if self._last_attempt is not None and now - self._last_attempt < self.RETRY_DELAY:
            return False
        return True

    async def _weather(self) -> Optional[str]:
        lat = getattr(self.config, "latitude", None)
        lon = getattr(self.config, "longitude", None)
        if lat is None or lon is None:
            return None
        fetch = self._weather_fetcher
        if fetch is None:
            from bbs.commands.meteo_cmd import _fetch_meteo as fetch
        try:
            # Blocking HTTP: run in a thread, bounded in time
            data = await asyncio.wait_for(asyncio.to_thread(fetch, lat, lon), timeout=10)
        except Exception as e:
            logger.warning(f"Bulletin weather unavailable: {e}")
            return None
        return format_weather_line(data)

    async def compose(self, now: Optional[datetime] = None) -> str:
        now = now or self._clock()
        yesterday = now.date() - timedelta(days=1)
        try:
            with get_session() as session:
                counts = posts_per_area(session, yesterday)
        except Exception as e:
            logger.warning(f"Bulletin post count failed: {e}")
            counts = []
        weather = await self._weather()
        return build_bulletin(getattr(self.config, "bbs_name", "BBS"), weather, counts)

    def channel(self) -> int:
        try:
            idx = int(getattr(self.config, "bulletin_channel", 0) or 0)
        except (TypeError, ValueError):
            idx = 0
        return idx if 0 <= idx <= 7 else 0

    async def run_once(self, now: Optional[datetime] = None) -> bool:
        """Send the bulletin if due. Returns True if sent."""
        now = now or self._clock()
        if not self.is_due(now):
            return False
        day, attempts = self._attempts
        self._attempts = (now.date(), (attempts if day == now.date() else 0) + 1)
        self._last_attempt = now
        text = await self.compose(now)
        ok = False
        try:
            ok = bool(await self._send_channel(self.channel(), text))
        except Exception as e:
            logger.error(f"Bulletin send error: {e}")
        if ok:
            self._save_run_date(now.date())
            logger.info(f"Daily bulletin sent on channel {self.channel()}")
        else:
            logger.warning("Daily bulletin not sent (will retry)")
        return ok

    async def run(self, is_running: Callable[[], bool]) -> None:
        while is_running():
            try:
                await asyncio.sleep(self.CHECK_INTERVAL)
                if is_running():
                    await self.run_once()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Bulletin error: {e}")
