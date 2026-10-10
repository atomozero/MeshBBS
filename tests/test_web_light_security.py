"""
Security tests for the lightweight bottle web server (web_light).

Covers: XSS escaping of mesh/DB data, CSRF + Origin checks, session cookie
flags and TTL, weak admin password refusal, 401 JSON for /api/*.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import io
import json
import re
import time
from datetime import datetime
from http.cookies import SimpleCookie
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlencode

import pytest

import web_light.server as srv

XSS = "<script>alert(1)</script>"
XSS_Q = "x'\"><img src=x onerror=alert(1)>"
STRONG_PW = "S3cure-Test-Passw0rd!"
HOST = "localhost:8080"
ORIGIN = "http://localhost:8080"


# ---------------------------------------------------------------
# WSGI test client
# ---------------------------------------------------------------

class Resp:
    def __init__(self, status, headers, body):
        self.status = status
        self.code = int(status.split()[0])
        self.headers = headers
        self.body = body

    def header(self, name):
        return [v for k, v in self.headers if k.lower() == name.lower()]

    def cookies(self):
        out = {}
        for raw in self.header("Set-Cookie"):
            c = SimpleCookie()
            c.load(raw)
            for k, m in c.items():
                out[k] = (m.value, raw)
        return out

    def json(self):
        return json.loads(self.body)


def call(path, method="GET", cookies=None, headers=None, form=None, json_body=None,
         scheme="http"):
    query = ""
    if "?" in path:
        path, query = path.split("?", 1)
    body = b""
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "SERVER_NAME": "localhost",
        "SERVER_PORT": "8080",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "HTTP_HOST": HOST,
        "REMOTE_ADDR": "127.0.0.1",
        "wsgi.errors": io.StringIO(),
        "wsgi.url_scheme": scheme,
    }
    if form is not None:
        body = urlencode(form).encode()
        environ["CONTENT_TYPE"] = "application/x-www-form-urlencoded"
    elif json_body is not None:
        body = json.dumps(json_body).encode()
        environ["CONTENT_TYPE"] = "application/json"
    environ["CONTENT_LENGTH"] = str(len(body))
    environ["wsgi.input"] = io.BytesIO(body)
    if cookies:
        environ["HTTP_COOKIE"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    for k, v in (headers or {}).items():
        environ["HTTP_" + k.upper().replace("-", "_")] = v

    captured = {}

    def start_response(status, hdrs, exc_info=None):
        captured["status"] = status
        captured["headers"] = hdrs

    out = srv.app.wsgi(environ, start_response)
    text = b"".join(out).decode("utf-8", errors="replace")
    return Resp(captured["status"], captured["headers"], text)


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.setattr(srv, "_admin_password", STRONG_PW)
    monkeypatch.setattr(srv, "_admin_username", "admin")
    srv._sessions.clear()
    srv._login_attempts.clear()
    srv._last_seen_repeaters.clear()
    srv._nodes_cache["time"] = 0.0
    srv._nodes_cache["nodes"] = []
    # Default: no radio, no stats DB needed
    monkeypatch.setattr(srv, "_get_radio_status",
                        lambda: {"connected": False, "status": "x", "messages_processed": 0})
    yield
    srv._sessions.clear()
    srv._login_attempts.clear()


def login(password=STRONG_PW, username="admin"):
    """Perform the full login flow; returns (response, session cookie or None)."""
    r = call("/login")
    token_cookie = r.cookies()[srv.LOGIN_CSRF_COOKIE][0]
    m = re.search(r'name="csrf_token" value="([^"]+)"', r.body)
    assert m and m.group(1) == token_cookie
    r = call("/login", method="POST",
             cookies={srv.LOGIN_CSRF_COOKIE: token_cookie},
             headers={"Origin": ORIGIN},
             form={"username": username, "password": password, "csrf_token": token_cookie})
    sid = r.cookies().get(srv.SESSION_COOKIE, (None, None))[0]
    return r, sid


def auth():
    r, sid = login()
    assert r.code == 303 and sid
    return {srv.SESSION_COOKIE: sid}, srv._sessions[sid]["csrf"]


# ---------------------------------------------------------------
# Login / sessions
# ---------------------------------------------------------------

class TestLoginAndSession:
    def test_login_success_sets_hardened_cookie(self):
        r, sid = login()
        assert r.code == 303
        raw = r.cookies()[srv.SESSION_COOKIE][1].lower()
        assert "httponly" in raw
        assert "samesite=strict" in raw
        assert "path=/" in raw
        assert "secure" not in raw  # plain http
        # Plain random token (not a bottle signed/pickled cookie)
        assert not sid.startswith("!") and "?" not in sid
        assert len(sid) >= 40

    def test_cookie_secure_on_https(self):
        r = call("/login", scheme="https")
        raw = r.cookies()[srv.LOGIN_CSRF_COOKIE][1].lower()
        assert "secure" in raw

    def test_wrong_password_rejected(self):
        r, sid = login(password="nope")
        assert r.code == 200 and sid is None
        assert "Credenziali errate" in r.body

    def test_login_without_csrf_token_rejected(self):
        r = call("/login", method="POST", headers={"Origin": ORIGIN},
                 form={"username": "admin", "password": STRONG_PW})
        assert srv.SESSION_COOKIE not in r.cookies()
        assert "Richiesta non valida" in r.body

    def test_login_cross_origin_rejected(self):
        r = call("/login")
        tok = r.cookies()[srv.LOGIN_CSRF_COOKIE][0]
        r = call("/login", method="POST", cookies={srv.LOGIN_CSRF_COOKIE: tok},
                 headers={"Origin": "http://evil.example"},
                 form={"username": "admin", "password": STRONG_PW, "csrf_token": tok})
        assert srv.SESSION_COOKIE not in r.cookies()

    @pytest.mark.parametrize("weak", ["", "meshbbs123"])
    def test_weak_password_disables_login(self, monkeypatch, weak):
        monkeypatch.setattr(srv, "_admin_password", weak)
        r = call("/login")
        assert "ADMIN_PASSWORD" in r.body and "config.env" in r.body
        assert 'name="password"' not in r.body
        r = call("/login", method="POST", headers={"Origin": ORIGIN},
                 form={"username": "admin", "password": weak})
        assert srv.SESSION_COOKIE not in r.cookies()
        assert not srv._sessions

    def test_session_idle_ttl_expires(self):
        cookies, _ = auth()
        sid = cookies[srv.SESSION_COOKIE]
        srv._sessions[sid]["last"] = time.time() - srv.SESSION_TTL - 1
        r = call("/", cookies=cookies)
        assert r.code == 303
        assert sid not in srv._sessions

    def test_expired_sessions_pruned_on_login(self):
        srv._sessions["old"] = {"user": "admin", "created": 0, "last": 0, "csrf": "x"}
        auth()
        assert "old" not in srv._sessions

    def test_stale_login_attempts_pruned(self):
        srv._login_attempts["10.0.0.1"] = [time.time() - srv.LOGIN_LOCKOUT - 10]
        assert srv._check_login_rate("127.0.0.1")
        assert "10.0.0.1" not in srv._login_attempts

    def test_logout_requires_post_and_csrf(self):
        cookies, csrf = auth()
        sid = cookies[srv.SESSION_COOKIE]
        assert call("/logout", cookies=cookies).code == 405
        # Missing token: session survives
        call("/logout", method="POST", cookies=cookies, headers={"Origin": ORIGIN}, form={})
        assert sid in srv._sessions
        r = call("/logout", method="POST", cookies=cookies, headers={"Origin": ORIGIN},
                 form={"csrf_token": csrf})
        assert r.code == 303
        assert sid not in srv._sessions

    def test_page_contains_csrf_meta_and_logout_form(self, monkeypatch):
        cookies, csrf = auth()
        monkeypatch.setattr(srv, "_get_logs", lambda *a, **k: [])
        r = call("/logs", cookies=cookies)
        assert f'<meta name="csrf-token" content="{csrf}">' in r.body
        assert 'action="/logout"' in r.body and 'method="POST"' in r.body


# ---------------------------------------------------------------
# API auth + CSRF
# ---------------------------------------------------------------

class TestApiAuthAndCsrf:
    def test_api_unauthenticated_returns_401_json(self):
        r = call("/api/stats")
        assert r.code == 401
        assert r.json()["ok"] is False
        r = call("/api/partial/dashboard")
        assert r.code == 401

    def test_pages_still_redirect(self):
        assert call("/users").code == 303

    def test_post_without_csrf_rejected(self):
        cookies, _ = auth()
        with patch.object(srv, "_get_mesh_nodes") as m:
            r = call("/api/settings", method="POST", cookies=cookies,
                     headers={"Origin": ORIGIN}, json_body={"bbs_name": "pwned"})
            m.assert_not_called()
        assert r.code == 403
        assert r.json()["error"] == "csrf"

    def test_post_with_wrong_csrf_rejected(self):
        cookies, _ = auth()
        r = call("/api/user/abc/ban", method="POST", cookies=cookies,
                 headers={"Origin": ORIGIN, "X-CSRF-Token": "wrong"})
        assert r.code == 403

    def test_delete_without_csrf_rejected(self):
        cookies, _ = auth()
        r = call("/api/message/1", method="DELETE", cookies=cookies, headers={"Origin": ORIGIN})
        assert r.code == 403

    def test_cross_origin_rejected_even_with_token(self):
        cookies, csrf = auth()
        r = call("/api/user/abc/ban", method="POST", cookies=cookies,
                 headers={"Origin": "http://evil.example", "X-CSRF-Token": csrf})
        assert r.code == 403
        assert r.json()["error"] == "bad_origin"
        r = call("/api/user/abc/ban", method="POST", cookies=cookies,
                 headers={"Referer": "http://evil.example/x", "X-CSRF-Token": csrf})
        assert r.code == 403

    def test_valid_csrf_accepted(self):
        cookies, csrf = auth()
        # Invalid action -> handler reached, returns its own JSON error
        r = call("/api/user/abc/explode", method="POST", cookies=cookies,
                 headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
        assert r.code == 200
        assert "non valida" in r.json()["message"]


# ---------------------------------------------------------------
# XSS escaping
# ---------------------------------------------------------------

class TestXss:
    def test_helpers(self):
        assert srv.esc(0) == "0"
        assert srv.esc(None) == ""
        out = srv._js_json([{"name": "</script><script>alert(1)</script>&"}])
        assert "<" not in out and ">" not in out and "&" not in out
        assert json.loads(out)[0]["name"].startswith("</script>")

    def test_network_page_escapes_node_names(self, monkeypatch):
        cookies, _ = auth()
        nodes = [{"name": XSS, "type": "RPT", "key": XSS_Q, "path": XSS_Q, "hops": 1,
                  "lat": 45.1, "lon": 12.1}]
        monkeypatch.setattr(srv, "_get_mesh_nodes", lambda refresh=False: list(nodes))
        monkeypatch.setattr(srv, "_render_repeater_telemetry", lambda: "")
        cfg = SimpleNamespace(latitude=45.0, longitude=12.0, bbs_name="</script><b>x")
        with patch("utils.config.get_config", return_value=cfg):
            r = call("/network", cookies=cookies)
        assert r.code == 200
        assert XSS not in r.body
        assert "<img src=x" not in r.body
        assert "</script><b>x" not in r.body
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in r.body
        # popups built with escapeHtml, not raw concatenation
        assert "escapeHtml(n.name)" in r.body
        assert "'<b>'+n.name" not in r.body

    def test_partial_network_has_five_columns_and_no_radio_refresh(self, monkeypatch):
        cookies, _ = auth()
        calls = []

        def fake(refresh=False):
            calls.append(refresh)
            return [{"name": XSS, "type": "CLI", "key": "k" * 20, "path": "diretto", "hops": 0}]

        monkeypatch.setattr(srv, "_get_mesh_nodes", fake)
        r = call("/api/partial/network", cookies=cookies)
        assert "<th>Hop</th>" in r.body
        assert XSS not in r.body
        assert calls == [False]

    def test_dashboard_repeater_alert_escaped(self, monkeypatch):
        cookies, _ = auth()
        monkeypatch.setattr(srv, "_get_mesh_nodes", lambda refresh=False: [])
        monkeypatch.setattr(srv, "_get_stats", lambda: {})
        monkeypatch.setattr(srv, "_get_recent_activity", lambda limit=10: [])
        monkeypatch.setattr(srv, "_render_activity_chart", lambda: "")
        srv._last_seen_repeaters[XSS] = time.time() - 600
        srv._last_seen_repeaters["ancient"] = time.time() - 30 * 86400
        r = call("/api/partial/dashboard", cookies=cookies)
        assert "Repeater non raggiungibili" in r.body
        assert XSS not in r.body
        assert "&lt;script&gt;" in r.body
        assert "ancient" not in srv._last_seen_repeaters

    def test_radio_name_escaped(self, monkeypatch):
        cookies, _ = auth()
        monkeypatch.setattr(srv, "_get_radio_status", lambda: {
            "connected": True, "status": "c", "messages_processed": 1,
            "name": XSS, "port": XSS_Q, "battery_level": None})
        monkeypatch.setattr(srv, "_get_mesh_nodes", lambda refresh=False: [])
        monkeypatch.setattr(srv, "_get_stats", lambda: {})
        monkeypatch.setattr(srv, "_get_recent_activity", lambda limit=10: [])
        monkeypatch.setattr(srv, "_render_activity_chart", lambda: "")
        r = call("/api/partial/dashboard", cookies=cookies)
        assert XSS not in r.body and "<img src=x" not in r.body

    def test_users_page_uses_data_attributes(self, monkeypatch):
        cookies, _ = auth()
        users = [{"name": XSS_Q, "key": "ab'cd\"<x>" + "0" * 20, "admin": False,
                  "moderator": False, "banned": False, "muted": False,
                  "messages": 3, "last_seen": "mai"}]
        monkeypatch.setattr(srv, "_get_users_paginated", lambda p=1, n=50: (list(users), 1))
        r = call("/users", cookies=cookies)
        assert r.code == 200
        assert "<img src=x" not in r.body
        assert "onclick=\"showSendMsg" not in r.body
        assert "onclick=\"userAction" not in r.body
        assert 'data-name="x&#39;&quot;&gt;&lt;img src=x onerror=alert(1)&gt;"' in r.body
        assert 'data-action="ban"' in r.body

    def test_settings_values_escaped(self):
        cookies, _ = auth()
        cfg = SimpleNamespace(bbs_name=XSS_Q, response_prefix="", default_area="g",
                              latitude=None, longitude=None, send_delay=0,
                              advert_interval_minutes=0, beacon_interval=0,
                              beacon_message=XSS, pm_retention_days=0,
                              activity_log_retention_days=0)
        with patch("utils.config.get_config", return_value=cfg):
            r = call("/settings", cookies=cookies)
        assert r.code == 200
        assert XSS not in r.body and "<img src=x" not in r.body
        assert 'name="beacon_interval" value="0"' in r.body

    def test_toasts_use_text_content(self, monkeypatch):
        cookies, _ = auth()
        monkeypatch.setattr(srv, "_get_messages_paginated", lambda p=1, n=25: ([], 0))
        r = call("/messages", cookies=cookies)
        assert "+ d.message +" not in r.body
        assert "showToast(d.message" in r.body


# ---------------------------------------------------------------
# Misc robustness
# ---------------------------------------------------------------

class TestMisc:
    def test_messages_bad_page_param(self, monkeypatch):
        cookies, _ = auth()
        seen = []

        def fake(p=1, n=25):
            seen.append(p)
            return [], 0

        monkeypatch.setattr(srv, "_get_messages_paginated", fake)
        assert call("/messages?p=abc", cookies=cookies).code == 200
        assert call("/messages?p=-5", cookies=cookies).code == 200
        assert all(p >= 1 for p in seen)

    def test_users_aggregated_query_and_pagination(self, db_session, sample_areas):
        from bbs.models.message import Message
        from bbs.models.user import User

        for i in range(3):
            db_session.add(User(public_key=f"{i:064x}", nickname=f"<u{i}>",
                                last_seen=datetime(2026, 1, 1 + i)))
        db_session.commit()
        for _ in range(4):
            db_session.add(Message(area_id=sample_areas[0].id, sender_key=f"{2:064x}", body="b"))
        db_session.commit()

        users, total = srv._get_users_paginated(1, 2)
        assert total == 3 and len(users) == 2
        assert users[0]["name"] == "<u2>" and users[0]["messages"] == 4
        users2, _ = srv._get_users_paginated(2, 2)
        assert len(users2) == 1 and users2[0]["messages"] == 0

    def test_activity_chart_groups_by_hour(self, db_session, sample_areas):
        from bbs.models.message import Message
        from bbs.models.user import User

        db_session.add(User(public_key="f" * 64))
        db_session.commit()
        for _ in range(3):
            db_session.add(Message(area_id=sample_areas[0].id, sender_key="f" * 64, body="b"))
        db_session.commit()
        html = srv._render_activity_chart()
        assert "(3 msg, 0 adv)" in html

    def test_mesh_nodes_cached(self, monkeypatch):
        calls = []

        def build(refresh=False):
            calls.append(refresh)
            return [{"name": "n", "type": "CLI", "key": "k", "path": "", "hops": 0}]

        monkeypatch.setattr(srv, "_build_mesh_nodes", build)
        srv._get_mesh_nodes(refresh=True)
        srv._get_mesh_nodes(refresh=False)
        srv._get_mesh_nodes(refresh=True)
        assert calls == [True]

    def test_threaded_server_class(self):
        from socketserver import ThreadingMixIn
        assert issubclass(srv._ThreadingWSGIServer, ThreadingMixIn)
        assert srv._ThreadingWSGIServer.daemon_threads is True

    def test_security_headers(self):
        r = call("/login")
        assert r.header("X-Frame-Options") == ["DENY"]
        assert r.header("X-Content-Type-Options") == ["nosniff"]
