"""
Canonical user keys.

MIT License - Copyright (c) 2026 MeshBBS Contributors

MeshCore identifies DM senders only by a 6-byte public key prefix
(12 hex chars, "pubkey_prefix"), while contacts resolved from the
companion carry the full 32-byte key (64 hex chars). Using both forms as
User.public_key made the same person appear as two different users.

The BBS therefore uses ONE canonical form for user identity: the
lowercase 12-hex-char prefix. It is what every DM already carries, so
existing users created by DMs keep their key unchanged.

normalize_user_keys() is a safe, idempotent data migration for rows
created with a full 64-char key (e.g. by a channel "!bbs" resolved via
contacts): they are renamed to the prefix form, or merged into the
existing prefix user, with all references updated. Keys are canonicalised
on input, so it runs once, as schema migration 1 (bbs.models.migrations).
"""

import re
from typing import Optional, Union

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.user_keys")
except ImportError:
    import logging
    logger = logging.getLogger("meshbbs.user_keys")


# Length (hex chars) of the key prefix used as canonical user identity
CANONICAL_KEY_LENGTH = 12

_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")

# (table, column) pairs that store a user public key
_KEY_REFERENCES = (
    ("messages", "sender_key"),
    ("private_messages", "sender_key"),
    ("private_messages", "recipient_key"),
    ("activity_log", "user_key"),
    ("delivery_statuses", "sender_key"),
    ("delivery_statuses", "recipient_key"),
)


def canonical_user_key(key: Optional[str]) -> Optional[str]:
    """
    Return the canonical user key for a MeshCore public key or prefix.

    Hex keys of at least 12 chars are reduced to their lowercase 12-char
    prefix. Anything else (empty, shorter, non-hex test/legacy keys) is
    returned unchanged.
    """
    if not key:
        return key
    key = key.strip()
    if len(key) >= CANONICAL_KEY_LENGTH and _HEX_RE.match(key):
        return key[:CANONICAL_KEY_LENGTH].lower()
    return key


def _existing_tables(session: Session) -> set:
    rows = session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    ).fetchall()
    return {r[0] for r in rows}


def _update_references(session: Session, tables: set, old: str, new: str) -> None:
    for table, column in _KEY_REFERENCES:
        if table not in tables:
            continue
        session.execute(
            text(f"UPDATE {table} SET {column} = :new WHERE {column} = :old"),
            {"new": new, "old": old},
        )


def normalize_user_keys(session: Union[Session, Connection], commit: bool = True) -> int:
    """
    Migrate users stored with a non-canonical key to the canonical form.

    - No user with the canonical key: the row is renamed.
    - A canonical user already exists: roles/flags are merged into it
      (admin/moderator/ban/mute are OR-ed, nickname kept or inherited),
      references are moved, and the duplicate row is deleted.

    Idempotent: a second run finds nothing to do. Only SQLite databases
    are handled (the BBS default); other dialects are skipped.

    Args:
        session: ORM Session or Core Connection
        commit: Commit the changes (the migration runner passes False and
            commits its own transaction)

    Returns:
        Number of user rows migrated
    """
    bind = session.get_bind() if hasattr(session, "get_bind") else session
    if bind is None or bind.dialect.name != "sqlite":
        return 0

    tables = _existing_tables(session)
    if "users" not in tables:
        return 0

    rows = session.execute(
        text(
            "SELECT id, public_key, nickname, is_admin, is_moderator, "
            "is_banned, ban_reason, is_muted, mute_reason FROM users"
        )
    ).mappings().all()

    by_key = {r["public_key"]: dict(r) for r in rows}
    migrated = 0

    if not any(canonical_user_key(r["public_key"]) != r["public_key"] for r in rows):
        return 0

    # Parent key and child references are updated in separate statements:
    # with foreign keys enforced, defer the check to commit time (the
    # pragma resets automatically at the end of the transaction).
    session.execute(text("PRAGMA defer_foreign_keys = ON"))

    for row in rows:
        old_key = row["public_key"]
        new_key = canonical_user_key(old_key)
        if not new_key or new_key == old_key:
            continue

        twin = by_key.get(new_key)
        if twin is None:
            session.execute(
                text("UPDATE users SET public_key = :new WHERE id = :id"),
                {"new": new_key, "id": row["id"]},
            )
            _update_references(session, tables, old_key, new_key)
            moved = dict(row)
            moved["public_key"] = new_key
            by_key[new_key] = moved
            by_key.pop(old_key, None)
            logger.info(f"User key normalised: {old_key[:12]}... -> {new_key}")
        else:
            nickname = twin["nickname"] or row["nickname"]
            session.execute(
                text(
                    "UPDATE users SET "
                    "is_admin = :is_admin, is_moderator = :is_moderator, "
                    "is_banned = :is_banned, ban_reason = :ban_reason, "
                    "is_muted = :is_muted, mute_reason = :mute_reason "
                    "WHERE id = :id"
                ),
                {
                    "is_admin": bool(twin["is_admin"] or row["is_admin"]),
                    "is_moderator": bool(twin["is_moderator"] or row["is_moderator"]),
                    "is_banned": bool(twin["is_banned"] or row["is_banned"]),
                    "ban_reason": twin["ban_reason"] or row["ban_reason"],
                    "is_muted": bool(twin["is_muted"] or row["is_muted"]),
                    "mute_reason": twin["mute_reason"] or row["mute_reason"],
                    "id": twin["id"],
                },
            )
            _update_references(session, tables, old_key, new_key)
            session.execute(text("DELETE FROM users WHERE id = :id"), {"id": row["id"]})
            if nickname and not twin["nickname"]:
                session.execute(
                    text("UPDATE users SET nickname = :nick WHERE id = :id"),
                    {"nick": nickname, "id": twin["id"]},
                )
                twin["nickname"] = nickname
            by_key.pop(old_key, None)
            logger.info(f"User key merged: {old_key[:12]}... -> {new_key}")
        migrated += 1

    if migrated:
        if commit:
            session.commit()
        logger.info(f"User key normalisation: {migrated} user(s) migrated")
    return migrated
