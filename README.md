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
- **User Management**: Nicknames, roles (admin/moderator), ban/mute/kick
- **Welcome Message**: Messaggio di benvenuto automatico al primo contatto
- **Role-aware Help**: `!help` mostra comandi diversi per utenti e admin
- **Area Management**: Create, edit, delete discussion areas
- **Privacy & GDPR**: Retention policies, ephemeral messages, data transparency
- **Rate Limiting**: Anti-spam protection with configurable limits
- **Beacon Broadcast**: Messaggio periodico sulla mesh (configurabile)
- **Smart Chunking**: Risposte lunghe spezzate automaticamente (140 bytes max)

### Web Administration (Lightweight)
- **Unified Launcher**: Single command to start BBS + Web (`python launcher.py`)
- **Lightweight Web UI**: bottle.py (zero compiled dependencies, runs on Pi Zero)
- **Dashboard**: Stats, grafico attivita 24h (messaggi + advert), radio status
- **User Management**: Ban, unban, mute, kick, promuovi/declassa da web
- **Message Viewer**: Lista messaggi con auto-refresh
- **Network Map**: Mappa Leaflet con nodi mesh raggruppati per tipo, hop e percorso repeater
- **Repeater Alerts**: Notifica quando un repeater scompare dalla rete
- **Settings Page**: Modifica config BBS dalla web (nome, coordinate, beacon, retention)
- **Activity Logs**: Log sistema con auto-refresh
- **Connection Indicator**: Pallino verde/rosso nella navbar
- **Mobile Responsive**: Menu hamburger, tabelle scrollabili, layout adattivo
- **BBS Control**: Invio advertisement manuale dalla dashboard

### Integrations
- **MeshCore Hardware**: Full support via meshcore_py library (Serial, BLE, TCP)
- **MQTT**: Publish BBS events and statistics for home automation (Home Assistant, Node-RED)
- **Statistics API**: Unified stats endpoint (`GET /api/v1/stats`) and periodic MQTT publishing
- **Backup System**: Automatic scheduled backups
- **Send Throttling**: Chunked message sending with configurable delay to prevent message loss on slow radio links

## Requirements

- Python 3.9+
- MeshCore companion radio (Serial or TCP)
- SQLite 3
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

# Setup web interface
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

Default credentials: `admin` / `meshbbs123`

### Development Mode (No Hardware)

```bash
cd src
python launcher.py --debug
```

## Command Line Options

```
usage: launcher.py [-h] [--tcp] [--tcp-host HOST] [--tcp-port PORT]
                   [-p PORT] [-b BAUD] [-d DATABASE] [-n NAME]
                   [--web-host HOST] [--web-port PORT]
                   [--web-only] [--bbs-only] [--debug]

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
  --debug               Enable debug logging
```

## BBS Commands

Users interact with the BBS by sending commands via MeshCore messages.
The `!help` command shows different commands based on the user's role (user/admin).

### Basic Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!help` | Comandi disponibili (diversi per ruolo) | `!help` |
| `!help <cmd>` | Dettaglio comando | `!help post` |
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
| `!mail <user> <ogg> \| <corpo>` | Invia mail con oggetto | `!mail Mario Riunione \| Domani alle 10` |
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
| `!msg! <user> <msg>` | PM effimero (non salvato) | `!msg! Mario Segreto` |
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
| `!stats` | Statistiche BBS | `!stats` |
| `!info` | Informazioni BBS | `!info` |
| `!mydata` | Dati personali | `!mydata` |
| `!gdpr` | Informazioni privacy | `!gdpr` |

### Admin Commands (visibili solo agli admin via `!help`)

| Command | Description | Example |
|---------|-------------|---------|
| `!ban/unban <user>` | Banna/sbanna utente | `!ban spammer Spam` |
| `!mute/unmute <user>` | Silenzia/ripristina utente | `!mute Mario Offtopic` |
| `!kick/unkick <user> [min]` | Espelli temporaneamente | `!kick Mario 30` |
| `!promote/demote <user>` | Promuovi/declassa | `!promote Mario` |
| `!staff` | Lista staff | `!staff` |
| `!advert` | Invia advertisement manuale | `!advert` |
| `!nodes` | Nodi e repeater sulla rete | `!nodes` |
| `!newarea/delarea <name>` | Crea/elimina area | `!newarea gaming` |
| `!editarea <name> <prop> <val>` | Modifica area | `!editarea tech desc Tech` |
| `!cleanup` | Pulizia dati scaduti | `!cleanup --dry-run` |

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

### Database Encryption (Optional)
SQLCipher support for encrypting the database at rest. Set `BBS_DATABASE_KEY` environment variable.

## @Mentions

Users can mention others in messages using `@nickname`:
```
/post Hey @Mario, check this out!
```

