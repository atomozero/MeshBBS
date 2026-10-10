"""
Tests for DM notifications: rate limit, aggregation, opt-out, ephemeral
privacy, deferred delivery on advert/message, expiry.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
from datetime import datetime, timedelta

import pytest

import bbs.models.base as db_base
from bbs.core import BBSCore
from bbs.models.message import Message as Post
from bbs.models.user import User
from bbs.models.user_prefs import PendingNotification, UserPrefs
from bbs.services import notifications as notify
from bbs.services.notifications import NotificationService, render_notice
from meshbbs_radio.connection import MockMeshCoreConnection
from meshbbs_radio.messages import Message

ALICE = "a1a1a1a1a1a1"
BOB = "b2b2b2b2b2b2"
CARL = "c3c3c3c3c3c3"


class Clock:
    def __init__(self):
        self.now = datetime.utcnow()

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += timedelta(**kw)


class FakeSender:
    def __init__(self, results=None):
        self.sent = []
        self.results = list(results or [])

    async def __call__(self, dest, text):
        self.sent.append((dest, text))
        return self.results.pop(0) if self.results else True


class AckConnection(MockMeshCoreConnection):
    def __init__(self, results=None):
        super().__init__(node_name="TestBBS")
        self.connected = True
        self.sent = []
        self.results = list(results or [])

    async def send_message(self, destination, text, use_path=True):
        self.sent.append((destination, text))
        return self.results.pop(0) if self.results else True


async def settle(rounds=20):
    for _ in range(rounds):
        await asyncio.sleep(0)


@pytest.fixture
def users(db_session):
    old = datetime.utcnow() - timedelta(hours=1)
    for key, nick in ((ALICE, "alice"), (BOB, "bob"), (CARL, "carl")):
        db_session.add(User(public_key=key, nickname=nick, last_seen=old))
    db_session.commit()
    yield
    notify.set_notification_service(None)


def set_last_seen(key, when):
    with db_base.get_session() as s:
        s.query(User).filter(User.public_key == key).update({"last_seen": when})


def pending(key):
    with db_base.get_session() as s:
        row = s.query(PendingNotification).filter_by(user_key=key).first()
        if row is None:
            return None
        return {f: getattr(row, f) for f in (
            "pm_count", "mail_count", "reply_count", "mention_count",
            "last_sender", "last_ref", "wait_heard", "attempts")}


def make_core(config, sender=None, clock=None):
    conn = AckConnection()
    core = BBSCore(config=config, connection=conn)
    core.rate_limiter = None  # user rate limit is not under test here
    svc = NotificationService(
        send=sender or core._send_notification, prefix="[BBS]", clock=clock or Clock(),
    )
    svc.HEARD_DELAY = 0
    notify.set_notification_service(svc)
    core.notifications = svc
    return core, svc, conn


async def say(core, key, text):
    return await core.handle_message(Message(sender_key=key, text=text))


class TestNotifications:

    async def test_pm_notifies_recipient(self, config, users):
        config.send_delay = 0
        core, svc, conn = make_core(config)
        await say(core, ALICE, "!msg bob ciao bob")
        await settle()
        assert (BOB, "[BBS] Nuovo PM da alice: !inbox") in conn.sent
        assert pending(BOB) is None  # delivered and ACKed

    async def test_rate_limit_and_aggregation(self, config, users):
        clock = Clock()
        sender = FakeSender()
        core, svc, _ = make_core(config, sender=sender, clock=clock)
        await say(core, ALICE, "!msg bob uno")
        await settle()
        assert len(sender.sent) == 1

        await say(core, ALICE, "!msg bob due")
        await say(core, CARL, "!mail bob Oggetto | corpo")
        await settle()
        assert len(sender.sent) == 1  # rate limited: aggregated
        assert pending(BOB)["pm_count"] == 1 and pending(BOB)["mail_count"] == 1

        clock.advance(minutes=5)
        await svc.tick()
        assert len(sender.sent) == 1
        clock.advance(minutes=6)
        await svc.tick()
        assert sender.sent[-1] == (BOB, "[BBS] 2 novità (1 PM, 1 mail): !inbox")
        assert pending(BOB) is None

    async def test_not_notified_when_recently_active(self, config, users):
        sender = FakeSender()
        core, svc, _ = make_core(config, sender=sender)
        set_last_seen(BOB, datetime.utcnow() - timedelta(seconds=30))
        await say(core, ALICE, "!msg bob ciao")
        await settle()
        assert sender.sent == []
        assert pending(BOB) is None

    async def test_no_self_notification_on_reply(self, config, users):
        sender = FakeSender()
        core, svc, _ = make_core(config, sender=sender)
        await say(core, ALICE, "!post primo post")
        with db_base.get_session() as s:
            post_id = s.query(Post).first().id
        await say(core, ALICE, f"!reply {post_id} rispondo a me")
        await settle()
        assert sender.sent == []

    async def test_reply_and_mention_texts(self, config, users):
        sender = FakeSender()
        clock = Clock()
        core, svc, _ = make_core(config, sender=sender, clock=clock)
        await say(core, ALICE, "!post primo post")
        # alice was just active: she would not be notified
        set_last_seen(ALICE, datetime.utcnow() - timedelta(hours=1))
        with db_base.get_session() as s:
            post_id = s.query(Post).first().id
        await say(core, BOB, f"!reply {post_id} ottimo")
        await settle()
        with db_base.get_session() as s:
            reply_id = s.query(Post).order_by(Post.id.desc()).first().id
        assert sender.sent[-1] == (ALICE, f"[BBS] bob ha risposto al tuo post: !read {reply_id}")

        await say(core, BOB, "!post ciao @carl come va")
        await settle()
        assert sender.sent[-1][0] == CARL
        assert sender.sent[-1][1].startswith("[BBS] bob ti ha menzionato: !read ")

    async def test_opt_out(self, config, users):
        sender = FakeSender()
        core, svc, _ = make_core(config, sender=sender)
        resp = await say(core, BOB, "!notifiche off")
        assert "disattivate" in resp
        set_last_seen(BOB, datetime.utcnow() - timedelta(hours=1))
        await say(core, ALICE, "!msg bob ciao")
        await settle()
        assert sender.sent == [] and pending(BOB) is None
        with db_base.get_session() as s:
            assert s.get(UserPrefs, BOB).notify is False

        assert "disattivate" in await say(core, BOB, "!notifiche")
        assert "attive" in await say(core, BOB, "!notifiche on")
        assert "Uso" in await say(core, BOB, "!notifiche forse")

    async def test_ephemeral_pm_does_not_leak(self, config, users):
        sender = FakeSender(results=[False])
        core, svc, _ = make_core(config, sender=sender)
        await say(core, ALICE, "!msg! bob parola-segreta")
        await settle()
        assert sender.sent == [(BOB, "[BBS] Nuovo PM: !inbox")]
        row = pending(BOB)  # failed: kept, without sender or text
        assert row["last_sender"] is None and row["last_ref"] is None
        assert "alice" not in sender.sent[0][1]
        assert "segreta" not in sender.sent[0][1]

    async def test_deferred_until_advert(self, config, users):
        sender = FakeSender()
        core, svc, _ = make_core(config, sender=sender)
        set_last_seen(BOB, datetime.utcnow() - timedelta(days=2))
        await say(core, ALICE, "!msg bob ci sei?")
        await settle()
        assert sender.sent == []
        assert pending(BOB)["wait_heard"] is True

        # Tick does not call a user that was not heard
        await svc.tick()
        assert sender.sent == []

        # An advert from bob (full key) delivers the notice
        core._on_advert({"public_key": BOB + "00" * 26, "name": "Bob", "type": 1})
        await settle()
        assert sender.sent == [(BOB, "[BBS] Nuovo PM da alice: !inbox")]
        assert pending(BOB) is None

    async def test_failed_send_waits_for_next_message(self, config, users):
        sender = FakeSender(results=[False, True])
        core, svc, _ = make_core(config, sender=sender, clock=Clock())
        await say(core, ALICE, "!msg bob ciao")
        await settle()
        assert len(sender.sent) == 1
        assert pending(BOB)["wait_heard"] is True and pending(BOB)["attempts"] == 1

        svc._clock.advance(minutes=11)
        await svc.tick()
        assert len(sender.sent) == 1  # no blind retries

        await say(core, BOB, "!ping")
        await settle()
        assert len(sender.sent) == 2
        assert pending(BOB) is None

    async def test_failed_send_through_core_queue(self, config, users):
        config.send_delay = 0
        core, svc, conn = make_core(config)
        conn.results = [False]
        await say(core, ALICE, "!msg bob ciao")
        await settle(50)
        assert conn.sent and conn.sent[0][0] == BOB
        assert pending(BOB)["wait_heard"] is True

    async def test_expiry_after_seven_days(self, config, users):
        clock = Clock()
        sender = FakeSender()
        core, svc, _ = make_core(config, sender=sender, clock=clock)
        set_last_seen(BOB, datetime.utcnow() - timedelta(days=2))
        await say(core, ALICE, "!msg bob ciao")
        await settle()
        assert pending(BOB) is not None
        clock.advance(days=8)
        await svc.tick()
        assert pending(BOB) is None
        svc.on_heard(BOB)
        await settle()
        assert sender.sent == []

    async def test_one_row_per_user(self, config, users):
        core, svc, _ = make_core(config, sender=FakeSender())
        set_last_seen(BOB, datetime.utcnow() - timedelta(days=2))
        for i in range(5):
            await say(core, ALICE, f"!msg bob n{i}")
        await settle()
        with db_base.get_session() as s:
            assert s.query(PendingNotification).filter_by(user_key=BOB).count() == 1
        assert pending(BOB)["pm_count"] == 5

    async def test_load_restores_pending_keys(self, config, users):
        core, svc, _ = make_core(config, sender=FakeSender())
        set_last_seen(BOB, datetime.utcnow() - timedelta(days=2))
        await say(core, ALICE, "!msg bob ciao")
        await settle()
        svc2 = NotificationService(send=FakeSender())
        svc2.load()
        assert BOB in svc2._pending_keys

    def test_notify_event_without_service_is_noop(self):
        notify.set_notification_service(None)
        notify.notify_event(BOB, notify.KIND_PM, sender_key=ALICE)
        assert notify.take_events() == []


class TestRender:

    def _row(self, **kw):
        base = dict(pm_count=0, mail_count=0, reply_count=0, mention_count=0,
                    last_sender=None, last_ref=None)
        base.update(kw)
        return PendingNotification(**base)

    def test_single_pm(self):
        assert render_notice(self._row(pm_count=1, last_sender="x")) == "[BBS] Nuovo PM da x: !inbox"

    def test_plural_parts(self):
        text = render_notice(self._row(pm_count=2, reply_count=1, mention_count=3))
        assert text == "[BBS] 6 novità (2 PM, 1 risposta, 3 menzioni): !inbox"

    def test_byte_limit(self):
        long = "é" * 40
        text = render_notice(self._row(mail_count=1, last_sender=long), prefix="[" + "ü" * 60 + "]")
        assert len(text.encode("utf-8")) <= 140
        text.encode("utf-8").decode("utf-8")


class TestCoreLifecycle:

    async def test_start_registers_and_stop_unregisters(self, config, db_session):
        conn = AckConnection()
        core = BBSCore(config=config, connection=conn)
        await core.start()
        try:
            assert notify.get_notification_service() is core.notifications
            assert conn._advert_callback is not None
            assert core._bulletin_task is not None
        finally:
            await core.stop()
        assert notify.get_notification_service() is None
        assert conn._advert_callback is None
