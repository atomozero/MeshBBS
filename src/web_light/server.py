"""
MeshBBS Lightweight Web Server.

Minimal web dashboard for Raspberry Pi Zero and other constrained devices.
Uses bottle.py (single file, zero compiled dependencies).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import json
import os
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path

# Import bottle from local copy
import sys
sys.path.insert(0, str(Path(__file__).parent))
from bottle import Bottle, request, response, template, static_file, run

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.web_light")
except ImportError:
    import logging
    logger = logging.getLogger("meshbbs.web_light")


app = Bottle()

# Simple session store (in-memory, single admin)
_sessions = {}
_admin_password = os.environ.get("ADMIN_PASSWORD", "meshbbs123")
_admin_username = os.environ.get("ADMIN_USERNAME", "admin")


# ---------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------

def check_auth():
    """Check if request has valid session cookie."""
    sid = request.get_cookie("session", secret="meshbbs-cookie-secret")
    return sid in _sessions


def require_auth(func):
    """Decorator to require authentication."""
    def wrapper(*args, **kwargs):
        if not check_auth():
            response.status = 303
            response.set_header("Location", "/login")
            return ""
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


# ---------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------

BASE_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #0f172a; color: #e2e8f0; line-height: 1.6; }
a { color: #60a5fa; text-decoration: none; }
a:hover { text-decoration: underline; }

.container { max-width: 960px; margin: 0 auto; padding: 1rem; }

nav { background: #1e293b; border-bottom: 1px solid #334155; padding: 0.75rem 1rem; }
nav .inner { max-width: 960px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
nav .brand { font-weight: 700; font-size: 1.1rem; color: #60a5fa; }
nav .links a { margin-left: 1.5rem; color: #94a3b8; font-size: 0.9rem; }
nav .links a:hover { color: #e2e8f0; }

.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1rem 0; }
.card { background: #1e293b; border-radius: 8px; padding: 1.25rem; border: 1px solid #334155; }
.card h3 { font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem; }
.card .value { font-size: 1.8rem; font-weight: 700; color: #f1f5f9; }
.card .sub { font-size: 0.75rem; color: #64748b; margin-top: 0.25rem; }

.badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
.badge-green { background: #166534; color: #4ade80; }
.badge-red { background: #7f1d1d; color: #f87171; }
.badge-yellow { background: #713f12; color: #fbbf24; }

table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
th, td { text-align: left; padding: 0.6rem 0.75rem; border-bottom: 1px solid #334155; font-size: 0.85rem; }
th { color: #94a3b8; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }
tr:hover { background: #1e293b; }

.section { margin: 1.5rem 0; }
.section h2 { font-size: 1.1rem; margin-bottom: 0.75rem; color: #f1f5f9; }

.login-box { max-width: 320px; margin: 4rem auto; }
.login-box h1 { text-align: center; margin-bottom: 1.5rem; }
input[type=text], input[type=password] {
    width: 100%; padding: 0.6rem; margin-bottom: 0.75rem;
    background: #1e293b; border: 1px solid #475569; border-radius: 6px;
    color: #e2e8f0; font-size: 0.9rem;
}
button { width: 100%; padding: 0.6rem; background: #3b82f6; color: white;
         border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
button:hover { background: #2563eb; }
.error { color: #f87171; font-size: 0.85rem; margin-bottom: 0.75rem; text-align: center; }
.footer { text-align: center; color: #475569; font-size: 0.75rem; margin-top: 2rem; padding: 1rem; }
.msg-feed { max-height: 300px; overflow-y: auto; }
.msg-item { padding: 0.5rem 0; border-bottom: 1px solid #1e293b; font-size: 0.85rem; }
.msg-sender { color: #60a5fa; font-weight: 600; }
.msg-time { color: #64748b; font-size: 0.75rem; }
.refresh-note { font-size: 0.75rem; color: #64748b; }
"""


def page(title, content, active=""):
    """Wrap content in base HTML template."""
    def nav_link(href, label, key):
        cls = "color: #e2e8f0; font-weight: 600;" if active == key else ""
        return f'<a href="{href}" style="{cls}">{label}</a>'

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - MeshBBS</title>
<style>{BASE_CSS}</style>
</head>
<body>
<nav>
<div class="inner">
  <span class="brand">MeshBBS Admin</span>
  <div class="links">
    {nav_link('/', 'Dashboard', 'dashboard')}
    {nav_link('/messages', 'Messaggi', 'messages')}
    {nav_link('/users', 'Utenti', 'users')}
    {nav_link('/logs', 'Log', 'logs')}
    {nav_link('/logout', 'Esci', '')}
  </div>
