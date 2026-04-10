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


def esc(text):
    """Escape HTML special characters to prevent XSS."""
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")

# Simple session store (in-memory, single admin)
_sessions = {}
_admin_password = os.environ.get("ADMIN_PASSWORD", "meshbbs123")
_admin_username = os.environ.get("ADMIN_USERNAME", "admin")

# Generate unique cookie secret per instance (survives restarts via env var)
import hashlib as _hl
_cookie_secret = os.environ.get("COOKIE_SECRET", _hl.sha256(
    f"{_admin_password}{os.getpid()}{time.time()}".encode()
).hexdigest())


# ---------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------

def check_auth():
    """Check if request has valid session cookie."""
    sid = request.get_cookie("session", secret=_cookie_secret)
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
    {nav_link('/settings', 'Config', 'settings')}
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

# Login rate limiting: IP -> [timestamps of failed attempts]
_login_attempts = {}
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW = 300      # 5 minutes
LOGIN_LOCKOUT = 900     # 15 minutes lockout


def _check_login_rate(ip: str) -> bool:
    """Returns True if login is allowed for this IP."""
    now = time.time()
    if ip not in _login_attempts:
        return True
    attempts = _login_attempts[ip]
    # Clean old attempts
    attempts = [t for t in attempts if now - t < LOGIN_LOCKOUT]
    _login_attempts[ip] = attempts
    # Check if locked out (too many recent failures)
    recent = [t for t in attempts if now - t < LOGIN_WINDOW]
    return len(recent) < LOGIN_MAX_ATTEMPTS


def _record_login_failure(ip: str):
    """Record a failed login attempt."""
    if ip not in _login_attempts:
        _login_attempts[ip] = []
    _login_attempts[ip].append(time.time())


