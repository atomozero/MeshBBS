"""
Shared helpers for command handlers.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import Optional

# SQLite INTEGER is 64-bit signed: larger values raise OverflowError when
# bound as query parameters. 18 digits keeps us safely below 2**63.
_MAX_INT_DIGITS = 18


def parse_int(value: Optional[str], strip_hash: bool = False) -> Optional[int]:
    """
    Parse a non-negative ASCII decimal integer from user input.

    str.isdigit() accepts Unicode digits like '²' or '٣' that int() then
    rejects or interprets unexpectedly; this helper only accepts ASCII 0-9.

    Args:
        value: Raw argument
        strip_hash: Strip a leading '#' (e.g. '#42')

    Returns:
        The integer, or None if the input is not a valid number
    """
    if value is None:
        return None
    s = value.strip()
    if strip_hash:
        s = s.lstrip("#")
    if not s or len(s) > _MAX_INT_DIGITS:
        return None
    if not (s.isascii() and s.isdecimal()):
        return None
    return int(s)


def can_view_area(area, ctx) -> bool:
    """
    Check whether the sender may see/read an area.

    Hidden areas (is_public=False) are visible only to admins.
    """
    if area is None:
        return False
    if area.is_public:
        return True
    return bool(getattr(ctx, "is_admin", False))