When mentioned:
- User sees the mention in their `/inbox`
- Shows who mentioned them, in which area, and the message excerpt
- Includes a direct link to read the full message
- Mentions disappear after viewing (like ephemeral messages)

Mention rules:
- Nicknames must be 2-20 characters
- Case insensitive (@MARIO = @mario)
- You won't be notified for mentioning yourself
- Banned users don't receive mentions

## Rate Limiting

The BBS includes anti-spam protection:
- **Minimum interval**: 1 second between commands
- **Max per minute**: 30 commands per minute
- **Block duration**: 60 seconds when limit exceeded
- **Admin bypass**: Admins skip rate limiting

Rate limit messages are shown in Italian:
- "Troppo veloce. Attendi un momento"
- "Limite comandi superato. Bloccato per 60s"

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BBS_SERIAL_PORT` | `/dev/ttyUSB0` | Serial port for radio |
| `BBS_BAUD_RATE` | `115200` | Serial baud rate |
| `BBS_DATABASE_PATH` | `data/bbs.db` | Database file path |
| `BBS_DATABASE_KEY` | (none) | SQLCipher encryption key |
| `BBS_LOG_PATH` | `logs/bbs.log` | Log file path |
| `BBS_LOG_LEVEL` | `INFO` | Log level |
| `BBS_NAME` | `MeshCore BBS` | BBS display name |
| `BBS_DEFAULT_AREA` | `generale` | Default message area |
| `BBS_LATITUDE` | (none) | BBS latitude (-90/+90) |
| `BBS_LONGITUDE` | (none) | BBS longitude (-180/+180) |
| `BBS_PM_RETENTION_DAYS` | `30` | Days to keep PMs (0=forever) |
| `BBS_LOG_RETENTION_DAYS` | `90` | Days to keep logs (0=forever) |
| `BBS_ALLOW_EPHEMERAL_PM` | `true` | Enable !msg! command |
| `SEND_DELAY` | `3.0` | Seconds between response chunks |
| `MAX_SEND_ATTEMPTS` | `2` | Max send retry attempts |
| `SEND_RETRY_DELAY` | `2.0` | Base seconds between retries |
| `STATS_PUBLISH_INTERVAL` | `300` | Seconds between MQTT stats publish |
| `MQTT_ENABLED` | `false` | Enable MQTT integration |
| `MQTT_HOST` | `localhost` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for the full list.

## Project Structure

```
MeshBBS/
├── src/
│   ├── launcher.py              # Unified launcher (BBS + Web)
│   ├── main.py                  # Legacy BBS-only entry point
│   ├── bbs/
│   │   ├── core.py              # Main BBS logic + chunked send (160 byte MTU)
│   │   ├── runtime.py           # Shared state between BBS and web threads
│   │   ├── scheduler.py         # Background task scheduler
│   │   ├── rate_limiter.py      # Anti-spam rate limiting
│   │   ├── mentions.py          # @mention notification system
│   │   ├── privacy.py           # Privacy/GDPR utilities
│   │   ├── commands/            # Command handlers
│   │   │   ├── base.py          # Base command class + registry
│   │   │   ├── dispatcher.py    # Command routing + welcome message
│   │   │   ├── help_cmd.py      # Role-aware help (user/admin)
│   │   │   ├── news_cmd.py      # RSS feed reader (ANSA)
│   │   │   ├── advert_cmd.py    # Manual mesh advertisement (admin)
│   │   │   ├── nodes_cmd.py     # Mesh network nodes/repeaters (admin)
│   │   │   └── ...              # post, list, read, msg, nick, search, etc.
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── repositories/        # Data access layer
│   │   └── services/
│   │       └── stats_collector.py  # Unified stats collection
│   ├── meshbbs_radio/           # MeshCore protocol (renamed to avoid pip conflict)
│   │   ├── connection.py        # Serial, BLE, TCP, Mock connections
│   │   ├── messages.py          # Message types
│   │   ├── protocol.py          # Protocol definitions
│   │   └── state.py             # Connection state manager
│   ├── utils/
│   │   ├── config.py            # Configuration with persistence
│   │   ├── logger.py            # Logging setup
│   │   └── mqtt.py              # MQTT client integration
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

SQLite with SQLAlchemy ORM (optional SQLCipher encryption). Tables:

- `users` - User profiles keyed by MeshCore public key
- `areas` - Message board areas/topics
- `messages` - Public messages with threading support
- `private_messages` - Direct messages between users
- `activity_log` - System event log
- `delivery_status` - Message delivery tracking (pending/sent/delivered/failed)

Note: MeshCore provides E2E encryption for messages in transit. The BBS receives messages already decrypted by the companion radio. For additional protection, enable SQLCipher database encryption.

### Mock Connection

For development without hardware, `MockMeshCoreConnection` simulates:
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
- [API Documentation](docs/API.md) - REST API reference
- [Plugin Guide](docs/PLUGINS.md) - Plugin development
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