</div>
</nav>
<div class="container">
{content}
</div>
<div class="footer">MeshBBS Light &middot; {datetime.utcnow().strftime('%H:%M:%S UTC')}</div>
</body>
</html>"""


# ---------------------------------------------------------------
# Routes: Auth
# ---------------------------------------------------------------

@app.route("/login", method=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        username = request.forms.get("username", "")
        password = request.forms.get("password", "")

        if username == _admin_username and password == _admin_password:
            import hashlib
            sid = hashlib.sha256(f"{time.time()}{username}".encode()).hexdigest()[:32]
            _sessions[sid] = {"user": username, "time": time.time()}
            response.set_cookie("session", sid, secret="meshbbs-cookie-secret", path="/", max_age=86400)
            response.status = 303
            response.set_header("Location", "/")
            return ""
        else:
            error = "Username o password errati"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Login - MeshBBS</title><style>{BASE_CSS}</style></head>
<body><div class="login-box"><h1>MeshBBS</h1>
<div class="card">
{'<p class="error">' + error + '</p>' if error else ''}
<form method="POST">
<input type="text" name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Accedi</button>
</form></div></div></body></html>"""


@app.route("/logout")
def logout():
    sid = request.get_cookie("session", secret="meshbbs-cookie-secret")
    if sid in _sessions:
        del _sessions[sid]
    response.delete_cookie("session", path="/")
    response.status = 303
    response.set_header("Location", "/login")
    return ""


# ---------------------------------------------------------------
# Routes: Dashboard
# ---------------------------------------------------------------

@app.route("/")
@require_auth
def dashboard():
    stats = _get_stats()
    radio = _get_radio_status()

    radio_badge = '<span class="badge badge-green">Connesso</span>' if radio["connected"] else '<span class="badge badge-red">Disconnesso</span>'

    cards = f"""
    <div class="grid">
        <div class="card">
            <h3>Utenti</h3>
            <div class="value">{stats.get('users', {}).get('total', 0)}</div>
            <div class="sub">{stats.get('users', {}).get('active_24h', 0)} attivi 24h</div>
        </div>
        <div class="card">
            <h3>Messaggi oggi</h3>
            <div class="value">{stats.get('messages', {}).get('public', {}).get('today', 0)}</div>
            <div class="sub">{stats.get('messages', {}).get('public', {}).get('total', 0)} totali</div>
        </div>
        <div class="card">
            <h3>PM</h3>
            <div class="value">{stats.get('messages', {}).get('private', {}).get('today', 0)}</div>
            <div class="sub">{stats.get('messages', {}).get('private', {}).get('unread', 0)} non letti</div>
        </div>
        <div class="card">
            <h3>Radio</h3>
            <div class="value">{radio_badge}</div>
            <div class="sub">{radio.get('messages_processed', 0)} msg processati</div>
        </div>
    </div>
    """

    # Radio details
    radio_info = ""
    if radio["connected"]:
        battery = radio.get("battery_level")
        bat_str = f"{battery}%" if battery is not None else "N/A"
        radio_info = f"""
        <div class="section">
        <h2>Stato Radio</h2>
        <div class="card">
            <table>
            <tr><td>Nome</td><td>{radio.get('name', 'N/A')}</td></tr>
            <tr><td>Porta</td><td>{radio.get('port', 'N/A')}</td></tr>
            <tr><td>Batteria</td><td>{bat_str}</td></tr>
            <tr><td>Uptime</td><td>{_format_uptime(radio.get('uptime_seconds', 0))}</td></tr>
            <tr><td>Messaggi</td><td>{radio.get('messages_processed', 0)}</td></tr>
            </table>
        </div>
        </div>
        """

    # Recent activity
    activity = _get_recent_activity(10)
    act_rows = ""
    for item in activity:
        act_rows += f'<tr><td>{item["time"]}</td><td>{item["event"]}</td><td>{item["details"]}</td></tr>'

    activity_html = f"""
    <div class="section">
    <h2>Attivita recente</h2>
    <div class="card">
        <table>
        <tr><th>Ora</th><th>Evento</th><th>Dettagli</th></tr>
        {act_rows if act_rows else '<tr><td colspan="3" style="text-align:center;color:#64748b">Nessuna attivita</td></tr>'}
        </table>
    </div>
    </div>
    """

    return page("Dashboard", f"""
        <h1 style="margin:1rem 0">Dashboard</h1>
        <span class="refresh-note">Aggiorna pagina per dati aggiornati</span>
        {cards}{radio_info}{activity_html}
    """, active="dashboard")


