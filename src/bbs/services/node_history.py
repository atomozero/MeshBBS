"""
Mesh node history: who was heard, when, how far.

MIT License - Copyright (c) 2026 MeshBBS Contributors

Nodes are recorded from received adverts and from received messages.
Writes are debounced (at most one per node every WRITE_INTERVAL) to spare
the SD card of a Raspberry Pi: in between, sightings are accumulated in
memory and written with the next allowed write (or by flush_all()).
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Set, Tuple

from bbs.models.base import get_session
from bbs.models.node_sighting import NodeSighting, NodeSightingDay

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.nodes")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("meshbbs.nodes")


PREFIX_LEN = 12
_HEX_RE = re.compile(r"^[0-9a-f]+$")

NODE_TYPE_NAMES = {0: "---", 1: "CLI", 2: "RPT", 3: "ROOM", 4: "SENS"}


def node_prefix(key) -> Optional[str]:
    """Return the canonical 12-hex prefix of a public key (or None)."""
    if isinstance(key, (bytes, bytearray)):
        key = key.hex()
    key = str(key or "").strip().lower()
    if len(key) < PREFIX_LEN or not _HEX_RE.match(key[:PREFIX_LEN]):
        return None
    return key[:PREFIX_LEN]


def local_day(now_utc: datetime) -> date:
    """Local calendar day of a naive UTC datetime."""
    return now_utc.replace(tzinfo=timezone.utc).astimezone().date()


def _clean_name(name) -> Optional[str]:
    if name is None:
        return None
    name = "".join(ch for ch in str(name) if ch.isprintable()).strip()
    return name[:32] or None


@dataclass
class _Pending:
    """Sightings of one node accumulated since the last DB write."""

    count: int = 0
    last_seen: Optional[datetime] = None
    fields: Dict[str, object] = field(default_factory=dict)


class NodeHistory:
    """Debounced recorder and queries for the node_sightings tables."""

    WRITE_INTERVAL = timedelta(minutes=5)
    RETENTION_DAYS = 30

    def __init__(self, clock: Callable[[], datetime] = datetime.utcnow):
        self._clock = clock
        self._last_write: Dict[str, datetime] = {}
        self._pending: Dict[str, _Pending] = {}
        self._days_written: Set[Tuple[date, str]] = set()

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(
        self,
        key,
        name=None,
        node_type=None,
        hops=None,
        snr=None,
        rssi=None,
        lat=None,
        lon=None,
    ) -> bool:
        """
        Record that a node was heard.

        Returns:
            True if the sighting was written to the database now
        """
        prefix = node_prefix(key)
        if prefix is None:
            return False
        now = self._clock()

        pending = self._pending.setdefault(prefix, _Pending())
        pending.count += 1
        pending.last_seen = now
        values = {
            "name": _clean_name(name),
            "node_type": _as_int(node_type),
            "last_hops": _as_int(hops),
            "snr": _as_float(snr),
            "rssi": _as_int(rssi),
        }
        lat, lon = _as_float(lat), _as_float(lon)
        if lat is not None and lon is not None and (lat, lon) != (0.0, 0.0) \
                and -90 <= lat <= 90 and -180 <= lon <= 180:
            values["lat"], values["lon"] = lat, lon
        for k, v in values.items():
            if v is not None:
                pending.fields[k] = v

        last = self._last_write.get(prefix)
        new_day = last is not None and local_day(last) != local_day(now)
        if last is not None and not new_day and now - last < self.WRITE_INTERVAL:
            return False
        return self._write(prefix)

    def _write(self, prefix: str) -> bool:
        pending = self._pending.pop(prefix, None)
        if pending is None or pending.last_seen is None:
            return False
        try:
            with get_session() as session:
                row = session.get(NodeSighting, prefix)
                if row is None:
                    row = NodeSighting(
                        pubkey_prefix=prefix,
                        first_seen=pending.last_seen,
                        last_seen=pending.last_seen,
                        count=0,
                    )
                    session.add(row)
                row.count = int(row.count or 0) + pending.count
                row.last_seen = pending.last_seen
                for k, v in pending.fields.items():
                    setattr(row, k, v)

                day = local_day(pending.last_seen)
                if (day, prefix) not in self._days_written:
                    if session.get(NodeSightingDay, (day, prefix)) is None:
                        session.add(NodeSightingDay(day=day, pubkey_prefix=prefix))
                    self._days_written.add((day, prefix))
            self._last_write[prefix] = pending.last_seen
            return True
        except Exception as e:
            logger.warning(f"Node sighting write failed for {prefix}: {e}")
            return False

    def flush_all(self) -> int:
        """Write every accumulated sighting (on shutdown / housekeeping)."""
        written = 0
        for prefix in list(self._pending):
            if self._write(prefix):
                written += 1
        return written

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def purge(self, retention_days: int = RETENTION_DAYS) -> int:
        """Delete nodes not heard for retention_days (and old day rows)."""
        now = self._clock()
        cutoff = now - timedelta(days=retention_days)
        day_cutoff = local_day(now) - timedelta(days=retention_days)
        with get_session() as session:
            deleted = (
                session.query(NodeSighting)
                .filter(NodeSighting.last_seen < cutoff)
                .delete(synchronize_session=False)
            )
            session.query(NodeSightingDay).filter(
                NodeSightingDay.day < day_cutoff
            ).delete(synchronize_session=False)
        # Bound the in-memory state too
        self._last_write = {
            k: v for k, v in self._last_write.items() if now - v < timedelta(days=1)
        }
        today = local_day(now)
        self._days_written = {d for d in self._days_written if d[0] >= today}
        return deleted


# ----------------------------------------------------------------------
# Queries (used by !nodes and the web panel)
# ----------------------------------------------------------------------

def recent_nodes(session, limit: int = 50) -> List[NodeSighting]:
    """Nodes ordered by last_seen (most recent first)."""
    return (
        session.query(NodeSighting)
        .order_by(NodeSighting.last_seen.desc())
        .limit(limit)
        .all()
    )


def nodes_per_day(session, days: int = 7, today: Optional[date] = None) -> List[Tuple[date, int]]:
    """Number of distinct nodes heard per day, oldest first (zeros included)."""
    from sqlalchemy import func

    today = today or local_day(datetime.utcnow())
    first = today - timedelta(days=days - 1)
    counts = dict(
        session.query(NodeSightingDay.day, func.count(NodeSightingDay.pubkey_prefix))
        .filter(NodeSightingDay.day >= first, NodeSightingDay.day <= today)
        .group_by(NodeSightingDay.day)
        .all()
    )
    return [(first + timedelta(days=i), int(counts.get(first + timedelta(days=i), 0)))
            for i in range(days)]


def format_ago(then: Optional[datetime], now: Optional[datetime] = None) -> str:
    """Compact Italian 'time ago': 30s, 5m, 3h, 2g."""
    if then is None:
        return "?"
    now = now or datetime.utcnow()
    secs = max(0, int((now - then).total_seconds()))
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m"
    if secs < 86400:
        return f"{secs // 3600}h"
    return f"{secs // 86400}g"


def _as_int(value) -> Optional[int]:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value) -> Optional[float]:
    try:
        f = None if value is None else float(value)
    except (TypeError, ValueError):
        return None
    if f is None or f != f or f in (float("inf"), float("-inf")):
        return None
    return f