@app.route("/login", method=["GET", "POST"])
def login():
    error = ""
    client_ip = request.environ.get("REMOTE_ADDR", "unknown")

    if request.method == "POST":
        if not _check_login_rate(client_ip):
            error = "Troppi tentativi. Riprova tra 15 minuti"
        else:
            username = request.forms.get("username", "")
            password = request.forms.get("password", "")

            if username == _admin_username and password == _admin_password:
                import hashlib
                sid = hashlib.sha256(f"{time.time()}{username}".encode()).hexdigest()[:32]
                _sessions[sid] = {"user": username, "time": time.time()}
                response.set_cookie("session", sid, secret=_cookie_secret, path="/", max_age=86400)
                # Clear failed attempts on success
                _login_attempts.pop(client_ip, None)
                response.status = 303
                response.set_header("Location", "/")
                return ""
            else:
                _record_login_failure(client_ip)
                remaining = LOGIN_MAX_ATTEMPTS - len([t for t in _login_attempts.get(client_ip, []) if time.time() - t < LOGIN_WINDOW])
                if remaining <= 0:
                    error = "Troppi tentativi. Riprova tra 15 minuti"
                else:
                    error = f"Credenziali errate ({remaining} tentativi rimasti)"

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
    sid = request.get_cookie("session", secret=_cookie_secret)
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

    sys_info = stats.get('system', {})
    uptime_str = _format_uptime(sys_info.get('uptime_seconds', 0))
    db_size = _format_bytes(sys_info.get('db_size_bytes', 0))

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
        <div class="card">
            <h3>Uptime BBS</h3>
            <div class="value">{uptime_str}</div>
            <div class="sub">DB: {db_size}</div>
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
        act_rows += f'<tr><td>{esc(item["time"])}</td><td>{esc(item["event"])}</td><td>{esc(item["details"])}</td></tr>'

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
        <div class="section">
        <h2>Broadcast canale</h2>
        <div class="card">
            <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
                <input type="text" id="broadcast-msg" placeholder="Scrivi messaggio per il canale pubblico..." style="flex:1;min-width:200px;margin:0">
                <button class="btn-sm btn-blue" style="padding:0.5rem 1rem;font-size:0.85rem" onclick="sendBroadcast()">Invia</button>
            </div>
            <div style="font-size:0.7rem;color:#64748b;margin-top:0.4rem">Il messaggio verra inviato sul canale pubblico della rete mesh</div>
        </div>
        </div>
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
        function sendBroadcast() {{
            var msg = document.getElementById('broadcast-msg').value.trim();
            if (!msg) {{ alert('Scrivi un messaggio'); return; }}
            if (!confirm('Inviare sul canale pubblico?\\n\\n' + msg)) return;
            fetch('/api/broadcast', {{
                method: 'POST',
                credentials: 'same-origin',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{message: msg}})
            }})
            .then(function(r) {{ return r.json(); }})
            .then(function(d) {{
                var ta = document.getElementById('toast-area');
                var cls = d.ok ? 'toast success' : 'toast error';
                ta.innerHTML = '<div class="' + cls + '">' + d.message + '</div>';
                if (d.ok) document.getElementById('broadcast-msg').value = '';
                setTimeout(function(){{ ta.innerHTML = ''; }}, 3000);
            }})
            .catch(function(){{ alert('Errore di rete'); }});
        }}
        </script>
    """, active="dashboard")


def _render_dashboard_content(stats, radio, cards, radio_info, activity_html):
    """Render the dashboard inner content (used by both full page and partial)."""
    chart_html = _render_activity_chart()
    alert_html = _render_repeater_alerts()
    return f"{cards}{alert_html}{radio_info}{chart_html}{activity_html}"


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
        act_rows += f'<tr><td>{esc(item["time"])}</td><td>{esc(item["event"])}</td><td>{esc(item["details"])}</td></tr>'

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
    rows = _render_message_rows(messages)
    return f"""<table>
    <tr><th>ID</th><th>Autore</th><th>Area</th><th>Messaggio</th><th>Data</th><th></th></tr>
    {rows if rows else '<tr><td colspan="6" style="text-align:center;color:#64748b">Nessun messaggio</td></tr>'}
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
            <td>{esc(log_entry['type'])}</td>
            <td>{esc(log_entry.get('user', ''))}</td>
            <td>{esc(log_entry.get('details', ''))}</td>
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
    page_num = int(request.params.get("p", 1))
    per_page = 25
    messages, total = _get_messages_paginated(page_num, per_page)
    rows = _render_message_rows(messages)
    total_pages = max(1, (total + per_page - 1) // per_page)

    pagination = ""
    if total_pages > 1:
        links = []
        if page_num > 1:
            links.append(f'<a href="/messages?p={page_num - 1}">&laquo; Prec</a>')
        links.append(f'<span style="color:#94a3b8">Pagina {page_num}/{total_pages}</span>')
        if page_num < total_pages:
            links.append(f'<a href="/messages?p={page_num + 1}">Succ &raquo;</a>')
        pagination = f'<div style="margin-top:0.75rem;text-align:center;font-size:0.85rem">{" &middot; ".join(links)}</div>'

    return page("Messaggi", f"""
        <h1 style="margin:1rem 0">Messaggi
            <span id="live-indicator" class="badge badge-green" style="font-size:0.6rem;vertical-align:middle;opacity:0.5">LIVE</span>
        </h1>
        <div id="toast-area"></div>
        <div class="card"><div id="live-content">
        <table>
        <tr><th>ID</th><th>Autore</th><th>Area</th><th>Messaggio</th><th>Data</th><th></th></tr>
        {rows if rows else '<tr><td colspan="6" style="text-align:center;color:#64748b">Nessun messaggio</td></tr>'}
        </table>
        </div></div>
        {pagination}
        <script>
        function deleteMsg(id) {{
            if (!confirm('Eliminare messaggio #' + id + '?')) return;
            fetch('/api/message/' + id, {{method:'DELETE', credentials:'same-origin'}})
            .then(function(r) {{ return r.json(); }})
            .then(function(d) {{
                var ta = document.getElementById('toast-area');
                var cls = d.ok ? 'toast success' : 'toast error';
                ta.innerHTML = '<div class="' + cls + '">' + d.message + '</div>';
                setTimeout(function(){{ ta.innerHTML = ''; }}, 3000);
                if (d.ok) {{
                    fetch('/api/partial/messages', {{credentials:'same-origin'}})
                    .then(function(r){{ return r.text(); }})
                    .then(function(h){{ document.getElementById('live-content').innerHTML = h; }});
                }}
            }})
            .catch(function(){{ alert('Errore di rete'); }});
        }}
        </script>
    """, active="messages")


def _render_message_rows(messages):
    """Render message table rows with delete button."""
    rows = ""
    for msg in messages:
        rows += f"""<tr>
            <td>#{msg['id']}</td>
            <td>{esc(msg['author'])}</td>
            <td>{esc(msg['area'])}</td>
            <td class="wrap">{esc(msg['body'][:60])}{'...' if len(msg['body']) > 60 else ''}</td>
            <td>{msg['time']}</td>
            <td class="actions"><button class="btn-sm btn-red" onclick="deleteMsg({msg['id']})">X</button></td>
        </tr>"""
    return rows


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
        <div class="section" id="send-msg-section" style="display:none">
        <h2>Invia messaggio a <span id="send-msg-name"></span></h2>
        <div class="card">
            <input type="hidden" id="send-msg-key">
            <input type="text" id="send-msg-text" placeholder="Scrivi messaggio..." style="margin-bottom:0.5rem" maxlength="140">
            <div style="display:flex;gap:0.5rem">
                <button class="btn-sm btn-blue" style="padding:0.4rem 1rem" onclick="doSendMsg()">Invia</button>
                <button class="btn-sm btn-red" style="padding:0.4rem 1rem" onclick="cancelSendMsg()">Annulla</button>
            </div>
        </div>
        </div>
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
                fetch('/api/partial/users', {{credentials:'same-origin'}})
                .then(function(r){{ return r.text(); }})
                .then(function(h){{ document.getElementById('live-content').innerHTML = h; }});
            }})
            .catch(function(){{ alert('Errore di rete'); }});
        }}
        function showSendMsg(key, name) {{
            document.getElementById('send-msg-key').value = key;
            document.getElementById('send-msg-name').textContent = name;
            document.getElementById('send-msg-text').value = '';
            document.getElementById('send-msg-section').style.display = 'block';
            document.getElementById('send-msg-text').focus();
        }}
        function cancelSendMsg() {{
            document.getElementById('send-msg-section').style.display = 'none';
        }}
        function doSendMsg() {{
            var key = document.getElementById('send-msg-key').value;
            var text = document.getElementById('send-msg-text').value.trim();
            if (!text) {{ alert('Scrivi un messaggio'); return; }}
            fetch('/api/send-message', {{
                method: 'POST',
                credentials: 'same-origin',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{recipient_key: key, text: text}})
            }})
            .then(function(r) {{ return r.json(); }})
            .then(function(d) {{
                var ta = document.getElementById('toast-area');
                var cls = d.ok ? 'toast success' : 'toast error';
                ta.innerHTML = '<div class="' + cls + '">' + d.message + '</div>';
                setTimeout(function(){{ ta.innerHTML = ''; }}, 3000);
                if (d.ok) cancelSendMsg();
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

        # Add send message button for all non-banned users
        name_escaped = esc(u['name']).replace("'", "\\'")
        if not u.get("banned"):
            actions += f' <button class="btn-sm btn-blue" onclick="showSendMsg(\'{key}\',\'{name_escaped}\')">Scrivi</button>'

        rows += f"""<tr>
            <td>{esc(u['name'])}</td>
            <td><code>{key[:8]}...</code></td>
            <td>{status}</td>
            <td>{u['messages']}</td>
            <td>{esc(u['last_seen'])}</td>
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
        <tr><th>Nome</th><th>Tipo</th><th>Hop</th><th>Chiave</th><th>Percorso</th></tr>
        {rows if rows else '<tr><td colspan="5" style="text-align:center;color:#64748b">Nessun nodo visibile</td></tr>'}
        </table>
        </div></div>
    """, active="network")


def _render_network_rows(nodes):
    """Render network table rows grouped by type."""
    type_badges = {
        "RPT": '<span class="badge badge-yellow">RPT</span>',
        "CLI": '<span class="badge" style="background:#1e3a5f;color:#60a5fa">CLI</span>',
        "ROOM": '<span class="badge badge-green">ROOM</span>',
        "SENS": '<span class="badge" style="background:#4a1d7f;color:#c084fc">SENS</span>',
    }
    type_labels = {"RPT": "Ripetitori", "ROOM": "BBS / Room", "CLI": "Client", "SENS": "Sensori"}
    type_order = ["RPT", "ROOM", "CLI", "SENS", "---"]

    # Group nodes by type
    groups = {}
    for n in nodes:
        t = n["type"]
        if t not in groups:
            groups[t] = []
        groups[t].append(n)

    rows = ""
    for t in type_order:
        if t not in groups:
            continue
        label = type_labels.get(t, t)
        badge = type_badges.get(t, f'<span class="badge">{t}</span>')
        rows += f'<tr><td colspan="5" style="padding-top:1rem"><strong>{badge} {label} ({len(groups[t])})</strong></td></tr>'
        for n in groups[t]:
            path = n.get("path", "")
            hops = n.get("hops", 0)
            hop_badge = f'<span class="badge" style="background:#334155;color:#94a3b8">{hops}h</span>' if hops > 0 else '<span class="badge badge-green">0h</span>'
            gps = ""
            if "lat" in n and "lon" in n:
                gps = f' <span style="color:#64748b;font-size:0.7rem">GPS</span>'
            rows += f"""<tr>
                <td>{esc(n['name'])}{gps}</td>
                <td>{badge}</td>
                <td>{hop_badge}</td>
                <td><code>{n['key'][:12]}...</code></td>
                <td class="wrap">{esc(path)}</td>
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
            <td>{esc(log_entry['type'])}</td>
            <td>{esc(log_entry.get('user', ''))}</td>
            <td>{esc(log_entry.get('details', ''))}</td>
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
# Routes: Settings
# ---------------------------------------------------------------

@app.route("/settings")
@require_auth
def settings_page():
    from utils.config import get_config
    cfg = get_config()

    return page("Impostazioni", f"""
        <h1 style="margin:1rem 0">Impostazioni</h1>
        <div id="toast-area"></div>
        <form id="settings-form" onsubmit="return saveSettings(event)">
        <div class="grid" style="grid-template-columns:1fr 1fr">
            <div class="card">
                <h3>BBS</h3>
                <label style="font-size:0.8rem;color:#94a3b8">Nome BBS</label>
                <input type="text" name="bbs_name" value="{cfg.bbs_name}" style="margin-bottom:0.5rem">
                <label style="font-size:0.8rem;color:#94a3b8">Prefisso risposte</label>
                <input type="text" name="response_prefix" value="{cfg.response_prefix}" style="margin-bottom:0.5rem">
                <label style="font-size:0.8rem;color:#94a3b8">Area predefinita</label>
                <input type="text" name="default_area" value="{cfg.default_area}" style="margin-bottom:0.5rem">
            </div>
            <div class="card">
                <h3>Posizione</h3>
                <label style="font-size:0.8rem;color:#94a3b8">Latitudine</label>
                <input type="text" name="latitude" value="{cfg.latitude or ''}" placeholder="45.4986" style="margin-bottom:0.5rem">
                <label style="font-size:0.8rem;color:#94a3b8">Longitudine</label>
                <input type="text" name="longitude" value="{cfg.longitude or ''}" placeholder="12.2459" style="margin-bottom:0.5rem">
            </div>
            <div class="card">
                <h3>Invio messaggi</h3>
                <label style="font-size:0.8rem;color:#94a3b8">Delay tra chunk (sec)</label>
                <input type="text" name="send_delay" value="{cfg.send_delay}" style="margin-bottom:0.5rem">
                <label style="font-size:0.8rem;color:#94a3b8">Advert ogni (min)</label>
                <input type="text" name="advert_interval_minutes" value="{cfg.advert_interval_minutes}" style="margin-bottom:0.5rem">
            </div>
            <div class="card">
                <h3>Beacon</h3>
                <label style="font-size:0.8rem;color:#94a3b8">Intervallo beacon (min, 0=off)</label>
                <input type="text" name="beacon_interval" value="{cfg.beacon_interval}" style="margin-bottom:0.5rem">
                <label style="font-size:0.8rem;color:#94a3b8">Messaggio beacon</label>
                <input type="text" name="beacon_message" value="{cfg.beacon_message}" style="margin-bottom:0.5rem">
            </div>
            <div class="card">
                <h3>Retention</h3>
                <label style="font-size:0.8rem;color:#94a3b8">PM retention (giorni, 0=infinito)</label>
                <input type="text" name="pm_retention_days" value="{cfg.pm_retention_days}" style="margin-bottom:0.5rem">
                <label style="font-size:0.8rem;color:#94a3b8">Log retention (giorni)</label>
                <input type="text" name="activity_log_retention_days" value="{cfg.activity_log_retention_days}" style="margin-bottom:0.5rem">
            </div>
        </div>
        <button type="submit" style="margin-top:1rem;max-width:200px">Salva</button>
        </form>

        <div class="section">
        <h2>Orologio Companion</h2>
        <div class="card">
            <div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">
                <div>
                    <label style="font-size:0.8rem;color:#94a3b8">Ora companion:</label>
                    <span id="companion-time" style="font-size:1.1rem;font-weight:600">--:--:--</span>
                </div>
                <div>
                    <label style="font-size:0.8rem;color:#94a3b8">Ora server (Pi):</label>
                    <span id="server-time" style="font-size:1.1rem;font-weight:600">--:--:--</span>
                </div>
                <div>
                    <label style="font-size:0.8rem;color:#94a3b8">Differenza:</label>
                    <span id="time-diff" style="font-size:1.1rem;font-weight:600">--</span>
                </div>
                <button class="btn-sm btn-blue" style="padding:0.4rem 1rem" onclick="syncTime()">Sincronizza con Pi</button>
            </div>
        </div>
        </div>

        <script>
        // Load companion time on page load
        (function(){{
            fetch('/api/companion-time', {{credentials:'same-origin'}})
            .then(function(r){{ return r.json(); }})
            .then(function(d){{
                if (d.ok) {{
                    document.getElementById('companion-time').textContent = d.companion_time;
                    document.getElementById('server-time').textContent = d.server_time;
                    var diff = d.diff_seconds;
                    var sign = diff >= 0 ? '+' : '';
                    document.getElementById('time-diff').textContent = sign + diff + 's';
                    var el = document.getElementById('time-diff');
                    if (Math.abs(diff) > 60) el.style.color = '#f87171';
                    else if (Math.abs(diff) > 10) el.style.color = '#fbbf24';
                    else el.style.color = '#4ade80';
                }} else {{
                    document.getElementById('companion-time').textContent = d.message || 'Errore';
                }}
            }})
            .catch(function(){{ document.getElementById('companion-time').textContent = 'N/A'; }});
        }})();

        function syncTime() {{
            if (!confirm('Sincronizzare orologio companion con ora Pi?')) return;
            fetch('/api/companion-time/sync', {{method:'POST', credentials:'same-origin'}})
            .then(function(r){{ return r.json(); }})
            .then(function(d){{
                var ta = document.getElementById('toast-area');
                var cls = d.ok ? 'toast success' : 'toast error';
                ta.innerHTML = '<div class="' + cls + '">' + d.message + '</div>';
                setTimeout(function(){{ ta.innerHTML = ''; location.reload(); }}, 2000);
            }})
            .catch(function(){{ alert('Errore di rete'); }});
        }}

        function saveSettings(e) {{
            e.preventDefault();
            var form = document.getElementById('settings-form');
            var data = {{}};
            var inputs = form.querySelectorAll('input');
            inputs.forEach(function(inp) {{
                var v = inp.value.trim();
                if (v !== '') data[inp.name] = v;
            }});
            fetch('/api/settings', {{
                method: 'POST',
                credentials: 'same-origin',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify(data)
            }})
            .then(function(r) {{ return r.json(); }})
            .then(function(d) {{
                var ta = document.getElementById('toast-area');
                var cls = d.ok ? 'toast success' : 'toast error';
                ta.innerHTML = '<div class="' + cls + '">' + d.message + '</div>';
                setTimeout(function(){{ ta.innerHTML = ''; }}, 3000);
            }})
            .catch(function() {{ alert('Errore di rete'); }});
            return false;
        }}
        </script>
    """, active="settings")


@app.route("/api/settings", method="POST")
@require_auth
def api_save_settings():
    """Save BBS settings."""
    response.content_type = "application/json"
    try:
        from utils.config import get_config
        cfg = get_config()

        data = request.json or {}
        updates = {}

        # String fields
        for field in ("bbs_name", "default_area", "response_prefix", "beacon_message"):
            if field in data and data[field]:
                updates[field] = str(data[field])

        # Float fields
        for field in ("latitude", "longitude", "send_delay"):
            if field in data and data[field]:
                try:
                    updates[field] = float(data[field])
                except ValueError:
                    pass

        # Int fields
        for field in ("advert_interval_minutes", "beacon_interval",
                      "pm_retention_days", "activity_log_retention_days"):
            if field in data and data[field]:
                try:
                    updates[field] = int(data[field])
                except ValueError:
                    pass

        if updates:
            cfg.update(updates)
            return json.dumps({"ok": True, "message": f"{len(updates)} impostazioni salvate"})
        else:
            return json.dumps({"ok": False, "message": "Nessuna modifica"})

    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


# ---------------------------------------------------------------
# Companion time API
# ---------------------------------------------------------------

@app.route("/api/companion-time")
@require_auth
def api_get_companion_time():
    """Get companion radio time and compare with server."""
    response.content_type = "application/json"
    try:
        from bbs.runtime import get_bbs_instance, get_event_loop
        import asyncio

        bbs = get_bbs_instance()
        loop = get_event_loop()

        if not bbs or not bbs._running or not loop:
            return json.dumps({"ok": False, "message": "BBS non attivo"})

        mc = bbs.connection._meshcore
        if not mc:
            return json.dumps({"ok": False, "message": "Radio non connessa"})

        # Get time from companion (async from thread)
        future = asyncio.run_coroutine_threadsafe(
            mc.commands.get_time(), loop
        )
        result = future.result(timeout=10)

        if result is None or result.payload is None:
            return json.dumps({"ok": False, "message": "Nessuna risposta dal companion"})

        companion_ts = result.payload.get("time", 0)
        server_ts = int(time.time())
        diff = companion_ts - server_ts

        # Format times
        from datetime import datetime as dt
        companion_str = dt.utcfromtimestamp(companion_ts).strftime("%H:%M:%S UTC") if companion_ts else "N/A"
        server_str = dt.utcfromtimestamp(server_ts).strftime("%H:%M:%S UTC")

        return json.dumps({
            "ok": True,
            "companion_time": companion_str,
            "companion_timestamp": companion_ts,
            "server_time": server_str,
            "server_timestamp": server_ts,
            "diff_seconds": diff,
        })

    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


@app.route("/api/companion-time/sync", method="POST")
@require_auth
def api_sync_companion_time():
    """Sync companion radio time with server (Pi) time."""
    response.content_type = "application/json"
    try:
        from bbs.runtime import get_bbs_instance, get_event_loop
        import asyncio

        bbs = get_bbs_instance()
        loop = get_event_loop()

        if not bbs or not bbs._running or not loop:
            return json.dumps({"ok": False, "message": "BBS non attivo"})

        mc = bbs.connection._meshcore
        if not mc:
            return json.dumps({"ok": False, "message": "Radio non connessa"})

        # Set companion time to current server time
        server_ts = int(time.time())
        future = asyncio.run_coroutine_threadsafe(
            mc.commands.set_time(server_ts), loop
        )
        result = future.result(timeout=10)

        from datetime import datetime as dt
        time_str = dt.utcfromtimestamp(server_ts).strftime("%H:%M:%S UTC")

        return json.dumps({
            "ok": True,
            "message": f"Orologio sincronizzato: {time_str}",
        })

    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


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

@app.route("/api/send-message", method="POST")
@require_auth
def api_send_message():
    """Send a private message to a mesh node."""
    response.content_type = "application/json"
    try:
        from bbs.runtime import get_bbs_instance, get_event_loop
        import asyncio

        data = request.json or {}
        recipient_key = data.get("recipient_key", "").strip()
        text = data.get("text", "").strip()

        if not recipient_key or not text:
            return json.dumps({"ok": False, "message": "Destinatario e testo richiesti"})

        if len(text) > 140:
            return json.dumps({"ok": False, "message": f"Messaggio troppo lungo ({len(text)}/140)"})

        bbs = get_bbs_instance()
        loop = get_event_loop()

        if not bbs or not bbs._running:
            return json.dumps({"ok": False, "message": "BBS non attivo"})
        if not loop:
            return json.dumps({"ok": False, "message": "Event loop non disponibile"})

        # Send message via the BBS connection
        future = asyncio.run_coroutine_threadsafe(
            bbs.connection.send_message(destination=recipient_key, text=text),
            loop
        )
        success = future.result(timeout=15)

        if success:
            logger.info(f"Message sent to {recipient_key[:8]} via web: {text[:30]}...")
            return json.dumps({"ok": True, "message": "Messaggio inviato"})
        else:
            return json.dumps({"ok": False, "message": "Invio fallito"})

    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


@app.route("/api/message/<msg_id:int>", method="DELETE")
@require_auth
def api_delete_message(msg_id):
    """Delete a message by ID."""
    response.content_type = "application/json"
    try:
        from bbs.models.base import get_session
        from bbs.models.message import Message

        with get_session() as session:
            msg = session.query(Message).filter_by(id=msg_id).first()
            if not msg:
                return json.dumps({"ok": False, "message": f"Messaggio #{msg_id} non trovato"})

            session.delete(msg)
            session.commit()
            logger.info(f"Message #{msg_id} deleted via web admin")
            return json.dumps({"ok": True, "message": f"Messaggio #{msg_id} eliminato"})

    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


@app.route("/api/broadcast", method="POST")
@require_auth
def api_send_broadcast():
    """Send a message on the public channel."""
    response.content_type = "application/json"
    try:
        from bbs.runtime import get_bbs_instance, get_event_loop
        import asyncio

        data = request.json or {}
        msg = data.get("message", "").strip()

        if not msg:
            return json.dumps({"ok": False, "message": "Messaggio vuoto"})

        if len(msg) > 140:
            return json.dumps({"ok": False, "message": f"Messaggio troppo lungo ({len(msg)}/140)"})

        bbs = get_bbs_instance()
        loop = get_event_loop()

        if not bbs or not bbs._running:
            return json.dumps({"ok": False, "message": "BBS non attivo"})
        if not loop:
            return json.dumps({"ok": False, "message": "Event loop non disponibile"})

        mc = bbs.connection._meshcore
        if not mc:
            return json.dumps({"ok": False, "message": "Radio non connessa"})

        future = asyncio.run_coroutine_threadsafe(
            mc.commands.send_chan_msg(msg), loop
        )
        future.result(timeout=15)

        logger.info(f"Broadcast sent on channel: {msg[:50]}...")
        return json.dumps({"ok": True, "message": "Messaggio inviato sul canale"})

    except Exception as e:
        return json.dumps({"ok": False, "message": str(e)})


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
        from bbs.runtime import get_bbs_instance, get_event_loop
        import asyncio

        bbs = get_bbs_instance()
        if bbs is None or not bbs._running:
            return []

        mc = bbs.connection._meshcore
        if mc is None:
            return []

        # Refresh contacts from the radio (must run in the async loop)
        loop = get_event_loop()
        if loop is not None:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    mc.commands.get_contacts(), loop
                )
                future.result(timeout=10)
            except Exception:
                pass  # Use cached contacts

        contacts = mc.contacts or {}

        # First pass: build repeater lookup by path hash prefix
        repeaters = {}
        for key, info in contacts.items():
            if info.get("type") == 2:  # RPT
                pub_key = info.get("public_key", key)
                if isinstance(pub_key, bytes):
                    pub_key = pub_key.hex()
                name = info.get("adv_name", "") or info.get("name", pub_key[:8])
                repeaters[pub_key[:8]] = name

        # Second pass: build node list with route info
        nodes = []
        for key, info in contacts.items():
            node_type = NODE_TYPES.get(info.get("type", 0), "?")
            name = info.get("adv_name", "") or info.get("name", key[:8] if isinstance(key, str) else "?")
            pub_key = info.get("public_key", key)
            if isinstance(pub_key, bytes):
                pub_key = pub_key.hex()

            # Determine route
            out_path_len = info.get("out_path_len", 0)
            out_path = info.get("out_path", "")

            if out_path_len and out_path_len > 0 and out_path:
                # Node communicates via repeater(s)
                # Try to match path hash with known repeaters
                path_parts = []
                # out_path is hex string of hop hashes
                hash_mode = info.get("out_path_hash_mode", 1)
                hash_size = (hash_mode + 1) if hash_mode >= 0 else 2
                for i in range(0, len(out_path), hash_size * 2):
                    hop_hash = out_path[i:i + hash_size * 2]
                    if hop_hash and hop_hash != "00" * hash_size:
                        # Try to find matching repeater
                        matched = False
                        for rpt_key, rpt_name in repeaters.items():
                            if rpt_key.startswith(hop_hash) or hop_hash in rpt_key:
                                path_parts.append(rpt_name)
                                matched = True
                                break
                        if not matched:
                            path_parts.append(f"hop:{hop_hash[:6]}")

                if path_parts:
                    path = "via " + " > ".join(path_parts)
                else:
                    path = f"{out_path_len} hop"
            else:
                path = "diretto"

            node_data = {
                "name": name,
                "type": node_type,
                "key": str(pub_key),
                "path": path,
                "hops": out_path_len if out_path_len and out_path_len > 0 else 0,
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
    msgs, _ = _get_messages_paginated(1, limit)
    return msgs


def _get_messages_paginated(page_num=1, per_page=25):
    """Get messages with pagination. Returns (messages_list, total_count)."""
    try:
        from bbs.models.base import get_session
        from bbs.models.message import Message

        with get_session() as session:
            total = session.query(Message).count()
            offset = (page_num - 1) * per_page
            messages = (
                session.query(Message)
                .order_by(Message.timestamp.desc())
                .offset(offset)
                .limit(per_page)
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
            return result, total
    except Exception as e:
        logger.error(f"Error fetching messages: {e}")
        return [], 0


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


def _format_bytes(num_bytes):
    """Format bytes to human readable string."""
    if not num_bytes:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}" if unit != "B" else f"{num_bytes} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


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


def _render_activity_chart():
    """Render a CSS bar chart showing messages and adverts per hour (last 24h)."""
    try:
        from bbs.models.base import get_session
        from bbs.models.message import Message
        from bbs.models.activity_log import ActivityLog

        with get_session() as session:
            now = datetime.utcnow()
            hours_data = []

            for i in range(23, -1, -1):
                hour_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=i)
                hour_end = hour_start + timedelta(hours=1)

                msg_count = session.query(Message).filter(
                    Message.timestamp >= hour_start,
                    Message.timestamp < hour_end,
                ).count()

                adv_count = session.query(ActivityLog).filter(
                    ActivityLog.timestamp >= hour_start,
                    ActivityLog.timestamp < hour_end,
                    ActivityLog.event_type == "ADVERT_SENT",
                ).count()

                hours_data.append((hour_start.strftime("%H"), msg_count, adv_count))

            max_val = max((m + a for _, m, a in hours_data), default=1) or 1

            bars = ""
            for hour, msg_count, adv_count in hours_data:
                msg_h = max(1, int(msg_count / max_val * 60))
                adv_h = max(0, int(adv_count / max_val * 60))
                total_title = f"{hour}:00 - {msg_count} msg, {adv_count} adv"

                bars += (
                    f'<div style="display:inline-block;width:3.5%;margin:0 0.3%;vertical-align:bottom" title="{total_title}">'
                    f'<div style="height:{adv_h}px;background:#fbbf24;border-radius:2px 2px 0 0"></div>'
                    f'<div style="height:{msg_h}px;background:#3b82f6;border-radius:{("0" if adv_h else "2px 2px")} 0 0"></div>'
                    f'<div style="font-size:0.55rem;color:#64748b;text-align:center">{hour}</div>'
                    f'</div>'
                )

            total_msg = sum(m for _, m, _ in hours_data)
            total_adv = sum(a for _, _, a in hours_data)

            legend = (
                '<div style="margin-top:0.5rem;font-size:0.7rem;color:#94a3b8">'
                '<span style="display:inline-block;width:10px;height:10px;background:#3b82f6;border-radius:2px;margin-right:3px;vertical-align:middle"></span>Messaggi '
                '<span style="display:inline-block;width:10px;height:10px;background:#fbbf24;border-radius:2px;margin-right:3px;margin-left:8px;vertical-align:middle"></span>Advert'
                '</div>'
            )

            return f"""
            <div class="section">
            <h2>Attivita 24h <span style="font-size:0.75rem;color:#64748b;font-weight:normal">({total_msg} msg, {total_adv} adv)</span></h2>
            <div class="card" style="padding:0.75rem">
                <div style="height:80px;display:flex;align-items:flex-end">{bars}</div>
                {legend}
            </div>
            </div>
            """
    except Exception:
        return ""


# Track last seen repeaters for alerts
_last_seen_repeaters = {}  # name -> timestamp


def _render_repeater_alerts():
    """Check for missing repeaters and render alert if any disappeared."""
    global _last_seen_repeaters

    try:
        nodes = _get_mesh_nodes()
        current_rpts = {n["name"]: n for n in nodes if n["type"] == "RPT"}
        now = time.time()

        # Update last seen
        for name in current_rpts:
            _last_seen_repeaters[name] = now

        # Check for missing repeaters (seen before but not now)
        alerts = []
        for name, last_seen in list(_last_seen_repeaters.items()):
            if name not in current_rpts and now - last_seen < 86400:  # within 24h
                minutes_ago = int((now - last_seen) / 60)
                if minutes_ago > 5:  # only alert after 5 min
                    alerts.append(f"{name} non visto da {minutes_ago}m")

        if not alerts:
            return ""

        alert_items = "".join(f"<li>{a}</li>" for a in alerts)
        return f"""
        <div class="card" style="border-color:#7f1d1d;margin-bottom:1rem">
            <h3 style="color:#f87171">Repeater non raggiungibili</h3>
            <ul style="margin:0.5rem 0 0 1rem;font-size:0.85rem">{alert_items}</ul>
        </div>
        """
    except Exception:
        return ""


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
