"""
Remote MeshCore repeater telemetry monitor.

Polls configured repeaters at a fixed interval, logging in with the
admin password and requesting status/telemetry. Samples are kept in
memory (last sample per repeater) and appended to a JSONL file.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.repeater_monitor")
except ImportError:
    import logging
    logger = logging.getLogger("meshbbs.repeater_monitor")

try:
    from meshcore import EventType
except ImportError:
    EventType = None


@dataclass
class RepeaterTarget:
    name: str
    public_key: str
    password_env: str
    last_sample: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None
    last_attempt: Optional[str] = None

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "public_key": self.public_key,
            "last_sample": self.last_sample,
            "last_error": self.last_error,
            "last_attempt": self.last_attempt,
        }


class RepeaterMonitor:
    """Background task that polls remote repeaters for telemetry."""

    def __init__(
        self,
        bbs: Any,
        targets: List[RepeaterTarget],
        interval_seconds: int = 1800,
        jsonl_path: Optional[str] = None,
        request_timeout: float = 20.0,
    ):
        self.bbs = bbs
        self.targets = targets
        self.interval_seconds = max(60, int(interval_seconds))
        self.jsonl_path = jsonl_path
        self.request_timeout = request_timeout
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is not None:
            return
        if not self.targets:
            logger.info("Repeater monitor: no targets configured, not starting")
            return
        if EventType is None:
            logger.warning("Repeater monitor: meshcore library unavailable, disabled")
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="repeater_monitor")
        logger.info(
            f"Repeater monitor started: {len(self.targets)} target(s), "
            f"interval={self.interval_seconds}s"
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def snapshot(self) -> List[Dict[str, Any]]:
        return [t.to_public_dict() for t in self.targets]

    async def _run(self) -> None:
        # Small initial delay so the BBS finishes booting first
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=30)
            return
        except asyncio.TimeoutError:
            pass

        while not self._stop.is_set():
            for target in self.targets:
                if self._stop.is_set():
                    break
                try:
                    await self._poll_target(target)
                except Exception as e:
                    target.last_error = f"unexpected: {e}"
                    logger.exception(f"Repeater monitor: error polling {target.name}")

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
                return
            except asyncio.TimeoutError:
                continue

    async def _poll_target(self, target: RepeaterTarget) -> None:
        mc = getattr(self.bbs.connection, "_meshcore", None)
        if mc is None:
            target.last_error = "radio not connected"
            return

        target.last_attempt = datetime.now(timezone.utc).isoformat()

        password = os.getenv(target.password_env, "")
        if not password:
            target.last_error = f"missing env var {target.password_env}"
            logger.warning(
                f"Repeater monitor: {target.name} skipped, "
                f"env var {target.password_env} not set"
            )
            return

        contact = mc.get_contact_by_key_prefix(target.public_key[:12])
        if contact is None:
            target.last_error = "contact not in companion contact list"
            return

        try:
            login_result = await mc.commands.send_login(contact, password)
            if getattr(login_result, "type", None) == EventType.ERROR:
                target.last_error = "login send failed"
                return

            login_evt = await mc.wait_for_event(
                EventType.LOGIN_SUCCESS, timeout=self.request_timeout
            )
            if login_evt is None:
                failed = await mc.wait_for_event(EventType.LOGIN_FAILED, timeout=0.1)
                target.last_error = (
                    "login rejected (bad password?)" if failed else "login timeout"
                )
                return

            status_result = await mc.commands.send_statusreq(contact)
            if getattr(status_result, "type", None) == EventType.ERROR:
                target.last_error = "status request send failed"
                return

            status_evt = await mc.wait_for_event(
                EventType.STATUS_RESPONSE, timeout=self.request_timeout
            )
            if status_evt is None:
                target.last_error = "status response timeout"
                return

            sample = self._build_sample(target, status_evt.payload)
            target.last_sample = sample
            target.last_error = None
            self._append_jsonl(sample)
            logger.info(
                f"Repeater monitor: {target.name} sample ok "
                f"(batt={sample.get('battery_mv')}mV uptime={sample.get('uptime_s')}s)"
            )

        except Exception as e:
            target.last_error = str(e)
            logger.warning(f"Repeater monitor: {target.name} poll failed: {e}")
        finally:
            try:
                await mc.commands.send_logout(contact)
            except Exception:
                pass

    def _build_sample(self, target: RepeaterTarget, payload: Any) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if isinstance(payload, dict):
            data = dict(payload)
        else:
            data = {"raw": repr(payload)}
        data["timestamp"] = datetime.now(timezone.utc).isoformat()
        data["repeater"] = target.name
        data["public_key"] = target.public_key
        return data

    def _append_jsonl(self, sample: Dict[str, Any]) -> None:
        if not self.jsonl_path:
            return
        try:
            Path(self.jsonl_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Repeater monitor: could not append JSONL: {e}")


def load_targets_from_config(config: Any) -> List[RepeaterTarget]:
    """
    Load repeater targets from config.

    Looks for config.repeater_monitor_targets, a list of dicts with
    name, public_key, password_env.
    """
    raw = getattr(config, "repeater_monitor_targets", None) or []
    targets: List[RepeaterTarget] = []
    for entry in raw:
        try:
            targets.append(
                RepeaterTarget(
                    name=entry["name"],
                    public_key=entry["public_key"],
                    password_env=entry.get("password_env", ""),
                )
            )
        except (KeyError, TypeError) as e:
            logger.warning(f"Repeater monitor: invalid target entry {entry}: {e}")
    return targets
