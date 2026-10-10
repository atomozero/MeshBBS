"""
Tests for canonical user keys (12-hex prefix) and the startup migration.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from sqlalchemy import text

from bbs.models.user import User
from bbs.services.user_keys import canonical_user_key, normalize_user_keys


FULL = "ab12" * 16
PREFIX = FULL[:12]


class TestCanonicalKey:

    def test_full_key_reduced_to_prefix(self):
        assert canonical_user_key(FULL) == PREFIX

    def test_prefix_unchanged(self):
        assert canonical_user_key(PREFIX) == PREFIX

    def test_uppercase_lowered(self):
        assert canonical_user_key(FULL.upper()) == PREFIX

    def test_non_hex_and_short_untouched(self):
        assert canonical_user_key("web_admin_user") == "web_admin_user"
        assert canonical_user_key("abc") == "abc"
        assert canonical_user_key("") == ""
        assert canonical_user_key(None) is None


def _add_pm(session, sender, recipient, body="ciao"):
    session.execute(
        text(
            "INSERT INTO private_messages (sender_key, recipient_key, body, timestamp, is_read) "
            "VALUES (:s, :r, :b, CURRENT_TIMESTAMP, 0)"
        ),
        {"s": sender, "r": recipient, "b": body},
    )


class TestNormalizeUserKeys:

    def test_rename_when_no_twin(self, db_session):
        db_session.add(User(public_key=FULL, nickname="mario"))
        db_session.add(User(public_key="ff" * 6))
        db_session.commit()
        _add_pm(db_session, FULL, "ff" * 6)
        db_session.commit()

        assert normalize_user_keys(db_session) == 1
        db_session.expire_all()

        keys = sorted(u.public_key for u in db_session.query(User).all())
        assert keys == sorted([PREFIX, "ff" * 6])
        sender = db_session.execute(text("SELECT sender_key FROM private_messages")).scalar()
        assert sender == PREFIX

    def test_merge_into_existing_prefix_user(self, db_session):
        db_session.add(User(public_key=PREFIX, nickname=None))
        db_session.add(User(public_key=FULL, nickname="mario", is_admin=True))
        db_session.add(User(public_key="ee" * 6))
        db_session.commit()
        _add_pm(db_session, "ee" * 6, FULL)
        db_session.commit()

        assert normalize_user_keys(db_session) == 1
        db_session.expire_all()

        users = db_session.query(User).filter(User.public_key.in_([PREFIX, FULL])).all()
        assert len(users) == 1
        merged = users[0]
        assert merged.public_key == PREFIX
        assert merged.nickname == "mario"
        assert merged.is_admin is True
        recipient = db_session.execute(text("SELECT recipient_key FROM private_messages")).scalar()
        assert recipient == PREFIX

    def test_idempotent(self, db_session):
        db_session.add(User(public_key=FULL))
        db_session.commit()
        assert normalize_user_keys(db_session) == 1
        assert normalize_user_keys(db_session) == 0

    def test_non_hex_keys_left_alone(self, db_session):
        db_session.add(User(public_key="Z" * 64))
        db_session.commit()
        assert normalize_user_keys(db_session) == 0
        assert db_session.query(User).filter_by(public_key="Z" * 64).count() == 1
