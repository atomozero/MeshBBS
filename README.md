# MeshCore BBS

A Bulletin Board System for MeshCore LoRa mesh networks.

## Overview

MeshCore BBS provides classic BBS functionality over MeshCore mesh networks. It allows users on the mesh to post public messages, send private messages, and participate in discussion areas.

## Features

### Core BBS
- **Public Message Boards**: Post and read messages in themed discussion areas
- **Private Messaging**: Direct messages between users with optional ephemeral mode
- **Mail System**: Email-like messages with subject (`!mail`)
- **Bulletin Board**: Persistent announcements board (`!board`)
- **News RSS**: Feed news ANSA con cache (`!news`)
- **Weather**: Previsioni meteo via Open-Meteo API (`!meteo`)
- **Trivia Game**: Quiz a risposta multipla con classifica (`!trivia`)
- **Fortune**: Citazioni e curiosita casuali (`!fortune`)
- **User Management**: Nicknames, roles (admin/moderator), ban/mute/kick (moderators can kick/mute/delete)
- **Welcome Message**: Messaggio di benvenuto automatico al primo contatto
- **Categorized Help**: `!help` mostra i comandi essenziali e le categorie (`forum`, `posta`, `utili`, `giochi`, `mod`), filtrati per ruolo
- **Area Management**: Create, edit, delete discussion areas
- **Privacy & GDPR**: Retention policies, ephemeral messages, data transparency
- **Rate Limiting**: Anti-spam protection (1 cmd/s, 30 cmd/min; admins exempt)
- **Beacon Broadcast**: Messaggio periodico sulla mesh (configurabile)
- **Smart Chunking**: Risposte lunghe spezzate automaticamente (140 byte max, UTF-8 safe)
- **Resilient Radio Link**: Il BBS parte anche con radio offline e si riconnette da solo (backoff 5s → 300s, probe ogni 150s)

### Web Administration (Lightweight)
- **Unified Launcher**: Single command to start BBS + Web (`python launcher.py`)
- **Lightweight Web UI**: bottle.py (zero compiled dependencies, runs on Pi Zero)
- **Dashboard**: Stats, grafico attivita 24h (messaggi + advert), radio status
- **User Management**: Ban, unban, mute, kick, promuovi/declassa da web
- **Message Viewer**: Lista messaggi con auto-refresh
- **Network Map**: Mappa Leaflet con nodi mesh raggruppati per tipo, hop e percorso repeater
- **Repeater Alerts**: Notifica quando un repeater scompare dalla rete
- **Secure Login**: Password obbligatoria, sessioni con scadenza, CSRF, cookie HttpOnly/SameSite
- **Settings Page**: Modifica config BBS dalla web (nome, coordinate, beacon, retention)
- **Activity Logs**: Log sistema con auto-refresh
- **Connection Indicator**: Pallino verde/rosso nella navbar
- **Mobile Responsive**: Menu hamburger, tabelle scrollabili, layout adattivo
- **BBS Control**: Invio advertisement manuale dalla dashboard

### Integrations
- **MeshCore Hardware**: Support via meshcore_py library (Serial, TCP). BLE: *non ancora attivo* (not selectable from the launcher)
- **Statistics API**: Stats endpoint `GET /api/stats` on the web panel
- **Send Throttling**: Chunked message sending with configurable delay to prevent message loss on slow radio links

### Experimental / non ancora attivo

The following modules exist in the source tree but are **not wired into the launcher yet**.
Configuring them has no effect at the moment:

- **MQTT** (`utils/mqtt.py`): the client is created but never connected, so no events/stats are published
- **Plugins** (`bbs/plugins/`): `PluginManager` is never instantiated, plugins are not loaded
- **Scheduled backups** (`utils/backup.py`): the backup scheduler is not started (PM/log retention cleanup *is* active)
- **SQLCipher encryption**: `BBS_DATABASE_KEY` is read but not applied, the database is plain SQLite
- **BLE connection**: implemented in `meshbbs_radio`, not selectable from `launcher.py`
- **Delivery tracking** (`delivery_status` table): not fed by the send path

