"""
Runtime state shared between BBS core and web server.

This module holds references to the running BBSCore instance and
the asyncio event loop, accessible from both the main thread and
the web server thread.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import time

_bbs_instance = None
_event_loop = None
_start_time = time.time()


def get_uptime_seconds():
    """Get BBS process uptime in seconds."""
    return int(time.time() - _start_time)


def set_bbs_instance(bbs):
    global _bbs_instance
    _bbs_instance = bbs


def get_bbs_instance():
    return _bbs_instance


def set_event_loop(loop):
    global _event_loop
    _event_loop = loop


def get_event_loop():
    return _event_loop
