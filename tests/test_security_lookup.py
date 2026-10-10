"""
Security regression tests for user/area lookups (audit ottobre 2026).

Covers:
- LIKE wildcard abuse ('_' and '%') in nickname / area / key-prefix lookups
- ambiguous public key prefixes
- impersonation via nicknames that look like a key prefix
- mention parsing/resolution and inbox hint prefix

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from sqlalchemy.orm import Session

import bbs.mentions
from bbs.commands.dispatcher import CommandDispatcher
from bbs.mentions import (
    MENTION_PATTERN,
    Mention,
    format_mentions_for_inbox,
    get_mention_notifier,
    process_mentions_in_message,
)
from bbs.models.area import Area
from bbs.models.message import Message
from bbs.models.private_message import PrivateMessage
from bbs.models.user import User
from bbs.repositories.area_repository import AreaRepository
from bbs.repositories.message_repository import MessageRepository
from bbs.repositories.user_repository import NicknameError, UserRepository

KEY_A = "A" * 64  # mario_1
KEY_B = "B" * 64  # no nickname, displayed as BBBBBBBB
KEY_C = "C" * 64  # sender
KEY_EVIL = "D" * 64  # older account, attacker


@pytest.fixture(autouse=True)
def reset_notifier():
    bbs.mentions._mention_notifier = None
    yield
    bbs.mentions._mention_notifier = None


def _pms_to(session: Session, key: str):
    return session.query(PrivateMessage).filter_by(recipient_key=key).all()


@pytest.fixture
def mario_users(db_session: Session):
    """Attacker 'marioX1' is older (lower id) than the real 'mario_1'."""
    db_session.add(User(public_key=KEY_EVIL, nickname="marioX1"))
    db_session.add(User(public_key=KEY_A, nickname="mario_1"))
    db_session.add(User(public_key=KEY_C, nickname="sender"))
    db_session.commit()


# --------------------------------------------------------------------------
# 1. LIKE wildcards
# --------------------------------------------------------------------------


class TestNicknameWildcards:
    def test_get_by_nickname_underscore_is_literal(self, db_session, mario_users):
        user = UserRepository(db_session).get_by_nickname("mario_1")
        assert user is not None
        assert user.public_key == KEY_A

    def test_get_by_nickname_percent_matches_nothing(self, db_session, mario_users):
        repo = UserRepository(db_session)
        assert repo.get_by_nickname("%") is None
        assert repo.get_by_nickname("mario%") is None
        assert repo.get_by_nickname("_______") is None

    def test_get_by_nickname_case_insensitive(self, db_session, mario_users):
        user = UserRepository(db_session).get_by_nickname("MARIO_1")
        assert user is not None and user.public_key == KEY_A

    @pytest.mark.asyncio
    async def test_msg_underscore_goes_to_right_user(self, db_session, mario_users):
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!msg mario_1 segreto", KEY_C)
        assert "inviato" in response.lower()
        db_session.expire_all()
        assert _pms_to(db_session, KEY_EVIL) == []
        assert len(_pms_to(db_session, KEY_A)) == 1

    @pytest.mark.asyncio
    async def test_ephemeral_msg_underscore_goes_to_right_user(
        self, db_session, mario_users
    ):
        from bbs.commands.msg_cmd import _ephemeral_messages

        _ephemeral_messages.clear()
        dispatcher = CommandDispatcher(session=db_session)
        await dispatcher.dispatch("!msg! mario_1 segreto", KEY_C)
        assert KEY_EVIL not in _ephemeral_messages
        assert KEY_A in _ephemeral_messages
        _ephemeral_messages.clear()

    @pytest.mark.asyncio
    async def test_msg_wildcard_key_prefix_not_found(self, db_session, mario_users):
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!msg ________ ciao", KEY_C)
        assert "non trovato" in response.lower()
        db_session.expire_all()
        assert db_session.query(PrivateMessage).count() == 0

    @pytest.mark.asyncio
    async def test_msg_percent_key_prefix_not_found(self, db_session, mario_users):
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!msg %%%%%%%% ciao", KEY_C)
        assert "non trovato" in response.lower()
        db_session.expire_all()
        assert db_session.query(PrivateMessage).count() == 0

    @pytest.mark.asyncio
    async def test_whois_underscore_is_literal(self, db_session, mario_users):
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!whois mario_1", KEY_C)
        assert "mario_1" in response
        assert "marioX1" not in response

    def test_find_user_underscore_is_literal(self, db_session, mario_users):
        # find_user is also used by admin moderation commands (ban/kick/mute)
        user = UserRepository(db_session).find_user("mario_1")
        assert user is not None and user.public_key == KEY_A


class TestAreaWildcards:
    @pytest.fixture
    def areas(self, db_session):
        # "generale" is seeded by init_database (protected default area)
        for name, public in (("generale", True), ("segreta", False)):
            if not db_session.query(Area).filter_by(name=name).first():
                db_session.add(Area(name=name, is_public=public))
        db_session.commit()

    def test_area_get_by_name_percent(self, db_session, areas):
        repo = AreaRepository(db_session)
        assert repo.get_by_name("gen%") is None
        assert repo.get_by_name("%") is None

    def test_area_get_by_name_underscore(self, db_session, areas):
        assert AreaRepository(db_session).get_by_name("s_greta") is None

    def test_area_get_by_name_exact_case_insensitive(self, db_session, areas):
        area = AreaRepository(db_session).get_by_name("GENERALE")
        assert area is not None and area.name == "generale"

    def test_delete_area_wildcard_does_not_delete(self, db_session, areas):
        repo = AreaRepository(db_session)
        assert repo.delete_area("gen%") is False
        db_session.expire_all()
        assert db_session.query(Area).filter_by(name="generale").count() == 1

    @pytest.mark.asyncio
    async def test_post_wildcard_area_does_not_post_in_private(
        self, db_session, areas
    ):
        db_session.add(User(public_key=KEY_C, nickname="sender"))
        db_session.commit()
        dispatcher = CommandDispatcher(session=db_session)
        await dispatcher.dispatch("!post #s_greta ciao2", KEY_C)
        db_session.expire_all()
        segreta = db_session.query(Area).filter_by(name="segreta").one()
        assert db_session.query(Message).filter_by(area_id=segreta.id).count() == 0

    def test_message_repository_area_filters_are_exact(self, db_session, areas):
        db_session.add(User(public_key=KEY_C, nickname="sender"))
        db_session.commit()
        repo = MessageRepository(db_session)
        msg = repo.create_message(
            area_name="segreta", sender_key=KEY_C, body="riservato"
        )
        assert msg is not None
        db_session.commit()
        assert repo.get_recent_messages("s_greta") == []
        assert repo.get_recent_messages("%") == []
        assert repo.count_by_area("s_greta") == 0
        assert repo.count_by_area("segreta") == 1
        assert repo.search_messages("riservato", area_name="s_greta") == []
        assert repo.create_message(
            area_name="s_greta", sender_key=KEY_C, body="x"
        ) is None

    def test_search_wildcards_are_literal(self, db_session, areas):
        db_session.add(User(public_key=KEY_C, nickname="sender"))
        db_session.commit()
        repo = MessageRepository(db_session)
        repo.create_message(area_name="generale", sender_key=KEY_C, body="ciao")
        repo.create_message(area_name="generale", sender_key=KEY_C, body="sconto 50%")
        db_session.commit()
        assert len(repo.search_messages("%")) == 1
        assert len(repo.search_messages("_")) == 0
        assert len(repo.search_messages("CIAO")) == 1


# --------------------------------------------------------------------------
# Key prefix ambiguity
# --------------------------------------------------------------------------


class TestKeyPrefixAmbiguity:
    @pytest.fixture
    def twins(self, db_session):
        db_session.add(User(public_key="abcdef12" + "1" * 56))
        db_session.add(User(public_key="abcdef12" + "2" * 56))
        db_session.add(User(public_key=KEY_C, nickname="sender"))
        db_session.commit()

    @pytest.mark.asyncio
    async def test_msg_ambiguous_prefix_refused(self, db_session, twins):
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!msg abcdef12 ciao", KEY_C)
        assert "ambiguo" in response.lower()
        assert "piu lungo" in response.lower()
        db_session.expire_all()
        assert db_session.query(PrivateMessage).count() == 0

    @pytest.mark.asyncio
    async def test_msg_longer_prefix_works(self, db_session, twins):
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!msg ABCDEF122 ciao", KEY_C)
        assert "inviato" in response.lower()
        db_session.expire_all()
        pm = db_session.query(PrivateMessage).one()
        assert pm.recipient_key == "abcdef12" + "2" * 56

    def test_find_user_ambiguous_returns_none(self, db_session, twins):
        repo = UserRepository(db_session)
        assert repo.find_user("abcdef12") is None
        user, error = repo.resolve_user("abcdef12")
        assert user is None and "ambiguo" in error.lower()


# --------------------------------------------------------------------------
# 2. Impersonation
# --------------------------------------------------------------------------


class TestImpersonation:
    @pytest.fixture
    def users(self, db_session):
        db_session.add(User(public_key=KEY_EVIL, nickname="early"))
        db_session.add(User(public_key=KEY_A, nickname="mario"))
        db_session.add(User(public_key=KEY_B))  # shown as BBBBBBBB
        db_session.commit()

    @pytest.mark.asyncio
    async def test_nick_equal_to_key_prefix_rejected(self, db_session, users):
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!nick BBBBBBBB", KEY_EVIL)
        assert "non valido" in response.lower()
        db_session.expire_all()
        assert db_session.query(User).filter_by(public_key=KEY_EVIL).one().nickname == "early"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("nick", ["abcdef", "DEADBEEF", "0123456789"])
    async def test_hex_nick_rejected(self, db_session, users, nick):
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!nick {nick}", KEY_EVIL)
        assert "non valido" in response.lower()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("nick", ["abcde", "cafe-bar", "beefy1"])
    async def test_non_hex_or_short_nick_allowed(self, db_session, users, nick):
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!nick {nick}", KEY_EVIL)
        assert "impostato" in response.lower()

    @pytest.mark.asyncio
    async def test_nick_case_insensitive_duplicate_rejected(self, db_session, users):
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!nick MARIO", KEY_EVIL)
        assert "gia in uso" in response.lower()

    @pytest.mark.asyncio
    async def test_nick_change_own_case_allowed(self, db_session, users):
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!nick Mario", KEY_A)
        assert "impostato" in response.lower()

    def test_repo_set_nickname_enforces_uniqueness(self, db_session, users):
        repo = UserRepository(db_session)
        with pytest.raises(NicknameError):
            repo.set_nickname(KEY_EVIL, "MaRiO")

    def test_repo_set_nickname_rejects_hex(self, db_session, users):
        repo = UserRepository(db_session)
        with pytest.raises(NicknameError):
            repo.set_nickname(KEY_EVIL, "BBBBBBBB")

    @pytest.mark.asyncio
    async def test_legacy_hex_nick_does_not_hijack_key_prefix(self, db_session, users):
        """A pre-existing nick equal to someone's key prefix loses to the key."""
        evil = db_session.query(User).filter_by(public_key=KEY_EVIL).one()
        evil.nickname = "BBBBBBBB"  # legacy row, set before the fix
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!msg BBBBBBBB ciao", KEY_A)
        assert "inviato" in response.lower()
        db_session.expire_all()
        assert _pms_to(db_session, KEY_EVIL) == []
        assert len(_pms_to(db_session, KEY_B)) == 1

    @pytest.mark.asyncio
    async def test_readpm_reply_hint_routes_to_sender(self, db_session, users):
        """The reply hint must resolve back to the real sender."""
        evil = db_session.query(User).filter_by(public_key=KEY_EVIL).one()
        evil.nickname = "BBBBBBBB"  # legacy hex nick mimicking KEY_B
        db_session.commit()
        pm = PrivateMessage(sender_key=KEY_EVIL, recipient_key=KEY_A, body="ciao")
        db_session.add(pm)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!readpm {pm.id}", KEY_A)
        hint = [l for l in response.splitlines() if l.startswith("Rispondi: !msg ")]
        assert hint
        target = hint[0].split()[2]
        user = UserRepository(db_session).find_user(target)
        assert user is not None and user.public_key == KEY_EVIL

    @pytest.mark.asyncio
    async def test_readpm_reply_hint_uses_nickname(self, db_session, users):
        pm = PrivateMessage(sender_key=KEY_A, recipient_key=KEY_B, body="ciao")
        db_session.add(pm)
        db_session.commit()
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!readpm {pm.id}", KEY_B)
        assert "Rispondi: !msg mario <testo>" in response


