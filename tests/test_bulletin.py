"""
Tests for the daily channel bulletin and its web settings.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone, time as dtime
from types import SimpleNamespace

import pytest

from bbs.models.area import Area
from bbs.models.message import Message as Post
from bbs.models.user import User
from bbs.services.bulletin import (
    BulletinService, build_bulletin, format_weather_line, parse_bulletin_time,
    posts_per_area, MAX_BULLETIN_BYTES,
)

WEATHER = {
    "current": {"temperature_2m": 18.4, "weather_code": 0},
    "daily": {"temperature_2m_min": [11.6], "temperature_2m_max": [22.2]},
}


def blen(t):
    return len(t.encode("utf-8"))


class Sender:
    def __init__(self, results=None):
        self.sent = []
        self.results = list(results or [])

    async def __call__(self, channel, text):
        self.sent.append((channel, text))
        return self.results.pop(0) if self.results else True


def make(config, tmp_path, sender=None, weather=WEATHER):
    config.bulletin_enabled = True
    config.bulletin_time = "08:00"
    config.bulletin_channel = 0
    config.latitude, config.longitude = 45.0, 12.0
    return BulletinService(
        config, sender or Sender(), state_path=str(tmp_path / "bulletin.json"),
        weather_fetcher=lambda lat, lon: weather,
    )


class TestBuild:

    def test_parse_time(self):
        assert parse_bulletin_time("8:05") == dtime(8, 5)
        assert parse_bulletin_time("23:59") == dtime(23, 59)
        for bad in ("24:00", "8", "ab:cd", "", None, "08:60"):
            assert parse_bulletin_time(bad) is None

    def test_weather_line(self):
        assert format_weather_line(WEATHER) == "18C Sereno 12/22C"
        assert format_weather_line(None) is None
        assert format_weather_line({"current": {"temperature_2m": "x"}}) is None

    def test_full_text(self):
        text = build_bulletin("MeshBBS", "18C Sereno 12/22C", [("tech", 2), ("generale", 3)])
        assert text == ("MeshBBS: 18C Sereno 12/22C. 5 nuovi post ieri: generale 3, tech 2. "
                        "!help per i comandi")

    def test_no_posts(self):
        assert build_bulletin("B", None, []) == "B: Nessun post ieri. !help per i comandi"

    def test_truncation_drops_areas_first(self):
        areas = [(f"area-numero-{i}", 10 - i) for i in range(10)]
        text = build_bulletin("Nome BBS", "18C Parz.nuvoloso 12/22C", areas)
        assert blen(text) <= MAX_BULLETIN_BYTES
        assert "18C" in text and text.endswith("!help per i comandi")
        assert "+" in text and "area-numero-0 10" in text

    def test_hard_limit_with_multibyte(self):
        areas = [("è" * 30, 5), ("ü" * 30, 4)]
        text = build_bulletin("Ö" * 60, "🌧" * 30, areas)
        assert blen(text) <= MAX_BULLETIN_BYTES
        text.encode("utf-8").decode("utf-8")
        assert "!help" in text


class TestSchedule:

    async def test_once_per_day_and_persisted(self, config, db_session, tmp_path):
        sender = Sender()
        svc = make(config, tmp_path, sender)
        today = datetime.now().replace(hour=8, minute=1, second=0, microsecond=0)
        assert await svc.run_once(today - timedelta(minutes=5)) is False  # too early
        assert await svc.run_once(today) is True
        assert len(sender.sent) == 1 and sender.sent[0][0] == 0
        assert blen(sender.sent[0][1]) <= MAX_BULLETIN_BYTES
        assert await svc.run_once(today + timedelta(minutes=30)) is False

        # A restart (new service, same state file) does not resend
        svc2 = make(config, tmp_path, sender)
        assert await svc2.run_once(today + timedelta(minutes=40)) is False
        assert len(sender.sent) == 1
        # Next day: sent again
        assert await svc2.run_once(today + timedelta(days=1)) is True

    async def test_not_sent_outside_window_or_disabled(self, config, db_session, tmp_path):
        sender = Sender()
        svc = make(config, tmp_path, sender)
        evening = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
        assert await svc.run_once(evening) is False
        config.bulletin_enabled = False
        assert await svc.run_once(evening.replace(hour=8, minute=5)) is False
        config.bulletin_enabled = True
        config.bulletin_time = "boh"
        assert await svc.run_once(evening.replace(hour=8, minute=5)) is False
        assert sender.sent == []

    async def test_retry_after_failure_is_rate_limited(self, config, db_session, tmp_path):
        sender = Sender(results=[False, False, False, False])
        svc = make(config, tmp_path, sender)
        t = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        assert await svc.run_once(t) is False
        assert await svc.run_once(t + timedelta(minutes=5)) is False
        assert len(sender.sent) == 1  # waits RETRY_DELAY
        await svc.run_once(t + timedelta(minutes=16))
        await svc.run_once(t + timedelta(minutes=32))
        await svc.run_once(t + timedelta(minutes=48))
        assert len(sender.sent) == BulletinService.MAX_ATTEMPTS_PER_DAY

    async def test_channel_setting(self, config, db_session, tmp_path):
        sender = Sender()
        svc = make(config, tmp_path, sender)
        config.bulletin_channel = 2
        t = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        await svc.run_once(t)
        assert sender.sent[0][0] == 2
        config.bulletin_channel = 99
        assert svc.channel() == 0

    async def test_content_counts_yesterday_public_posts(self, config, db_session, tmp_path):
        db_session.add(User(public_key="a1a1a1a1a1a1"))
        hidden = Area(name="segreta", is_public=False)
        db_session.add(hidden)
        db_session.flush()
        gen = db_session.query(Area).filter_by(name="generale").one()
        now = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        # yesterday at local noon, stored in UTC like every post
        y_noon = datetime.combine((now - timedelta(days=1)).date(), dtime(12)) \
            .astimezone(timezone.utc).replace(tzinfo=None)
        for area, ts in ((gen, y_noon), (gen, y_noon), (hidden, y_noon),
                         (gen, y_noon - timedelta(days=1))):
            db_session.add(Post(area_id=area.id, sender_key="a1a1a1a1a1a1", body="x", timestamp=ts))
        db_session.commit()
        counts = posts_per_area(db_session, (now - timedelta(days=1)).date())
        assert counts == [("generale", 2)]
        svc = make(config, tmp_path)
        text = await svc.compose(now)
        assert "2 nuovi post ieri: generale 2" in text
        assert "segreta" not in text and "18C Sereno" in text

    async def test_weather_failure_does_not_block(self, config, db_session, tmp_path):
        def slow(lat, lon):
            raise TimeoutError("no network")

        svc = make(config, tmp_path)
        svc._weather_fetcher = slow
        text = await svc.compose(datetime.now())
        assert text.startswith(config.bbs_name) and "C " not in text

    async def test_no_location_no_weather(self, config, db_session, tmp_path):
        svc = make(config, tmp_path)
        config.latitude = None
        assert await svc._weather() is None


class TestWebSettings:

    def _post(self, data):
        from tests.test_web_light_security import auth, call, ORIGIN
        cookies, csrf = auth()
        return call("/api/settings", method="POST", cookies=cookies, json_body=data,
                    headers={"X-CSRF-Token": csrf, "Origin": ORIGIN})

    @pytest.fixture(autouse=True)
    def _pw(self, monkeypatch):
        import web_light.server as srv
        monkeypatch.setattr(srv, "_admin_password", "S3cure-Test-Passw0rd!")
        monkeypatch.setattr(srv, "_admin_username", "admin")

    def test_settings_page_shows_bulletin_fields(self, config, monkeypatch):
        from tests.test_web_light_security import auth, call
        config.bulletin_time = "\"><script>x</script>"
        config.bulletin_enabled = True
        monkeypatch.setattr(config, "save_to_file", lambda: True)
        cookies, _ = auth()
        r = call("/settings", cookies=cookies)
        assert r.code == 200
        assert 'name="bulletin_time"' in r.body and "<script>x</script>" not in r.body
        assert '<option value="1" selected>' in r.body
        assert "querySelectorAll('input, select')" in r.body

    def test_save_bulletin_settings(self, config, monkeypatch):
        monkeypatch.setattr(config, "save_to_file", lambda: True)
        r = self._post({"bulletin_enabled": "1", "bulletin_time": "7:30", "bulletin_channel": "3"})
        assert r.json()["ok"] is True
        assert config.bulletin_enabled is True
        assert config.bulletin_time == "07:30" and config.bulletin_channel == 3
        r = self._post({"bulletin_enabled": "0"})
        assert config.bulletin_enabled is False

    def test_invalid_bulletin_values_rejected(self, config, monkeypatch):
        monkeypatch.setattr(config, "save_to_file", lambda: True)
        assert self._post({"bulletin_time": "25:00"}).json()["ok"] is False
        assert self._post({"bulletin_channel": "9"}).json()["ok"] is False
        assert config.bulletin_time == "08:00" and config.bulletin_channel == 0
