"""
Regression tests for the October 2026 command audit fixes.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import time
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from bbs.commands.base import BaseCommand, CommandRegistry, CommandResult
from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.activity_log import ActivityLog
from bbs.models.area import Area
from bbs.models.message import Message
from bbs.models.private_message import PrivateMessage
from bbs.models.user import User
from bbs.rate_limiter import RateLimiter

ROOT = Path(__file__).parent.parent

ALICE = "a1" * 32
BOB = "b2" * 32
CARL = "c3" * 32
MOD = "d4" * 32
ADMIN = "e5" * 32


@pytest.fixture
def users(db_session: Session):
    """Alice, Bob, Carl (plain), Mod (moderator), Root (admin)."""
    db_session.add_all([
        User(public_key=ALICE, nickname="Alice"),
        User(public_key=BOB, nickname="Bob"),
        User(public_key=CARL, nickname="Carl"),
        User(public_key=MOD, nickname="Moddy", is_moderator=True),
        User(public_key=ADMIN, nickname="Root", is_admin=True),
    ])
    db_session.commit()


@pytest.fixture
def dispatcher(db_session: Session, users):
    return CommandDispatcher(session=db_session)


def _user(session, key) -> User:
    return session.query(User).filter_by(public_key=key).one()


def _area(session, name) -> Area:
    return session.query(Area).filter_by(name=name).one()


def _add_msg(session, area, sender, body, parent_id=None) -> Message:
    m = Message(area_id=area.id, sender_key=sender, body=body, parent_id=parent_id)
    session.add(m)
    area.message_count = (area.message_count or 0) + 1
    session.commit()
    return m


# ---------------------------------------------------------------------------
# 1. !mail
# ---------------------------------------------------------------------------

class TestMail:

    @pytest.mark.asyncio
    async def test_mail_send_works(self, dispatcher, db_session):
        resp = await dispatcher.dispatch("!mail Bob Riunione | domani alle 10", ALICE)
        assert "Mail inviata a Bob" in resp
        pm = db_session.query(PrivateMessage).filter_by(recipient_key=BOB).one()
        assert pm.body.startswith("[MAIL:Riunione]")

    def test_mail_name_not_shadowed_by_inbox_alias(self):
        assert CommandRegistry.get("mail").name == "mail"
        from bbs.commands.inbox_cmd import InboxCommand
        assert "mail" not in InboxCommand.aliases

    @pytest.mark.asyncio
    async def test_mail_muted_sender_rejected(self, dispatcher, db_session):
        _user(db_session, ALICE).is_muted = True
        db_session.commit()
        resp = await dispatcher.dispatch("!mail Bob Ciao | test", ALICE)
        assert "Non puoi inviare" in resp
        assert db_session.query(PrivateMessage).count() == 0

    @pytest.mark.asyncio
    async def test_mail_to_banned_rejected(self, dispatcher, db_session):
        _user(db_session, BOB).is_banned = True
        db_session.commit()
        resp = await dispatcher.dispatch("!mail Bob Ciao | test", ALICE)
        assert "Impossibile" in resp
        assert db_session.query(PrivateMessage).count() == 0

    @pytest.mark.asyncio
    async def test_mail_too_long_rejected(self, dispatcher, db_session):
        resp = await dispatcher.dispatch("!mail Bob Ogg | " + "x" * 300, ALICE)
        assert "troppo lunga" in resp
        assert db_session.query(PrivateMessage).count() == 0

    @pytest.mark.asyncio
    async def test_readmail_output_bounded(self, dispatcher, db_session):
        pm = PrivateMessage(
            sender_key=ALICE, recipient_key=BOB, body="[MAIL:Ogg]\n" + "y" * 2000
        )
        db_session.add(pm)
        db_session.commit()
        resp = await dispatcher.dispatch(f"!readmail {pm.id}", BOB)
        assert "Mail #" in resp
        assert len(resp) < 500


# ---------------------------------------------------------------------------
# 2. !delarea / dispatcher rollback
# ---------------------------------------------------------------------------

class TestDelArea:

    @pytest.mark.asyncio
    async def test_delarea_with_messages_and_replies(self, dispatcher, db_session):
        area = Area(name="temp")
        db_session.add(area)
        db_session.commit()
        parent = _add_msg(db_session, area, ALICE, "root")
        _add_msg(db_session, area, BOB, "reply", parent_id=parent.id)
        area_id = area.id

        resp = await dispatcher.dispatch("!delarea temp", ADMIN)
        assert "eliminata" in resp
        db_session.expire_all()
        assert db_session.query(Area).filter_by(name="temp").first() is None
        assert db_session.query(Message).filter_by(area_id=area_id).count() == 0

    @pytest.mark.asyncio
    async def test_protected_area_checked_on_real_name(self, dispatcher, db_session):
        resp = await dispatcher.dispatch("!delarea #GENERALE", ADMIN)
        assert "protetta" in resp
        assert db_session.query(Area).filter_by(name="generale").first() is not None

    @pytest.mark.asyncio
    async def test_default_area_is_protected(self, dispatcher, db_session, config):
        config.default_area = "tech"
        resp = await dispatcher.dispatch("!delarea tech", ADMIN)
        assert "protetta" in resp

    @pytest.mark.asyncio
    async def test_dispatcher_rolls_back_on_error(self, dispatcher, db_session):
        class BoomCommand(BaseCommand):
            name = "boomtest"
            description = "test"
            usage = "!boomtest"

            def __init__(self, session):
                self.session = session

            async def execute(self, ctx, args):
                # Violates NOT NULL on messages.area_id -> IntegrityError
                self.session.add(Message(sender_key=ctx.sender_key, body="x"))
                self.session.flush()
                return CommandResult.ok("never")

        CommandRegistry.register(BoomCommand)
        try:
            resp = await dispatcher.dispatch("!boomtest", ALICE)
        finally:
            CommandRegistry._commands.pop("boomtest", None)
        assert "Errore interno" in resp
        # Session still usable (no PendingRollbackError)
        assert db_session.query(User).count() == 5


# ---------------------------------------------------------------------------
# 3. Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:

    @pytest.mark.asyncio
    async def test_admin_whitelist_not_sticky(self, db_session, users):
        limiter = RateLimiter(min_interval=5.0)
        d = CommandDispatcher(db_session, rate_limiter=limiter)
        await d.dispatch("!help", ADMIN)
        await d.dispatch("!help", ADMIN)
        assert ADMIN not in limiter._whitelist

        # Demoted: must be rate limited again
        _user(db_session, ADMIN).is_admin = False
        db_session.commit()
        await d.dispatch("!help", ADMIN)
        resp = await d.dispatch("!help", ADMIN)
        assert "Troppo veloce" in resp

    @pytest.mark.asyncio
    async def test_failing_commands_are_recorded(self, db_session, users):
        limiter = RateLimiter(min_interval=5.0)
        d = CommandDispatcher(db_session, rate_limiter=limiter)
        resp = await d.dispatch("!read 999999", ALICE)
        assert "non trovato" in resp
        resp = await d.dispatch("!help", ALICE)
        assert "Troppo veloce" in resp

    @pytest.mark.asyncio
    async def test_unknown_commands_are_recorded(self, db_session, users):
        limiter = RateLimiter(min_interval=5.0)
        d = CommandDispatcher(db_session, rate_limiter=limiter)
        await d.dispatch("!nonexistentcmd", ALICE)
        resp = await d.dispatch("!help", ALICE)
        assert "Troppo veloce" in resp

    @pytest.mark.asyncio
    async def test_no_rate_limiter(self, db_session, users):
        d = CommandDispatcher(db_session, rate_limiter=None)
        for _ in range(3):
            assert "Comandi" in await d.dispatch("!help", ALICE)


# ---------------------------------------------------------------------------
# 4. Activity log redaction
# ---------------------------------------------------------------------------

class TestActivityLogRedaction:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("command", [
        "!msg Bob segretissimo123",
        "!msg! Bob segretissimo123",
        "!mail Bob Oggetto | segretissimo123",
        "!pm Bob segretissimo123",
    ])
    async def test_private_bodies_not_logged(self, dispatcher, db_session, command):
        await dispatcher.dispatch(command, ALICE)
        db_session.flush()
        logs = [a.details or "" for a in db_session.query(ActivityLog).all()]
        cmd_logs = [d for d in logs if d.startswith("!")]
        assert cmd_logs, "command should still be logged"
        assert all("segretissimo123" not in d for d in logs)

    @pytest.mark.asyncio
    async def test_public_commands_still_logged_with_args(self, dispatcher, db_session):
        await dispatcher.dispatch("!search ciao", ALICE)
        db_session.flush()
        logs = [a.details or "" for a in db_session.query(ActivityLog).all()]
        assert any(d.startswith("!search ciao") for d in logs)


# ---------------------------------------------------------------------------
# 5. Hidden / read-only areas
# ---------------------------------------------------------------------------

@pytest.fixture
def hidden(db_session, users):
    area = Area(name="segreta", is_public=False)
    db_session.add(area)
    db_session.commit()
    msg = _add_msg(db_session, area, ADMIN, "parolasegreta nascosta")
    return area, msg


class TestHiddenAreas:

    @pytest.mark.asyncio
    async def test_read_hidden_denied_to_users(self, dispatcher, hidden):
        _, msg = hidden
        resp = await dispatcher.dispatch(f"!read {msg.id}", ALICE)
        assert "non trovato" in resp
        assert "parolasegreta" not in resp

    @pytest.mark.asyncio
    async def test_read_hidden_allowed_to_admin(self, dispatcher, hidden):
        _, msg = hidden
        resp = await dispatcher.dispatch(f"!read {msg.id}", ADMIN)
        assert "parolasegreta" in resp

    @pytest.mark.asyncio
    async def test_search_excludes_hidden(self, dispatcher, hidden):
        resp = await dispatcher.dispatch("!search parolasegreta", ALICE)
        assert "Nessun risultato" in resp
        resp = await dispatcher.dispatch("!search #segreta parolasegreta", ALICE)
        assert "non trovata" in resp
        resp = await dispatcher.dispatch("!search parolasegreta", ADMIN)
        assert "1 risultati" in resp

    @pytest.mark.asyncio
    async def test_post_hidden_denied(self, dispatcher, db_session, hidden):
        area, _ = hidden
        resp = await dispatcher.dispatch("!post #segreta ciao", ALICE)
        assert "non trovata" in resp
        assert "segreta" not in resp.split("\n", 1)[-1]  # not in "available"
        assert db_session.query(Message).filter_by(area_id=area.id).count() == 1

    @pytest.mark.asyncio
    async def test_reply_hidden_denied(self, dispatcher, db_session, hidden):
        area, msg = hidden
        resp = await dispatcher.dispatch(f"!reply {msg.id} ciao", ALICE)
        assert "non trovato" in resp
        assert db_session.query(Message).filter_by(area_id=area.id).count() == 1

    @pytest.mark.asyncio
    async def test_reply_readonly_area_denied(self, dispatcher, db_session, users):
        area = Area(name="annunci", is_readonly=True)
        db_session.add(area)
        db_session.commit()
        msg = _add_msg(db_session, area, ADMIN, "annuncio")
        resp = await dispatcher.dispatch(f"!reply {msg.id} ciao", ALICE)
        assert "sola lettura" in resp
        assert db_session.query(Message).filter_by(area_id=area.id).count() == 1

    @pytest.mark.asyncio
    async def test_areas_list_hides_hidden(self, dispatcher, hidden):
        resp = await dispatcher.dispatch("!areas", ALICE)
        assert "segreta" not in resp

    @pytest.mark.asyncio
    async def test_board_post_muted_denied(self, dispatcher, db_session, users):
        _user(db_session, ALICE).is_muted = True
        db_session.commit()
        resp = await dispatcher.dispatch("!board post annuncio spam", ALICE)
        assert "Non puoi" in resp
        assert db_session.query(Message).filter_by(body="annuncio spam").count() == 0

    @pytest.mark.asyncio
    async def test_board_post_readonly_denied(self, dispatcher, db_session, users):
        db_session.add(Area(name="bacheca", is_readonly=True))
        db_session.commit()
        resp = await dispatcher.dispatch("!board post annuncio", ALICE)
        assert "sola lettura" in resp
        assert db_session.query(Message).filter_by(body="annuncio").count() == 0


# ---------------------------------------------------------------------------
# 6. Inbox ephemeral PMs / allow_ephemeral_pm
# ---------------------------------------------------------------------------

class TestInboxEphemeral:

    @pytest.fixture(autouse=True)
    def _clean_ephemeral(self):
        from bbs.commands import msg_cmd
        msg_cmd._ephemeral_messages.clear()
        yield
        msg_cmd._ephemeral_messages.clear()

    @pytest.mark.asyncio
    async def test_ephemeral_shown_in_full(self, dispatcher):
        from bbs.commands.msg_cmd import add_ephemeral_message
        text = "inizio " + "z" * 150 + " FINE"
        add_ephemeral_message(BOB, ALICE, "Alice", text)
        resp = await dispatcher.dispatch("!inbox", BOB)
        assert text in resp

    @pytest.mark.asyncio
    async def test_ephemeral_not_shown_are_kept(self, dispatcher):
        from bbs.commands.msg_cmd import add_ephemeral_message
        for i in range(5):
            add_ephemeral_message(BOB, ALICE, "Alice", f"effimero-{i}")
        first = await dispatcher.dispatch("!inbox", BOB)
        second = await dispatcher.dispatch("!inbox", BOB)
        for i in range(5):
            assert f"effimero-{i}" in first + second
        assert "effimero-4" not in first
        third = await dispatcher.dispatch("!inbox", BOB)
        assert "effimero" not in third

    @pytest.mark.asyncio
    async def test_ephemeral_disabled_by_config(self, dispatcher, config):
        from bbs.commands import msg_cmd
        config.allow_ephemeral_pm = False
        resp = await dispatcher.dispatch("!msg! Bob ciao", ALICE)
        assert "disabilitati" in resp
        assert BOB not in msg_cmd._ephemeral_messages
        resp = await dispatcher.dispatch("!pm! Bob ciao", ALICE)
        assert "disabilitati" in resp


# ---------------------------------------------------------------------------
# 7. '/' prefix in user-facing hints
# ---------------------------------------------------------------------------

def test_privacy_hints_use_bang_prefix():
    from bbs.privacy import PrivacyInfo
    texts = PrivacyInfo.get_privacy_notice() + PrivacyInfo.get_gdpr_info(30, 30, False)
    for cmd in ("msg!", "gdpr", "delpm"):
        assert f"/{cmd}" not in texts
    assert "!msg!" in texts and "!gdpr" in texts and "!delpm" in texts


# ---------------------------------------------------------------------------
# 8. !news does not block the loop
# ---------------------------------------------------------------------------

class TestNews:

    def test_feedparser_in_requirements(self):
        for req in ("requirements.txt", "requirements-light.txt"):
            assert "feedparser" in (ROOT / req).read_text()

    @pytest.mark.asyncio
    async def test_news_fetch_off_loop_with_timeout(self, dispatcher, monkeypatch):
        from bbs.commands import news_cmd

        def slow_fetch(feed_name):
            time.sleep(1.5)
            return [("t", "s")]

        monkeypatch.setattr(news_cmd, "FEEDPARSER_AVAILABLE", True)
        monkeypatch.setattr(news_cmd, "_fetch_news", slow_fetch)
        monkeypatch.setattr(news_cmd, "FETCH_TIMEOUT", 0.3)

        ticks = 0

        async def ticker():
            nonlocal ticks
            for _ in range(5):
                await asyncio.sleep(0.02)
                ticks += 1

        start = time.monotonic()
        resp, _ = await asyncio.gather(dispatcher.dispatch("!news", ALICE), ticker())
        elapsed = time.monotonic() - start
        assert "non disponibili" in resp
        assert elapsed < 1.2
        assert ticks == 5

    def test_news_summary_cleaned_and_bounded(self):
        from bbs.commands.news_cmd import _clean_summary, MAX_SUMMARY_LEN
        out = _clean_summary("<p>Ciao &amp; " + "w" * 1000 + "</p>")
        assert "<p>" not in out and "&amp;" not in out
        assert len(out) <= MAX_SUMMARY_LEN


# ---------------------------------------------------------------------------
# 9. Unicode digits / huge numbers
# ---------------------------------------------------------------------------

class TestNumericParsing:

    def test_parse_int(self):
        from bbs.commands.helpers import parse_int
        assert parse_int("42") == 42
        assert parse_int("#42", strip_hash=True) == 42
        assert parse_int("²") is None
        assert parse_int("٣") is None
        assert parse_int("-1") is None
        assert parse_int("9" * 40) is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("command", [
        "!delete ²", "!readmail ²", "!delmail ²", "!board read ²", "!board del ²",
        "!search ciao ²", "!news ²", "!read ²", "!reply ² ciao",
        "!read 99999999999999999999999999", "!delete 99999999999999999999999",
    ])
    async def test_no_internal_error(self, dispatcher, command):
        resp = await dispatcher.dispatch(command, ALICE)
        assert "Errore interno" not in resp

    @pytest.mark.asyncio
    async def test_kick_unicode_digit(self, dispatcher, db_session):
        resp = await dispatcher.dispatch("!kick Carl ²", ADMIN)
        assert "Errore interno" not in resp


# ---------------------------------------------------------------------------
# 10. Small fixes
# ---------------------------------------------------------------------------

class TestSmallFixes:

    @pytest.mark.asyncio
    async def test_delete_decrements_message_count(self, dispatcher, db_session):
        area = _area(db_session, "tech")
        before = area.message_count
        msg = _add_msg(db_session, area, ALICE, "da cancellare")
        assert area.message_count == before + 1
        resp = await dispatcher.dispatch(f"!delete {msg.id}", ALICE)
        assert "eliminato" in resp
        db_session.refresh(area)
        assert area.message_count == before

    @pytest.mark.asyncio
    async def test_kick_zero_rejected(self, dispatcher, db_session):
        resp = await dispatcher.dispatch("!kick Carl 0", ADMIN)
        assert "Uso: !kick" in resp
        db_session.refresh(_user(db_session, CARL))
        assert not _user(db_session, CARL).is_kicked

    @pytest.mark.asyncio
    async def test_read_truncation_includes_reply_suffix(self, dispatcher, db_session):
        from bbs.commands.read_cmd import ReadCommand
        area = _area(db_session, "tech")
        msg = _add_msg(db_session, area, ALICE, "q" * 400)
        for i in range(3):
            _add_msg(db_session, area, BOB, f"r{i}", parent_id=msg.id)
        resp = await dispatcher.dispatch(f"!read {msg.id}", ALICE)
        assert resp.endswith("[3 risp]")
        assert "..." in resp
        assert len(resp) <= ReadCommand.MAX_RESPONSE_LENGTH

    @pytest.mark.asyncio
    async def test_meteo_zero_coordinates_are_valid(self, dispatcher, config, monkeypatch):
        from bbs.commands import meteo_cmd
        config.latitude = 0.0
        config.longitude = 0.0
        seen = {}

        def fake_fetch(lat, lon):
            seen["coords"] = (lat, lon)
            return {"current": {"temperature_2m": 30}, "daily": {}}

        monkeypatch.setattr(meteo_cmd, "_fetch_meteo", fake_fetch)
        resp = await dispatcher.dispatch("!meteo", ALICE)
        assert "non configurata" not in resp
        assert seen["coords"] == (0.0, 0.0)

    @pytest.mark.asyncio
    async def test_meteo_unconfigured(self, dispatcher, config):
        config.latitude = None
        config.longitude = None
        resp = await dispatcher.dispatch("!meteo", ALICE)
        assert "non configurata" in resp

    @pytest.mark.asyncio
    async def test_help_lists_everything_bounded(self, dispatcher):
        resp = await dispatcher.dispatch("!help", ALICE)
        assert "Comandi" in resp and "tutti" in resp
        assert len(resp) <= 250

        all_resp = await dispatcher.dispatch("!help tutti", ALICE)
        for cmd in ("post", "trivia", "news", "meteo", "board", "mail", "search", "reply"):
            assert cmd in all_resp
        assert "ban" not in all_resp.split()  # admin-only hidden from users
        assert len(all_resp) <= 600

        forum = await dispatcher.dispatch("!help forum", ALICE)
        assert "!reply" in forum and "!search" in forum

        mod = await dispatcher.dispatch("!help mod", MOD)
        assert "!kick" in mod and "!ban" not in mod

        detail = await dispatcher.dispatch("!help kick", MOD)
        assert "Uso:" in detail

    def test_trivia_answers_balanced(self):
        from collections import Counter
        from bbs.commands.trivia_cmd import QUESTIONS, _get_question
        counts = Counter(_get_question(i)[3] for i in range(len(QUESTIONS)))
        n = len(QUESTIONS)
        for letter in ("A", "B", "C"):
            assert counts[letter] >= n // 4, counts
        for i in range(n):
            _, _, opts, correct = _get_question(i)
            orig = QUESTIONS[i]
            assert opts[correct] == orig[2][orig[3]]
            assert sorted(opts.values()) == sorted(orig[2].values())

    @pytest.mark.asyncio
    async def test_trivia_answer_uses_shuffled_letter(self, dispatcher):
        from bbs.commands import trivia_cmd
        trivia_cmd._active_questions.pop(ALICE, None)
        await dispatcher.dispatch("!trivia", ALICE)
        q_idx, correct, _ = trivia_cmd._active_questions[ALICE]
        assert correct == trivia_cmd._get_question(q_idx)[3]
        resp = await dispatcher.dispatch(f"!trivia {correct}", ALICE)
        assert "Corretto" in resp


# ---------------------------------------------------------------------------
# 11. Moderator permissions
# ---------------------------------------------------------------------------

class TestModerators:

    @pytest.mark.asyncio
    async def test_moderator_can_kick_and_mute(self, dispatcher, db_session):
        resp = await dispatcher.dispatch("!kick Carl 10 spam", MOD)
        assert "espulso" in resp
        resp = await dispatcher.dispatch("!mute Bob", MOD)
        assert "silenziato" in resp
        resp = await dispatcher.dispatch("!unmute Bob", MOD)
        assert "nuovamente" in resp

    @pytest.mark.asyncio
    async def test_moderator_can_delete_others_messages(self, dispatcher, db_session):
        area = _area(db_session, "tech")
        msg = _add_msg(db_session, area, ALICE, "offtopic")
        resp = await dispatcher.dispatch(f"!delete {msg.id}", MOD)
        assert "eliminato" in resp

    @pytest.mark.asyncio
    async def test_plain_user_cannot_delete_others(self, dispatcher, db_session):
        area = _area(db_session, "tech")
        msg = _add_msg(db_session, area, ALICE, "mio")
        resp = await dispatcher.dispatch(f"!delete {msg.id}", BOB)
        assert "Solo" in resp

    @pytest.mark.asyncio
    @pytest.mark.parametrize("command", [
        "!ban Carl", "!promote Carl", "!newarea nuova", "!delarea tech",
    ])
    async def test_moderator_cannot_use_admin_commands(self, dispatcher, command):
        resp = await dispatcher.dispatch(command, MOD)
        assert "Permesso negato" in resp

    @pytest.mark.asyncio
    async def test_plain_user_cannot_kick(self, dispatcher):
        resp = await dispatcher.dispatch("!kick Carl 10", ALICE)
        assert "Permesso negato" in resp

    @pytest.mark.asyncio
    async def test_moderator_cannot_kick_moderator(self, dispatcher, db_session):
        _user(db_session, CARL).is_moderator = True
        db_session.commit()
        resp = await dispatcher.dispatch("!kick Carl 10", MOD)
        assert "moderatore" in resp
        resp = await dispatcher.dispatch("!mute Carl", MOD)
        assert "moderatore" in resp


# ---------------------------------------------------------------------------
# 11. Follow-up fixes: !list hidden default area, !delpm parsing, registry
# ---------------------------------------------------------------------------

class TestListHiddenDefaultArea:

    @pytest.mark.asyncio
    async def test_hidden_default_area_not_listed_to_users(
        self, dispatcher, db_session, config
    ):
        area = _area(db_session, config.default_area)
        _add_msg(db_session, area, ADMIN, "parolasegreta")
        area.is_public = False
        db_session.commit()

        resp = await dispatcher.dispatch("!list", ALICE)
        assert "parolasegreta" not in resp

        resp = await dispatcher.dispatch("!list", ADMIN)
        assert "parolasegreta" in resp

    @pytest.mark.asyncio
    @pytest.mark.parametrize("arg", ["²", "-3", "abc"])
    async def test_list_rejects_invalid_count(self, dispatcher, arg):
        resp = await dispatcher.dispatch(f"!list {arg}", ALICE)
        assert "Uso" in resp


class TestDelPmParsing:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("arg", ["²", "٣", "9" * 40, "abc"])
    async def test_delpm_invalid_id(self, dispatcher, arg):
        resp = await dispatcher.dispatch(f"!delpm {arg}", ALICE)
        assert "ID non valido" in resp

    @pytest.mark.asyncio
    async def test_delpm_hash_prefix(self, dispatcher, db_session):
        pm = PrivateMessage(sender_key=BOB, recipient_key=ALICE, body="ciao")
        db_session.add(pm)
        db_session.commit()
        resp = await dispatcher.dispatch(f"!delpm #{pm.id}", ALICE)
        assert "non valido" not in resp
        assert "non trovato" not in resp


def test_msg_docstring_uses_bang_prefix():
    from bbs.commands import msg_cmd
    assert "/msg" not in (msg_cmd.__doc__ or "")


class TestRegistryRecovery:

    @pytest.mark.asyncio
    async def test_dispatcher_reregisters_builtins_after_clear(self, db_session, users):
        CommandRegistry.clear()
        dispatcher = CommandDispatcher(session=db_session)
        resp = await dispatcher.dispatch("!help", ALICE)
        assert "sconosciuto" not in resp.lower()
        # aliases come back too
        assert CommandRegistry.get("pm") is CommandRegistry.get("msg")

    def test_unregister_only_removes_matching_class(self):
        class Shadow(BaseCommand):
            name = "help"
            aliases = ["shadowalias"]

            async def execute(self, ctx, args):
                return CommandResult.ok("shadow")

        builtin = CommandRegistry.get("help")
        assert CommandRegistry.unregister(Shadow) is False
        assert CommandRegistry.get("help") is builtin

        CommandRegistry.register(Shadow)
        assert CommandRegistry.get("help") is Shadow
        assert CommandRegistry.unregister(Shadow) is True
        assert CommandRegistry.get("shadowalias") is None
        CommandRegistry.ensure_builtins()
        assert CommandRegistry.get("help") is builtin