# --------------------------------------------------------------------------
# 3. Mentions
# --------------------------------------------------------------------------


class TestMentionsSecurity:
    def test_mention_with_dash(self):
        assert MENTION_PATTERN.findall("ciao @mario-1 come va") == ["mario-1"]

    def test_mention_starting_with_digit(self):
        assert MENTION_PATTERN.findall("ciao @1mario") == ["1mario"]

    def test_mention_email_ignored(self):
        assert MENTION_PATTERN.findall("scrivi a test@example.com") == []

    def test_inbox_hint_uses_bbs_prefix(self):
        text = format_mentions_for_inbox([
            Mention(
                recipient_key=KEY_A,
                sender_key=KEY_C,
                sender_name="sender",
                message_id=7,
                area_name="generale",
                excerpt="x",
            )
        ])
        assert "!read 7" in text
        assert "/read" not in text

    def test_mention_resolution_is_exact(self, db_session, mario_users):
        notified = process_mentions_in_message(
            db_session,
            message_body="ciao @mario_1",
            sender_key=KEY_C,
            sender_name="sender",
            message_id=1,
            area_name="generale",
        )
        assert notified == ["mario_1"]
        notifier = get_mention_notifier()
        assert notifier.get_mention_count(KEY_A) == 1
        assert notifier.get_mention_count(KEY_EVIL) == 0

    def test_mention_wildcard_matches_nobody(self, db_session, mario_users):
        notified = process_mentions_in_message(
            db_session,
            message_body="ciao @mario__",
            sender_key=KEY_C,
            sender_name="sender",
            message_id=1,
            area_name="generale",
        )
        assert notified == []

    def test_mention_dash_nick_notified(self, db_session):
        db_session.add(User(public_key=KEY_A, nickname="mario-1"))
        db_session.commit()
        notified = process_mentions_in_message(
            db_session,
            message_body="ciao @mario-1!",
            sender_key=KEY_C,
            sender_name="sender",
            message_id=1,
            area_name="generale",
        )
        assert notified == ["mario-1"]
