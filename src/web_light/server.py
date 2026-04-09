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

/* Navigation */
nav { background: #1e293b; border-bottom: 1px solid #334155; padding: 0.75rem 1rem; }
nav .inner { max-width: 960px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; }
nav .brand { font-weight: 700; font-size: 1.1rem; color: #60a5fa; }
nav .hamburger { display: none; background: none; border: none; color: #94a3b8; font-size: 1.5rem; cursor: pointer; padding: 0.25rem; width: auto; }
nav .links { display: flex; align-items: center; }
nav .links a { margin-left: 1.5rem; color: #94a3b8; font-size: 0.9rem; }
nav .links a:hover { color: #e2e8f0; }

/* Stats cards */
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.75rem; margin: 1rem 0; }
.card { background: #1e293b; border-radius: 8px; padding: 1rem; border: 1px solid #334155; overflow-x: auto; -webkit-overflow-scrolling: touch; }
.card h3 { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem; }
.card .value { font-size: 1.5rem; font-weight: 700; color: #f1f5f9; }
.card .sub { font-size: 0.7rem; color: #64748b; margin-top: 0.25rem; }

/* Badges */
.badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
.badge-green { background: #166534; color: #4ade80; }
.badge-red { background: #7f1d1d; color: #f87171; }
.badge-yellow { background: #713f12; color: #fbbf24; }

/* Tables — scrollable on mobile */
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
table { width: 100%; border-collapse: collapse; margin: 0.5rem 0; min-width: 500px; }
th, td { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid #334155; font-size: 0.8rem; white-space: nowrap; }
th { color: #94a3b8; font-weight: 600; font-size: 0.7rem; text-transform: uppercase; position: sticky; top: 0; background: #1e293b; }
tr:hover { background: #1e293b; }
td.wrap { white-space: normal; word-break: break-word; min-width: 120px; max-width: 200px; }

.section { margin: 1.5rem 0; }
.section h2 { font-size: 1rem; margin-bottom: 0.75rem; color: #f1f5f9; }

/* Login */
.login-box { max-width: 320px; margin: 3rem auto; padding: 0 1rem; }
.login-box h1 { text-align: center; margin-bottom: 1.5rem; }
input[type=text], input[type=password] {
    width: 100%; padding: 0.6rem; margin-bottom: 0.75rem;
    background: #1e293b; border: 1px solid #475569; border-radius: 6px;
    color: #e2e8f0; font-size: 1rem;
}
button { width: 100%; padding: 0.6rem; background: #3b82f6; color: white;
         border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; font-weight: 600; }
button:hover { background: #2563eb; }
.error { color: #f87171; font-size: 0.85rem; margin-bottom: 0.75rem; text-align: center; }
.footer { text-align: center; color: #475569; font-size: 0.75rem; margin-top: 2rem; padding: 1rem; }

/* Connection indicator */
.conn-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.conn-dot.on { background: #4ade80; box-shadow: 0 0 6px #4ade80; }
.conn-dot.off { background: #f87171; box-shadow: 0 0 6px #f87171; }
.conn-status { font-size: 0.75rem; color: #94a3b8; margin-right: 1rem; }

/* Action buttons */
.btn-sm { padding: 0.2rem 0.5rem; font-size: 0.7rem; border-radius: 4px; border: none;
          cursor: pointer; font-weight: 600; width: auto; display: inline-block; margin: 1px; }
.btn-red { background: #7f1d1d; color: #f87171; }
.btn-red:hover { background: #991b1b; }
.btn-green { background: #166534; color: #4ade80; }
.btn-green:hover { background: #15803d; }
.btn-yellow { background: #713f12; color: #fbbf24; }
.btn-yellow:hover { background: #854d0e; }
.btn-blue { background: #1e3a5f; color: #60a5fa; }
.btn-blue:hover { background: #1e40af; }
td.actions { white-space: nowrap; }

/* Toast notification */
.toast { position: fixed; bottom: 1rem; right: 1rem; background: #1e293b; border: 1px solid #334155;
         padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.85rem; z-index: 1000;
         transition: opacity 0.3s; }
.toast.success { border-color: #166534; }
.toast.error { border-color: #7f1d1d; }

/* Mobile responsive */
@media (max-width: 640px) {
    nav .hamburger { display: block; }
    nav .links { display: none; width: 100%; flex-direction: column; align-items: stretch; margin-top: 0.5rem; }
    nav .links.open { display: flex; }
    nav .links a { margin: 0; padding: 0.6rem 0; border-top: 1px solid #334155; text-align: center; }
    .grid { grid-template-columns: repeat(2, 1fr); }
    .card .value { font-size: 1.3rem; }
    h1 { font-size: 1.3rem; }
    .container { padding: 0.75rem; }
    table { min-width: 400px; }
    th, td { padding: 0.4rem; font-size: 0.75rem; }
    .conn-status { display: none; }
    .btn-sm { font-size: 0.65rem; padding: 0.15rem 0.35rem; }
}
"""


def page(title, content, active=""):
    """Wrap content in base HTML template."""
    radio = _get_radio_status()
    conn_class = "on" if radio["connected"] else "off"
    conn_text = "Online" if radio["connected"] else "Offline"

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
  <span class="brand"><span id="conn-dot" class="conn-dot {conn_class}"></span>MeshBBS</span>
  <span class="conn-status" id="conn-text">{conn_text}</span>
  <button class="hamburger" onclick="document.getElementById('nav-links').classList.toggle('open')">&#9776;</button>
  <div class="links" id="nav-links">
    {nav_link('/', 'Dashboard', 'dashboard')}
    {nav_link('/messages', 'Messaggi', 'messages')}
    {nav_link('/users', 'Utenti', 'users')}
    {nav_link('/network', 'Rete', 'network')}
    {nav_link('/logs', 'Log', 'logs')}
    {nav_link('/logout', 'Esci', '')}
  </div>
</div>
</nav>
<div class="container">
{content}
</div>
<div class="footer">MeshBBS Light &middot; <span id="clock">{datetime.utcnow().strftime('%H:%M:%S UTC')}</span></div>
<script>
(function(){{
  // Auto-refresh: fetch page content every 15s and replace #live-content
  var lc = document.getElementById('live-content');
  if (!lc) return;
  var path = location.pathname === '/' ? '/api/partial/dashboard' :
             location.pathname === '/messages' ? '/api/partial/messages' :
             location.pathname === '/users' ? '/api/partial/users' :
             location.pathname === '/network' ? '/api/partial/network' :
             location.pathname === '/logs' ? '/api/partial/logs' : null;
  if (!path) return;

  function tick() {{
    var d = new Date();
    var el = document.getElementById('clock');
    if (el) el.textContent = d.toUTCString().slice(17, 25) + ' UTC';
  }}
  setInterval(tick, 1000);

  function refreshContent() {{
    fetch(path, {{credentials: 'same-origin'}})
      .then(function(r) {{ if (r.ok) return r.text(); throw r; }})
      .then(function(html) {{
        lc.innerHTML = html;
        var ind = document.getElementById('live-indicator');
        if (ind) {{ ind.style.opacity = '1'; setTimeout(function(){{ ind.style.opacity = '0.5'; }}, 500); }}
      }})
      .catch(function() {{}});
  }}
  setInterval(refreshContent, 15000);

  // Update connection indicator
  function refreshConn() {{
    fetch('/api/health', {{credentials: 'same-origin'}})
      .then(function(r) {{ return r.json(); }})
      .then(function(d) {{
        var dot = document.getElementById('conn-dot');
        var txt = document.getElementById('conn-text');
        if (dot) {{ dot.className = 'conn-dot ' + (d.radio_connected ? 'on' : 'off'); }}
        if (txt) {{ txt.textContent = d.radio_connected ? 'Online' : 'Offline'; }}
      }})
      .catch(function() {{}});
  }}
  setInterval(refreshConn, 10000);
}})();
</script>
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
            <button class="btn-sm btn-blue" style="margin-top:0.5rem" onclick="sendAdvert()">Invia Advert</button>
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

    live_content = _render_dashboard_content(stats, radio, cards, radio_info, activity_html)

    return page("Dashboard", f"""
        <h1 style="margin:1rem 0">Dashboard
            <span id="live-indicator" class="badge badge-green" style="font-size:0.6rem;vertical-align:middle;opacity:0.5">LIVE</span>
        </h1>
        <div id="toast-area"></div>
        <div id="live-content">{live_content}</div>
        <script>
        function sendAdvert() {{
            fetch('/api/advert', {{method:'POST', credentials:'same-origin'}})
            .then(function(r) {{ return r.json(); }})
            .then(function(d) {{
                var ta = document.getElementById('toast-area');
                var cls = d.ok ? 'toast success' : 'toast error';
                ta.innerHTML = '<div class="' + cls + '">' + d.message + '</div>';
                setTimeout(function(){{ ta.innerHTML = ''; }}, 3000);
            }})
            .catch(function(){{ alert('Errore di rete'); }});
        }}
        </script>
    """, active="dashboard")


def _render_dashboard_content(stats, radio, cards, radio_info, activity_html):
    """Render the dashboard inner content (used by both full page and partial)."""
    return f"{cards}{radio_info}{activity_html}"


@app.route("/api/partial/dashboard")
@require_auth
def partial_dashboard():
    """Return dashboard HTML fragment for live refresh."""
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
            <button class="btn-sm btn-blue" style="margin-top:0.5rem" onclick="sendAdvert()">Invia Advert</button>
        </div>
        </div>
        """

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

    return _render_dashboard_content(stats, radio, cards, radio_info, activity_html)


# ---------------------------------------------------------------
# Partial routes for other pages
# ---------------------------------------------------------------

@app.route("/api/partial/messages")
@require_auth
def partial_messages():
    """Return messages table HTML fragment."""
    messages = _get_recent_messages(25)
    rows = ""
    for msg in messages:
        rows += f"""<tr>
            <td>#{msg['id']}</td>
            <td>{msg['author']}</td>
            <td>{msg['area']}</td>
            <td class="wrap">{msg['body'][:60]}{'...' if len(msg['body']) > 60 else ''}</td>
            <td>{msg['time']}</td>
        </tr>"""
    return f"""<table>
    <tr><th>ID</th><th>Autore</th><th>Area</th><th>Messaggio</th><th>Data</th></tr>
    {rows if rows else '<tr><td colspan="5" style="text-align:center;color:#64748b">Nessun messaggio</td></tr>'}
    </table>"""


@app.route("/api/partial/users")
@require_auth
def partial_users():
    """Return users table HTML fragment."""
    users = _get_users()
    rows = _render_user_rows(users)
    return f"""<table>
    <tr><th>Nome</th><th>Chiave</th><th>Stato</th><th>Msg</th><th>Visto</th><th>Azioni</th></tr>
    {rows if rows else '<tr><td colspan="6" style="text-align:center;color:#64748b">Nessun utente</td></tr>'}
    </table>"""


@app.route("/api/partial/logs")
@require_auth
def partial_logs():
    """Return logs table HTML fragment."""
    logs = _get_logs(50)
    rows = ""
    for log_entry in logs:
        rows += f"""<tr>
            <td>{log_entry['time']}</td>
            <td>{log_entry['type']}</td>
            <td>{log_entry.get('user', '')}</td>
            <td>{log_entry.get('details', '')}</td>
        </tr>"""
    return f"""<table>
    <tr><th>Data</th><th>Tipo</th><th>Utente</th><th>Dettagli</th></tr>
    {rows if rows else '<tr><td colspan="4" style="text-align:center;color:#64748b">Nessun log</td></tr>'}
    </table>"""


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
            <td class="wrap">{msg['body'][:60]}{'...' if len(msg['body']) > 60 else ''}</td>
            <td>{msg['time']}</td>
        </tr>"""

    return page("Messaggi", f"""
        <h1 style="margin:1rem 0">Messaggi
            <span id="live-indicator" class="badge badge-green" style="font-size:0.6rem;vertical-align:middle;opacity:0.5">LIVE</span>
        </h1>
        <div class="card"><div id="live-content">
        <table>
        <tr><th>ID</th><th>Autore</th><th>Area</th><th>Messaggio</th><th>Data</th></tr>
        {rows if rows else '<tr><td colspan="5" style="text-align:center;color:#64748b">Nessun messaggio</td></tr>'}
        </table>
        </div></div>
    """, active="messages")


# ---------------------------------------------------------------
# Routes: Users
# ---------------------------------------------------------------

@app.route("/users")
@require_auth
def users_page():
    users = _get_users()
    rows = _render_user_rows(users)

    return page("Utenti", f"""
        <h1 style="margin:1rem 0">Utenti
            <span id="live-indicator" class="badge badge-green" style="font-size:0.6rem;vertical-align:middle;opacity:0.5">LIVE</span>
        </h1>
        <div id="toast-area"></div>
        <div class="card"><div id="live-content">
        <table>
        <tr><th>Nome</th><th>Chiave</th><th>Stato</th><th>Msg</th><th>Visto</th><th>Azioni</th></tr>
        {rows if rows else '<tr><td colspan="6" style="text-align:center;color:#64748b">Nessun utente</td></tr>'}
        </table>
        </div></div>
        <script>
        function userAction(key, action) {{
            if (!confirm('Confermi ' + action + ' per questo utente?')) return;
            fetch('/api/user/' + key + '/' + action, {{method:'POST', credentials:'same-origin'}})
            .then(function(r) {{ return r.json(); }})
            .then(function(d) {{
                var ta = document.getElementById('toast-area');
                var cls = d.ok ? 'toast success' : 'toast error';
                ta.innerHTML = '<div class="' + cls + '">' + d.message + '</div>';
                setTimeout(function(){{ ta.innerHTML = ''; }}, 3000);
                // Refresh user list
                fetch('/api/partial/users', {{credentials:'same-origin'}})
                .then(function(r){{ return r.text(); }})
                .then(function(h){{ document.getElementById('live-content').innerHTML = h; }});
            }})
            .catch(function(){{ alert('Errore di rete'); }});
        }}
        </script>
    """, active="users")


def _render_user_rows(users):
    """Render user table rows with action buttons."""
    rows = ""
    for u in users:
        status = ""
        if u.get("banned"):
            status = '<span class="badge badge-red">Bannato</span>'
        elif u.get("muted"):
            status = '<span class="badge badge-yellow">Mutato</span>'
        elif u.get("admin"):
            status = '<span class="badge badge-green">Admin</span>'
        elif u.get("moderator"):
            status = '<span class="badge badge-blue">Mod</span>'

        # Action buttons based on current status
        key = u['key']
        actions = ""
        if u.get("banned"):
            actions = f'<button class="btn-sm btn-green" onclick="userAction(\'{key}\',\'unban\')">Sbanna</button>'
        elif u.get("muted"):
            actions = f'<button class="btn-sm btn-green" onclick="userAction(\'{key}\',\'unmute\')">Smuta</button>'
        elif u.get("admin"):
            actions = f'<button class="btn-sm btn-red" onclick="userAction(\'{key}\',\'demote\')">Declassa</button>'
        elif u.get("moderator"):
            actions = (
                f'<button class="btn-sm btn-green" onclick="userAction(\'{key}\',\'promote_admin\')">Admin</button>'
                f'<button class="btn-sm btn-red" onclick="userAction(\'{key}\',\'demote\')">Declassa</button>'
                f'<button class="btn-sm btn-yellow" onclick="userAction(\'{key}\',\'mute\')">Mute</button>'
            )
        else:
            actions = (
                f'<button class="btn-sm btn-green" onclick="userAction(\'{key}\',\'promote\')">Mod</button>'
                f'<button class="btn-sm btn-red" onclick="userAction(\'{key}\',\'ban\')">Ban</button>'
                f'<button class="btn-sm btn-yellow" onclick="userAction(\'{key}\',\'mute\')">Mute</button>'
                f'<button class="btn-sm btn-blue" onclick="userAction(\'{key}\',\'kick\')">Kick</button>'
            )

        rows += f"""<tr>
            <td>{u['name']}</td>
            <td><code>{key[:8]}...</code></td>
            <td>{status}</td>
            <td>{u['messages']}</td>
            <td>{u['last_seen']}</td>
            <td class="actions">{actions}</td>
        </tr>"""
    return rows


# ---------------------------------------------------------------
# Routes: Network
# ---------------------------------------------------------------

@app.route("/network")
@require_auth
def network_page():
    nodes = _get_mesh_nodes()
    rows = _render_network_rows(nodes)

    # Build nodes JSON for the map
    geo_nodes = [n for n in nodes if "lat" in n and "lon" in n]
    nodes_json = json.dumps(geo_nodes)

    # BBS own position from config
    from utils.config import get_config
    cfg = get_config()
    bbs_lat = cfg.latitude or 0
    bbs_lon = cfg.longitude or 0

    # Determine map center
    if bbs_lat and bbs_lon:
        center_lat, center_lon = bbs_lat, bbs_lon
    elif geo_nodes:
        center_lat = sum(n["lat"] for n in geo_nodes) / len(geo_nodes)
        center_lon = sum(n["lon"] for n in geo_nodes) / len(geo_nodes)
    else:
        center_lat, center_lon = 45.5, 12.2  # Default: Veneto

    has_map = bool(geo_nodes) or (bbs_lat and bbs_lon)

    map_html = ""
    if has_map:
        map_html = f"""
        <div class="section">
        <h2>Mappa</h2>
        <div class="card" style="padding:0;overflow:hidden">
            <div id="map" style="height:350px;width:100%;border-radius:8px"></div>
        </div>
        </div>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
        (function(){{
            var map = L.map('map').setView([{center_lat},{center_lon}], 11);
            L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; OpenStreetMap',
                maxZoom: 18
            }}).addTo(map);

            var colors = {{'RPT':'#fbbf24','CLI':'#60a5fa','ROOM':'#4ade80','SENS':'#c084fc'}};

            function makeIcon(color) {{
                return L.divIcon({{
                    className: '',
                    html: '<div style="width:14px;height:14px;border-radius:50%;background:'+color+';border:2px solid #fff;box-shadow:0 0 4px rgba(0,0,0,0.5)"></div>',
                    iconSize: [14,14],
                    iconAnchor: [7,7]
                }});
            }}

            // BBS position
            var bbsLat = {bbs_lat};
            var bbsLon = {bbs_lon};
            if (bbsLat && bbsLon) {{
                L.marker([bbsLat,bbsLon], {{icon: makeIcon('#ef4444')}})
                 .addTo(map)
                 .bindPopup('<b>{cfg.bbs_name}</b><br>BBS');
            }}

            // Mesh nodes
            var nodes = {nodes_json};
            var bounds = [];
            if (bbsLat && bbsLon) bounds.push([bbsLat,bbsLon]);

            nodes.forEach(function(n) {{
                var c = colors[n.type] || '#94a3b8';
                L.marker([n.lat,n.lon], {{icon: makeIcon(c)}})
                 .addTo(map)
                 .bindPopup('<b>'+n.name+'</b><br>'+n.type+'<br>'+n.path);
                bounds.push([n.lat,n.lon]);
            }});

            if (bounds.length > 1) {{
                map.fitBounds(bounds, {{padding:[30,30]}});
            }}
        }})();
        </script>
        """

    return page("Rete", f"""
        <h1 style="margin:1rem 0">Rete Mesh
            <span id="live-indicator" class="badge badge-green" style="font-size:0.6rem;vertical-align:middle;opacity:0.5">LIVE</span>
        </h1>
        <div class="grid">
            <div class="card">
                <h3>Nodi totali</h3>
                <div class="value">{len(nodes)}</div>
                <div class="sub">{len(geo_nodes)} con GPS</div>
            </div>
            <div class="card">
                <h3>Ripetitori</h3>
                <div class="value">{sum(1 for n in nodes if n['type'] == 'RPT')}</div>
            </div>
            <div class="card">
                <h3>Client</h3>
                <div class="value">{sum(1 for n in nodes if n['type'] == 'CLI')}</div>
            </div>
            <div class="card">
                <h3>BBS/Room</h3>
                <div class="value">{sum(1 for n in nodes if n['type'] == 'ROOM')}</div>
            </div>
        </div>
        {map_html}
        <div class="card"><div id="live-content">
        <table>
        <tr><th>Nome</th><th>Tipo</th><th>Chiave</th><th>Percorso</th></tr>
        {rows if rows else '<tr><td colspan="4" style="text-align:center;color:#64748b">Nessun nodo visibile</td></tr>'}
        </table>
        </div></div>
    """, active="network")


def _render_network_rows(nodes):
    """Render network table rows."""
    rows = ""
    type_badges = {
        "RPT": '<span class="badge badge-yellow">RPT</span>',
        "CLI": '<span class="badge" style="background:#1e3a5f;color:#60a5fa">CLI</span>',
        "ROOM": '<span class="badge badge-green">ROOM</span>',
        "SENS": '<span class="badge" style="background:#4a1d7f;color:#c084fc">SENS</span>',
    }
    for n in nodes:
        badge = type_badges.get(n["type"], '<span class="badge">?</span>')
        path = n.get("path", "")
        rows += f"""<tr>
            <td><strong>{n['name']}</strong></td>
            <td>{badge}</td>
            <td><code>{n['key'][:12]}...</code></td>
            <td>{path}</td>
        </tr>"""
    return rows


@app.route("/api/partial/network")
@require_auth
def partial_network():
    """Return network table HTML fragment."""
    nodes = _get_mesh_nodes()
    rows = _render_network_rows(nodes)
    return f"""<table>
    <tr><th>Nome</th><th>Tipo</th><th>Chiave</th><th>Percorso</th></tr>
    {rows if rows else '<tr><td colspan="4" style="text-align:center;color:#64748b">Nessun nodo visibile</td></tr>'}
    </table>"""


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
        <h1 style="margin:1rem 0">Log attivita
            <span id="live-indicator" class="badge badge-green" style="font-size:0.6rem;vertical-align:middle;opacity:0.5">LIVE</span>
        </h1>
        <div class="card"><div id="live-content">
        <table>
        <tr><th>Data</th><th>Tipo</th><th>Utente</th><th>Dettagli</th></tr>
        {rows if rows else '<tr><td colspan="4" style="text-align:center;color:#64748b">Nessun log</td></tr>'}
        </table>
        </div></div>
    """, active="logs")


# ---------------------------------------------------------------
# Admin actions API
# ---------------------------------------------------------------

@app.route("/api/user/<key>/<action>", method="POST")
@require_auth
def user_action(key, action):
    """Execute admin action on a user."""
    response.content_type = "application/json"

    valid_actions = {"ban", "unban", "mute", "unmute", "kick", "unkick",
                     "promote", "promote_admin", "demote"}
    if action not in valid_actions:
        return json.dumps({"ok": False, "message": f"Azione '{action}' non valida"})

    try:
        from bbs.models.base import get_session
        from bbs.models.user import User
        from bbs.models.activity_log import ActivityLog, EventType, log_activity

        with get_session() as session:
            user = session.query(User).filter(User.public_key == key).first()
            if not user:
                return json.dumps({"ok": False, "message": "Utente non trovato"})

            name = user.display_name

            if action == "ban":
                user.ban(reason="Bannato da admin web")
                log_activity(session, EventType.USER_BANNED, user_key=key, details="Via web admin")
            elif action == "unban":
                user.unban()
                log_activity(session, EventType.USER_UNBANNED, user_key=key, details="Via web admin")
            elif action == "mute":
                user.mute(reason="Mutato da admin web")
                log_activity(session, EventType.USER_MUTED, user_key=key, details="Via web admin")
            elif action == "unmute":
                user.unmute()
                log_activity(session, EventType.USER_UNMUTED, user_key=key, details="Via web admin")
            elif action == "kick":
                user.kick(minutes=60, reason="Kick da admin web")
                log_activity(session, EventType.USER_KICKED, user_key=key, details="60 min via web admin")
            elif action == "unkick":
                user.unkick()
                log_activity(session, EventType.USER_UNKICKED, user_key=key, details="Via web admin")
            elif action == "promote":
                user.promote_to_moderator()
                log_activity(session, EventType.USER_PROMOTED, user_key=key, details="Moderatore via web admin")
            elif action == "promote_admin":
                user.promote_to_admin()
                log_activity(session, EventType.USER_PROMOTED, user_key=key, details="Admin via web admin")
            elif action == "demote":
                if user.is_admin:
                    user.demote_from_admin()
                elif user.is_moderator:
                    user.demote_from_moderator()
                log_activity(session, EventType.USER_DEMOTED, user_key=key, details="Via web admin")

            session.commit()

            action_names = {
                "ban": "bannato", "unban": "sbannato",
                "mute": "mutato", "unmute": "smutato",
                "kick": "kickato (60 min)", "unkick": "unkickato",
                "promote": "promosso a moderatore",
                "promote_admin": "promosso ad admin",
                "demote": "declassato",
            }
            return json.dumps({"ok": True, "message": f"{name} {action_names[action]}"})

    except Exception as e:
        logger.error(f"Error executing user action {action} on {key[:8]}: {e}")
        return json.dumps({"ok": False, "message": f"Errore: {str(e)}"})


# ---------------------------------------------------------------
# API JSON (per integrazioni esterne)
# ---------------------------------------------------------------

@app.route("/api/advert", method="POST")
@require_auth
def api_send_advert():
    """Send a manual advertisement on the mesh network."""
    response.content_type = "application/json"
    try:
        from bbs.runtime import get_bbs_instance, get_event_loop

        bbs = get_bbs_instance()
        loop = get_event_loop()

        if bbs is None or not bbs._running:
            return json.dumps({"ok": False, "message": "BBS non attivo"})
        if loop is None:
            return json.dumps({"ok": False, "message": "Event loop non disponibile"})

        import asyncio
        future = asyncio.run_coroutine_threadsafe(
            bbs.connection.send_advert(flood=True), loop
        )
        success = future.result(timeout=15)

        if success:
            return json.dumps({"ok": True, "message": "Advertisement inviato"})
        else:
            return json.dumps({"ok": False, "message": "Invio fallito"})
    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


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


def _get_mesh_nodes():
    """Get mesh network nodes from companion radio."""
    NODE_TYPES = {0: "---", 1: "CLI", 2: "RPT", 3: "ROOM", 4: "SENS"}
    try:
        from bbs.runtime import get_bbs_instance

        bbs = get_bbs_instance()
        if bbs is None or not bbs._running:
            return []

        mc = bbs.connection._meshcore
        if mc is None:
            return []

        contacts = mc.contacts or {}
        nodes = []
        for key, info in contacts.items():
            node_type = NODE_TYPES.get(info.get("type", 0), "?")
            name = info.get("name", key[:8] if isinstance(key, str) else "?")
            adv_name = info.get("adv_name", "")
            path = f"via {adv_name}" if adv_name else "diretto"
            pub_key = info.get("pubkey", key)
            if isinstance(pub_key, bytes):
                pub_key = pub_key.hex()

            node_data = {
                "name": name,
                "type": node_type,
                "key": str(pub_key),
                "path": path,
            }

            # Add GPS coordinates if available
            lat = info.get("adv_lat")
            lon = info.get("adv_lon")
            if lat and lon and lat != 0 and lon != 0:
                node_data["lat"] = lat
                node_data["lon"] = lon

            nodes.append(node_data)

        # Sort: repeaters first, then by name
        type_order = {"RPT": 0, "ROOM": 1, "CLI": 2, "SENS": 3}
        nodes.sort(key=lambda n: (type_order.get(n["type"], 9), n["name"]))
        return nodes

    except Exception as e:
        logger.error(f"Error fetching mesh nodes: {e}")
        return []


def _get_radio_status():
    """Get radio connection status."""
    try:
        from meshbbs_radio.state import get_state_manager

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
                    "moderator": u.is_moderator,
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