## Requirements

- Python 3.9+
- MeshCore companion radio (Serial or TCP)
- SQLite 3
- `feedparser` for `!news` (included in `requirements.txt` / `requirements-light.txt`)
- Nessun Node.js richiesto (web UI leggera con bottle.py)

## Installation

### Quick Install (Raspberry Pi)

```bash
# Clone the repository
git clone https://github.com/atomozero/MeshBBS.git
cd MeshBBS

# Run automated installer
sudo ./deploy/install.sh
```

The installer generates a random web admin password and prints it once at the end (it is stored as `ADMIN_PASSWORD` in `/var/lib/meshbbs/config.env`).

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for detailed instructions.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/atomozero/MeshBBS.git
cd MeshBBS

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: legacy React admin UI (not needed for the lightweight panel)
cd web
npm install
npm run dev
```

## Quick Start

### Unified Launcher (Recommended)

Start both BBS radio service and web admin in a single command:

```bash
cd src

# TCP connection (WiFi companion)
python launcher.py --tcp --tcp-host 192.168.1.100 --tcp-port 5000 -n "My BBS"

# Serial connection (USB companion)
python launcher.py -p /dev/ttyUSB0 -n "My BBS"

# Other options
python launcher.py --web-only                  # Web server only
python launcher.py --bbs-only                  # BBS radio only
python launcher.py --web-port 9090 --debug     # Custom port + debug
```

Access the admin panel at http://localhost:8080

### Admin Password

There is **no default password**. The web login stays disabled until
`ADMIN_PASSWORD` is set to a non-default value (an unset value, `meshbbs123`
or the documentation placeholders are refused, and the login page explains why).

- `deploy/install.sh` generates a random password, writes it to
  `/var/lib/meshbbs/config.env` and prints it **once** at the end of the install
- for a manual/development setup, export it before starting:

```bash
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD='a-long-random-password'
```

Sessions expire after `WEB_SESSION_TTL` seconds of inactivity (default 8 hours).

### Development Mode (No Hardware)

```bash
cd src
python launcher.py --mock --debug
```

`--mock` lets the BBS fall back to a simulated radio when the real one is not
reachable. It is **for development only**: without `--mock` (production) the BBS
never switches to the mock, it starts anyway and keeps retrying the real radio
in background (backoff 5s → 300s).

## Command Line Options

```
usage: launcher.py [-h] [--tcp] [--tcp-host HOST] [--tcp-port PORT]
                   [-p PORT] [-b BAUD] [-d DATABASE] [-n NAME]
                   [--web-host HOST] [--web-port PORT]
                   [--web-only] [--bbs-only] [--mock] [--debug]
                   [--log-file PATH] [--version]

options:
  --tcp                 Use TCP connection instead of serial
  --tcp-host HOST       TCP host (default: 192.168.1.100)
  --tcp-port PORT       TCP port (default: 5000)
  -p, --port PORT       Serial port (default: /dev/ttyUSB0)
  -b, --baud BAUD       Baud rate (default: 115200)
  -d, --database PATH   Database path (default: data/bbs.db)
  -n, --name NAME       BBS name (default: MeshCore BBS)
  --web-host HOST       Web server bind (default: 0.0.0.0)
  --web-port PORT       Web server port (default: 8080)
  --web-only            Start web server only
  --bbs-only            Start BBS radio only
  --mock                Development only: simulated radio fallback
  --debug               Enable debug logging
  --log-file PATH       Log file path (default: logs/bbs.log)