# ---------------------------------------------------------------
# Routes: Messages
# ---------------------------------------------------------------

@app.route("/messages")
@require_auth
def messages_page():
    messages = _get_recent_messages(25)

    rows = ""
    for msg in messages:
        rows += f"""<tr>
            <td>#{msg['id']}</td>
            <td>{msg['author']}</td>
            <td>{msg['area']}</td>
            <td>{msg['body'][:60]}{'...' if len(msg['body']) > 60 else ''}</td>
            <td>{msg['time']}</td>
        </tr>"""

    return page("Messaggi", f"""
        <h1 style="margin:1rem 0">Messaggi</h1>
        <div class="card">
        <table>
        <tr><th>ID</th><th>Autore</th><th>Area</th><th>Messaggio</th><th>Data</th></tr>
        {rows if rows else '<tr><td colspan="5" style="text-align:center;color:#64748b">Nessun messaggio</td></tr>'}
        </table>
        </div>
    """, active="messages")


# ---------------------------------------------------------------
# Routes: Users
# ---------------------------------------------------------------

@app.route("/users")
@require_auth
def users_page():
    users = _get_users()

    rows = ""
    for u in users:
        status = ""
        if u.get("banned"):
            status = '<span class="badge badge-red">Bannato</span>'
        elif u.get("muted"):
            status = '<span class="badge badge-yellow">Mutato</span>'
        elif u.get("admin"):
            status = '<span class="badge badge-green">Admin</span>'

        rows += f"""<tr>
            <td>{u['name']}</td>
            <td><code>{u['key'][:12]}...</code></td>
            <td>{status}</td>
            <td>{u['messages']}</td>
            <td>{u['last_seen']}</td>
        </tr>"""

    return page("Utenti", f"""
        <h1 style="margin:1rem 0">Utenti</h1>
        <div class="card">
        <table>
        <tr><th>Nome</th><th>Chiave</th><th>Stato</th><th>Messaggi</th><th>Ultimo accesso</th></tr>
        {rows if rows else '<tr><td colspan="5" style="text-align:center;color:#64748b">Nessun utente</td></tr>'}
        </table>
        </div>
    """, active="users")


# ---------------------------------------------------------------
# Routes: Logs
# ---------------------------------------------------------------

@app.route("/logs")
@require_auth
def logs_page():
    logs = _get_logs(50)

    rows = ""
    for log_entry in logs:
        rows += f"""<tr>
            <td>{log_entry['time']}</td>
            <td>{log_entry['type']}</td>
            <td>{log_entry.get('user', '')}</td>
            <td>{log_entry.get('details', '')}</td>
        </tr>"""

    return page("Log", f"""
        <h1 style="margin:1rem 0">Log attivita</h1>
        <div class="card">
        <table>
        <tr><th>Data</th><th>Tipo</th><th>Utente</th><th>Dettagli</th></tr>
        {rows if rows else '<tr><td colspan="4" style="text-align:center;color:#64748b">Nessun log</td></tr>'}
        </table>
        </div>
    """, active="logs")


# ---------------------------------------------------------------
# API JSON (per integrazioni esterne)
# ---------------------------------------------------------------

@app.route("/api/stats")
@require_auth
def api_stats():
    response.content_type = "application/json"
    return json.dumps(_get_stats())


@app.route("/api/health")
def api_health():
    """Health check senza autenticazione."""
    response.content_type = "application/json"
    radio = _get_radio_status()
    return json.dumps({
        "status": "ok" if radio["connected"] else "degraded",
        "radio_connected": radio["connected"],
        "timestamp": datetime.utcnow().isoformat(),
    })


# ---------------------------------------------------------------
# Data helpers (query database)
# ---------------------------------------------------------------

def _get_stats():
    """Collect stats from database."""
    try:
        from bbs.models.base import get_session
        from bbs.services.stats_collector import StatsCollector

        with get_session() as session:
            collector = StatsCollector(session)
            return collector.collect()
    except Exception as e:
        logger.error(f"Error collecting stats: {e}")
        return {"users": {"total": 0, "active_24h": 0}, "messages": {"public": {"total": 0, "today": 0}, "private": {"total": 0, "today": 0, "unread": 0}}}


def _get_radio_status():
    """Get radio connection status."""
    try:
        from meshcore.state import get_state_manager

        sm = get_state_manager()
        state = sm.state
        data = {
            "connected": sm.is_connected,
            "status": state.status.value,
            "messages_processed": state.message_count,
        }
        if sm.is_connected:
            data["name"] = state.radio_info.name
            data["port"] = state.radio_info.port
            data["battery_level"] = state.radio_info.battery_level
            if state.connected_at:
                data["uptime_seconds"] = int((datetime.utcnow() - state.connected_at).total_seconds())
        return data
    except Exception:
        return {"connected": False, "status": "unknown", "messages_processed": 0}


def _get_recent_messages(limit=25):
    """Get recent messages from database."""
    try:
        from bbs.models.base import get_session
        from bbs.models.message import Message
        from bbs.models.user import User

        with get_session() as session:
            messages = (
                session.query(Message)
                .order_by(Message.timestamp.desc())
                .limit(limit)
                .all()
            )
            result = []
            for msg in messages:
                author = msg.author.display_name if msg.author else msg.sender_key[:8]
                area_name = msg.area.name if msg.area else "?"
                result.append({
                    "id": msg.id,
                    "author": author,
                    "area": area_name,
                    "body": msg.body or "",
                    "time": msg.timestamp.strftime("%d/%m %H:%M") if msg.timestamp else "",
                })
            return result
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return []


def _get_users():
    """Get users from database."""
    try:
        from bbs.models.base import get_session
        from bbs.models.user import User
        from bbs.models.message import Message
        from sqlalchemy import func

        with get_session() as session:
            users = session.query(User).order_by(User.last_seen.desc()).limit(50).all()
            result = []
            for u in users:
                msg_count = session.query(Message).filter_by(sender_key=u.public_key).count()
                result.append({
                    "name": u.display_name,
                    "key": u.public_key,
                    "admin": u.is_admin,
                    "banned": u.is_banned,
                    "muted": u.is_muted,
                    "messages": msg_count,
                    "last_seen": u.last_seen.strftime("%d/%m %H:%M") if u.last_seen else "mai",
                })
            return result
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return []


def _get_recent_activity(limit=10):
    """Get recent activity log entries."""
    try:
        from bbs.models.base import get_session
        from bbs.models.activity_log import ActivityLog

        with get_session() as session:
            logs = (
                session.query(ActivityLog)
                .order_by(ActivityLog.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [{
                "time": l.timestamp.strftime("%H:%M:%S") if l.timestamp else "",
                "event": l.event_type,
                "details": l.details or "",
            } for l in logs]
    except Exception:
        return []


def _get_logs(limit=50):
    """Get activity logs."""
    try:
        from bbs.models.base import get_session
        from bbs.models.activity_log import ActivityLog

        with get_session() as session:
            logs = (
                session.query(ActivityLog)
                .order_by(ActivityLog.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [{
                "time": l.timestamp.strftime("%d/%m %H:%M:%S") if l.timestamp else "",
                "type": l.event_type,
                "user": l.user_key[:8] if l.user_key else "",
                "details": l.details or "",
            } for l in logs]
    except Exception:
        return []


def _format_uptime(seconds):
    """Format uptime seconds to human readable string."""
    if not seconds:
        return "N/A"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60
    if days > 0:
        return f"{days}g {hours}h {mins}m"
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


# ---------------------------------------------------------------
# Server startup
# ---------------------------------------------------------------

def start_server(host="0.0.0.0", port=8080, debug=False):
    """Start the lightweight web server in a background thread."""
    logger.info(f"Starting lightweight web server on {host}:{port}")
    thread = threading.Thread(
        target=run,
        args=(app,),
        kwargs={"host": host, "port": port, "quiet": not debug, "debug": debug},
        daemon=True,
    )
    thread.start()
    return thread


def run_server(host="0.0.0.0", port=8080, debug=False):
    """Run the web server (blocking, for standalone use)."""
    logger.info(f"Starting lightweight web server on {host}:{port}")
    run(app, host=host, port=port, quiet=not debug, debug=debug)