```

## BBS Commands

Users interact with the BBS by sending commands via MeshCore messages.
All commands use the `!` prefix.

### Help

`!help` is kept short (every line costs airtime): it lists the essential
commands and the available categories. Commands the sender cannot use are hidden.

| Command | Description | Example |
|---------|-------------|---------|
| `!help` | Comandi essenziali + categorie | `!help` |
| `!help <categoria>` | Comandi di una categoria: `forum`, `posta`, `utili`, `giochi`, `mod` | `!help posta` |
| `!help tutti` | Tutti i comandi disponibili per il proprio ruolo | `!help tutti` |
| `!help <cmd>` | Descrizione e uso di un comando | `!help post` |

Category aliases: `messaggi` = `posta`, `games` = `giochi`, `moderazione` = `mod`, `all` = `tutti`.
The `mod` category is shown only to moderators and admins.

### Basic Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!areas` | Lista aree | `!areas` |
| `!list [n]` | Ultimi messaggi | `!list 10` |
| `!read <id>` | Leggi messaggio | `!read 5` |
| `!post [#area] <msg>` | Pubblica messaggio | `!post #tech Ciao!` |
| `!reply <id> <msg>` | Rispondi a messaggio | `!reply 5 Grazie!` |
| `!search [#area] <term>` | Cerca messaggi | `!search errore` |
| `!nick <name>` | Imposta nickname | `!nick Mario` |
| `!who [hours]` | Utenti attivi | `!who 24` |
| `!ping` | Test connessione (hop, RSSI) | `!ping` |

### News & Meteo

| Command | Description | Example |
|---------|-------------|---------|
| `!news` | Ultime notizie ANSA | `!news` |
| `!news <feed>` | Notizie da feed specifico | `!news ansa-tech` |
| `!news <n>` | Dettaglio notizia (sommario completo) | `!news 3` |
| `!news list` | Feed RSS disponibili | `!news list` |
| `!meteo [citta]` | Previsioni meteo 3 giorni | `!meteo Roma` |

### Mail & Bacheca

| Command | Description | Example |
|---------|-------------|---------|
| `!mail <user> <ogg> \| <corpo>` | Invia mail con oggetto (oggetto max 40, corpo max 200 caratteri) | `!mail Mario Riunione \| Domani alle 10` |
| `!mailbox` | Casella mail | `!mailbox` |
| `!readmail <id>` | Leggi mail | `!readmail 5` |
| `!delmail <id>` | Elimina mail | `!delmail 5` |
| `!board` | Bacheca annunci | `!board` |
| `!board post <testo>` | Pubblica annuncio | `!board post Riunione domani` |
| `!board read <id>` | Leggi annuncio | `!board read 3` |

### Private Messages

| Command | Description | Example |
|---------|-------------|---------|
| `!msg <user> <msg>` | Messaggio privato | `!msg Mario Ciao!` |
| `!msg! <user> <msg>` | PM effimero (non salvato, se `BBS_ALLOW_EPHEMERAL_PM=true`) | `!msg! Mario Segreto` |
| `!inbox [n]` | Posta in arrivo | `!inbox` |
| `!readpm <id>` | Leggi PM | `!readpm 3` |
| `!delpm <id>` | Elimina PM | `!delpm 3` |
| `!clear` | Segna tutti PM letti | `!clear` |

### Giochi & Fun

| Command | Description | Example |
|---------|-------------|---------|
| `!trivia` | Domanda quiz casuale | `!trivia` |
| `!trivia A/B/C` | Rispondi alla domanda | `!trivia B` |
| `!trivia score` | Tuo punteggio | `!trivia score` |
| `!trivia top` | Classifica top 5 | `!trivia top` |
| `!fortune` | Citazione/curiosita casuale | `!fortune` |

### User Info

| Command | Description | Example |
|---------|-------------|---------|
| `!whois <user>` | Profilo utente | `!whois Mario` |
| `!staff` | Lista admin e moderatori | `!staff` |
| `!stats` | Statistiche BBS | `!stats` |
| `!info` | Informazioni BBS | `!info` |
| `!mydata` | Dati personali | `!mydata` |
| `!gdpr` | Informazioni privacy | `!gdpr` |

### Moderation & Admin Commands (`!help mod`)

| Command | Who | Description | Example |
|---------|-----|-------------|---------|
| `!kick/unkick <user> [min]` | mod, admin | Espelli temporaneamente (min > 0) | `!kick Mario 30` |
| `!mute/unmute <user>` | mod, admin | Silenzia/ripristina utente | `!mute Mario Offtopic` |
| `!delete <id>` | autore, mod, admin | Elimina messaggio | `!delete 42` |
| `!board del <id>` | autore, mod, admin | Elimina annuncio | `!board del 3` |
| `!ban/unban <user>` | admin | Banna/sbanna utente | `!ban spammer Spam` |
| `!promote/demote <user>` | admin | Promuovi/declassa | `!promote Mario` |
| `!advert` | admin | Invia advertisement manuale | `!advert` |
| `!nodes` | admin | Nodi e repeater sulla rete | `!nodes` |
| `!newarea/delarea <name>` | admin | Crea/elimina area (`!delarea` elimina anche i messaggi; l'area predefinita è protetta) | `!newarea gaming` |
| `!editarea <name> <prop> <val>` | admin | Modifica area (`desc`, `readonly`, `public`) | `!editarea tech desc Tech` |
| `!listareas` | admin | Tutte le aree, incluse quelle nascoste | `!listareas` |
| `!cleanup` | admin | Pulizia dati scaduti | `!cleanup --dry-run` |

`!staff` (lista staff) is available to everyone.

User arguments (`<user>`) accept either the exact nickname (case-insensitive)
or a public key prefix of **at least 8 hex characters**; an ambiguous prefix
is refused.

## Privacy & GDPR

MeshCore BBS includes privacy features for GDPR compliance:

### Data Retention
- **Private Messages**: Automatically deleted after 30 days (configurable)
- **Activity Logs**: Automatically deleted after 90 days (configurable)
- **Manual Cleanup**: Admins can run `!cleanup` to purge old data

### Ephemeral Messages
Users can send private messages that are NOT saved to the database:
```
!msg! Mario Questo messaggio non viene salvato
```

### User Rights
- `!mydata` - I tuoi dati salvati
- `!gdpr` - Informazioni privacy e retention
- `!delpm <id>` - Elimina messaggi privati

### Database Encryption (non ancora attivo)
SQLCipher encryption at rest is planned but **not applied yet**: `BBS_DATABASE_KEY`
is read from the environment but the database is opened as plain SQLite.
Protect the database file with filesystem permissions (`chmod 600`).

### Activity Log
Private message bodies are never written to the activity log.

## @Mentions

Users can mention others in messages using `@nickname`:
```
!post Hey @Mario, check this out!
```

When mentioned:
- User sees the mention in their `!inbox`
- Shows who mentioned them, in which area, and the message excerpt
- Includes a direct link to read the full message
- Mentions disappear after viewing (like ephemeral messages)

Mention rules:
- Nicknames must be 2-16 characters (letters, digits, `_` and `-`)
- Case insensitive (@MARIO = @mario)
- You won't be notified for mentioning yourself
- Banned users don't receive mentions

## Users & Identity

MeshCore DMs carry only a 6-byte public key prefix, so the BBS uses one
**canonical user key**: the lowercase 12-hex-character prefix of the public key.
At startup an idempotent migration (`normalize_user_keys`) converts users saved
with the full 64-character key and merges duplicates, updating all references.
No manual action is needed after upgrading.

Nickname rules:
- 2-16 characters, letters, digits, `_` and `-`
- Unique, case-insensitive (`Mario` and `mario` are the same nick)
- Nicknames that look like a hex key prefix (6+ hex chars) are refused, to prevent impersonation
- Lookups by nickname and area name are exact and case-insensitive (no wildcards)

## Rate Limiting

The BBS includes anti-spam protection:
- **Minimum interval**: 1 second between commands
- **Max per minute**: 30 commands per minute
- **Block duration**: 60 seconds when limit exceeded
- **Admin bypass**: Admins skip rate limiting (role checked on every command)

Rate limit messages are shown in Italian:
- "Troppo veloce. Attendi un momento"
- "Limite comandi superato. Bloccato per 60s"

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BBS_SERIAL_PORT` | `/dev/ttyUSB0` | Serial port for radio |
| `BBS_BAUD_RATE` | `115200` | Serial baud rate |
| `BBS_DATABASE_PATH` | `data/bbs.db` | Database file path |
| `BBS_DATABASE_KEY` | (none) | SQLCipher key (*non ancora attivo*: not applied) |
| `BBS_LOG_PATH` | `logs/bbs.log` | Log file path |
| `BBS_LOG_LEVEL` | `INFO` | Log level |
| `BBS_NAME` | `MeshCore BBS` | BBS display name |
| `BBS_DEFAULT_AREA` | `generale` | Default message area |
| `BBS_LATITUDE` | (none) | BBS latitude (-90/+90) |
| `BBS_LONGITUDE` | (none) | BBS longitude (-180/+180) |
| `BBS_PM_RETENTION_DAYS` | `30` | Days to keep PMs (0=forever) |
| `BBS_LOG_RETENTION_DAYS` | `90` | Days to keep logs (0=forever) |
| `BBS_ALLOW_EPHEMERAL_PM` | `true` | Enable !msg! command |
| `ADMIN_USERNAME` | `admin` | Web panel username |
| `ADMIN_PASSWORD` | (none) | Web panel password. **Required**: unset or default values disable the web login |
| `WEB_SESSION_TTL` | `28800` | Web session idle timeout in seconds (8h, min 60) |
| `WEB_NODES_CACHE_TTL` | `60` | Seconds the web panel caches the mesh node list (min 5) |
| `WEB_CONTACTS_REFRESH` | `60` | Min seconds between contact refreshes from the radio (min 10) |
| `STATS_PUBLISH_INTERVAL` | `300` | Seconds between MQTT stats publish (*non ancora attivo*) |
| `MQTT_ENABLED` | `false` | MQTT integration (*non ancora attivo*: client never connected) |
| `MQTT_HOST` | `localhost` | MQTT broker host (*non ancora attivo*) |
| `MQTT_PORT` | `1883` | MQTT broker port (*non ancora attivo*) |

Send throttling (`send_delay`, `max_send_attempts`, `send_retry_delay`) is read from
`settings.json`, not from environment variables; `send_delay` is also editable from the web `/settings` page.

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for the full list.

## Project Structure

```
MeshBBS/
├── src/
│   ├── launcher.py              # Unified launcher (BBS + Web)
│   ├── main.py                  # Legacy BBS-only entry point
│   ├── bbs/
│   │   ├── core.py              # Main BBS logic, reconnect watchdog, chunked send (140 byte)
│   │   ├── runtime.py           # Shared state between BBS and web threads
│   │   ├── scheduler.py         # Background task scheduler
│   │   ├── rate_limiter.py      # Anti-spam rate limiting
│   │   ├── mentions.py          # @mention notification system
│   │   ├── privacy.py           # Privacy/GDPR utilities
│   │   ├── commands/            # Command handlers
│   │   │   ├── base.py          # Base command class + registry
│   │   │   ├── dispatcher.py    # Command routing + welcome message
│   │   │   ├── helpers.py       # Shared argument parsing helpers
│   │   │   ├── help_cmd.py      # Categorized, role-aware help
│   │   │   ├── news_cmd.py      # RSS feed reader (ANSA)
│   │   │   ├── advert_cmd.py    # Manual mesh advertisement (admin)
│   │   │   ├── nodes_cmd.py     # Mesh network nodes/repeaters (admin)
│   │   │   └── ...              # post, list, read, msg, nick, search, etc.
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── repositories/        # Data access layer
│   │   └── services/
│   │       ├── stats_collector.py  # Unified stats collection
│   │       └── user_keys.py     # Canonical user keys + startup migration
│   ├── meshbbs_radio/           # MeshCore protocol (renamed to avoid pip conflict)
│   │   ├── connection.py        # Serial, TCP, Mock (BLE not selectable yet)
│   │   ├── messages.py          # Message types
│   │   ├── protocol.py          # Protocol definitions
│   │   └── state.py             # Connection state manager
│   ├── utils/
│   │   ├── config.py            # Configuration with persistence
│   │   ├── logger.py            # Logging setup
│   │   └── mqtt.py              # MQTT client (non ancora attivo)
│   └── web_light/               # Lightweight web admin (bottle.py)
│       ├── bottle.py            # Bottle framework (single file, zero deps)
│       └── server.py            # Web UI: dashboard, users, network map, logs
├── tests/                       # Test suite (pytest)
├── deploy/                      # Systemd services + install scripts
├── requirements-light.txt       # Minimal deps for Pi Zero
└── docs/                        # Documentation
```

## Architecture

### Message Flow

1. User sends MeshCore message to BBS node
2. `BBSCore.receive()` receives the message via `MeshCoreConnection`
3. `CommandDispatcher.dispatch()` parses and routes the command
4. Command handler processes request and returns response
5. Response sent back to user via MeshCore

### Database

SQLite with SQLAlchemy ORM. Tables:

- `users` - User profiles keyed by the canonical public key prefix (12 hex chars)
- `areas` - Message board areas/topics
- `messages` - Public messages with threading support
- `private_messages` - Direct messages between users
- `activity_log` - System event log
- `delivery_status` - Message delivery tracking (*non ancora attivo*: table exists but is not fed)

Note: MeshCore provides E2E encryption for messages in transit. The BBS receives messages already decrypted by the companion radio, so restrict access to the database file.

### Radio Link

- The BBS starts even when the companion radio is offline and retries in background with exponential backoff (5s → 300s)
- The link is actively probed every 150s; a dead link or a `DISCONNECTED` event triggers a reconnect
- Each destination has its own send worker; a long reply stops at the first failed chunk
- Radio commands are serialized by a lock, so concurrent requests never mix their replies

### Mock Connection

Only with `--mock` (development), `MockMeshCoreConnection` simulates:
- Connection lifecycle
- Message sending/receiving
- Advertisement broadcasts

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Adding New Commands

1. Create command file in `src/bbs/commands/`
2. Extend `BaseCommand` class
3. Register with `@CommandRegistry.register("commandname")`
4. Import in `src/bbs/commands/__init__.py`

Example:

```python
from .base import BaseCommand, CommandContext, CommandResult, CommandRegistry

@CommandRegistry.register
class MyCommand(BaseCommand):
    name = "mycommand"
    description = "Does something useful"
    usage = "!mycommand <arg>"

    def __init__(self, session):
        self.session = session

    async def execute(self, ctx: CommandContext, args: list) -> CommandResult:
        return CommandResult.ok(f"[BBS] Done: {' '.join(args)}")
```

## Documentation

- [Installation Guide](docs/INSTALLATION.md) - Complete setup instructions
- [Configuration Guide](docs/CONFIGURATION.md) - All configuration options
- [API Documentation](docs/API.md) - Web panel and JSON API reference
- [Plugin Guide](docs/PLUGINS.md) - Plugin development (*sperimentale*: plugins are not loaded yet)
- [Changelog](CHANGELOG.md) - Version history

## License

MIT License - Copyright (c) 2026 MeshBBS Contributors

See [LICENSE](LICENSE) for full text.

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting PRs.

## Acknowledgments

- MeshCore project for the mesh networking protocol
- The amateur radio community for inspiration
- meshcore_py library by fdlamotte
