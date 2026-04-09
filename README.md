# MeshCore BBS

A Bulletin Board System for MeshCore LoRa mesh networks.

## Overview

MeshCore BBS provides classic BBS functionality over MeshCore mesh networks. It allows users on the mesh to post public messages, send private messages, and participate in discussion areas.

## Features

### Core BBS
- **Public Message Boards**: Post and read messages in themed discussion areas
- **Private Messaging**: Direct messages between users with optional ephemeral mode
- **User Management**: Nicknames, roles (admin/moderator), ban/mute/kick
- **Area Management**: Create, edit, delete discussion areas
- **Privacy & GDPR**: Retention policies, ephemeral messages, data transparency
- **@Mentions**: Get notified when someone mentions you in a message
- **Rate Limiting**: Anti-spam protection with configurable limits
- **Background Tasks**: Automatic retention cleanup scheduler
- **Activity Logging**: Track system events and user activity
- **Mock Mode**: Development and testing without hardware

### Web Administration (NEW in v1.4)
- **React Admin Panel**: Modern responsive web interface
- **Dashboard**: Real-time statistics and activity feed
- **User Management**: View, ban, unban, mute, kick, promote users
- **Message Moderation**: Search, view, delete messages
- **Area Management**: Create, edit, delete message areas
- **System Logs**: Filter and search activity logs
- **Settings**: Configure BBS parameters
- **Dark/Light/System Theme**: Automatic theme detection

### REST API
- **FastAPI Backend**: High-performance async API
- **JWT Authentication**: Secure token-based auth with refresh
- **WebSocket**: Real-time updates for dashboard
- **OpenAPI Docs**: Auto-generated API documentation

### Integrations
- **MeshCore Hardware**: Full support via meshcore_py library
- **MQTT**: Publish BBS events for home automation
- **Backup System**: Automatic scheduled backups

## Requirements

- Python 3.11+
- Node.js 20+ (for web interface)
- MeshCore companion radio (or use mock mode for development)
- SQLite 3

## Installation

### Quick Install (Raspberry Pi)

```bash
# Clone the repository
git clone https://github.com/meshbbs/meshbbs.git
cd meshbbs

# Run automated installer
sudo ./deploy/install.sh
```

See [docs/INSTALLATION.md](docs/INSTALLATION.md) for detailed instructions.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/meshbbs/meshbbs.git
cd meshbbs

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

### Development Mode (No Hardware)

The BBS runs in mock mode by default when no hardware is available:

```bash
cd src
python main.py --debug
```

### Web Interface

Start the API server and web interface:

```bash
# Terminal 1: Start API
cd src
uvicorn web.main:app --reload --port 8080

# Terminal 2: Start frontend dev server
cd web
npm run dev
```

Access the admin panel at http://localhost:3000

Default credentials: `admin` / `meshbbs123`

### Production Mode

Connect your MeshCore companion radio and specify the serial port:

```bash
python main.py -p /dev/ttyUSB0 -n "My BBS"
```

## Command Line Options

```
usage: main.py [-h] [-p PORT] [-b BAUD] [-d DATABASE] [-n NAME] [--debug] [--log-file LOG_FILE] [--version]

MeshCore BBS - Bulletin Board System for LoRa mesh networks

options:
  -h, --help            show this help message and exit
  -p PORT, --port PORT  Serial port for companion radio (default: /dev/ttyUSB0)
  -b BAUD, --baud BAUD  Baud rate (default: 115200)
  -d DATABASE, --database DATABASE
                        Database path (default: data/bbs.db)
  -n NAME, --name NAME  BBS name (default: MeshCore BBS)
  --debug               Enable debug logging
  --log-file LOG_FILE   Log file path (default: logs/bbs.log)
  --version             show program's version number and exit
```

## BBS Commands

Users interact with the BBS by sending commands via MeshCore messages:

### Basic Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/help` | Show available commands | `/help` |
| `/help <cmd>` | Help for specific command | `/help post` |
| `/areas` | List available areas | `/areas` |
| `/list [n]` | List recent messages | `/list 10` |
| `/read <id>` | Read a message | `/read 5` |
| `/post [#area] <msg>` | Post a message | `/post #tech Hello!` |
| `/reply <id> <msg>` | Reply to a message | `/reply 5 Thanks!` |
| `/search [#area] <term>` | Search messages | `/search error` |
| `/nick <name>` | Set your nickname | `/nick John` |
| `/who [hours]` | Active users | `/who 24` |

### Private Messages

| Command | Description | Example |
|---------|-------------|---------|
| `/msg <user> <msg>` | Send private message | `/msg John Hello!` |
| `/msg! <user> <msg>` | Send ephemeral PM (not saved) | `/msg! John Secret` |
| `/inbox [n]` | View inbox | `/inbox` |
| `/readpm <id>` | Read private message | `/readpm 3` |
| `/delpm <id>` | Delete private message | `/delpm 3` |
| `/clear` | Mark all PMs as read | `/clear` |

### User Info

| Command | Description | Example |
|---------|-------------|---------|
| `/whois <user>` | User profile | `/whois John` |
| `/stats` | BBS statistics | `/stats` |
| `/info` | BBS information | `/info` |
| `/mydata` | Your stored data | `/mydata` |
| `/gdpr` | Privacy information | `/gdpr` |

### Admin Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/ban <user> [reason]` | Ban user | `/ban spammer Spam` |
| `/unban <user>` | Remove ban | `/unban John` |
| `/mute <user> [reason]` | Mute user | `/mute John Offtopic` |
| `/unmute <user>` | Remove mute | `/unmute John` |
| `/kick <user> [min] [reason]` | Temporary kick | `/kick John 30` |
| `/unkick <user>` | Remove kick | `/unkick John` |
| `/promote <user> [admin]` | Promote to mod/admin | `/promote John` |
| `/demote <user>` | Demote user | `/demote John` |
| `/staff` | List staff members | `/staff` |
| `/newarea <name> [desc]` | Create area | `/newarea gaming` |
| `/delarea <name>` | Delete area | `/delarea test` |
| `/editarea <name> <prop> <val>` | Edit area | `/editarea tech desc Tech talk` |
| `/listareas` | List all areas (admin view) | `/listareas` |
| `/cleanup` | Run retention cleanup | `/cleanup --dry-run` |

## Privacy & GDPR

MeshCore BBS includes privacy features for GDPR compliance:

### Data Retention
- **Private Messages**: Automatically deleted after 30 days (configurable)
- **Activity Logs**: Automatically deleted after 90 days (configurable)
- **Manual Cleanup**: Admins can run `/cleanup` to purge old data

### Ephemeral Messages
Users can send private messages that are NOT saved to the database:
```
/msg! John This message won't be stored
```
Ephemeral messages exist only in memory and disappear after the recipient reads them.

### User Rights
- `/mydata` - View what data is stored about you
- `/gdpr` - View privacy policy and retention settings
- `/delpm <id>` - Delete your private messages

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
| `BBS_PM_RETENTION_DAYS` | `30` | Days to keep PMs (0=forever) |
| `BBS_LOG_RETENTION_DAYS` | `90` | Days to keep logs (0=forever) |
| `BBS_ALLOW_EPHEMERAL_PM` | `true` | Enable /msg! command |

## Project Structure

```
meshbbs/
├── src/
│   ├── main.py              # Entry point
│   ├── bbs/
│   │   ├── core.py          # Main BBS logic
│   │   ├── scheduler.py     # Background task scheduler
│   │   ├── rate_limiter.py  # Anti-spam rate limiting
│   │   ├── mentions.py      # @mention notification system
│   │   ├── privacy.py       # Privacy/GDPR utilities
│   │   ├── commands/        # Command handlers
│   │   │   ├── base.py      # Base command class
│   │   │   ├── dispatcher.py
│   │   │   ├── parser.py
│   │   │   ├── help_cmd.py
│   │   │   ├── post_cmd.py
│   │   │   ├── list_cmd.py
│   │   │   ├── read_cmd.py
│   │   │   ├── areas_cmd.py
│   │   │   └── nick_cmd.py
│   │   ├── models/          # Database models
│   │   │   ├── base.py
│   │   │   ├── user.py
│   │   │   ├── area.py
│   │   │   ├── message.py
│   │   │   ├── private_message.py
│   │   │   └── activity_log.py
│   │   └── repositories/    # Data access layer
│   │       ├── base_repository.py
│   │       ├── user_repository.py
│   │       ├── area_repository.py
│   │       └── message_repository.py
│   ├── meshcore/            # MeshCore protocol
│   │   ├── connection.py    # Radio connection
│   │   ├── messages.py      # Message types
│   │   └── protocol.py      # Protocol definitions
│   └── utils/
│       ├── config.py        # Configuration
│       └── logger.py        # Logging setup
├── data/                    # Database storage
├── logs/                    # Log files
├── tests/                   # Test suite
├── tasks/                   # Development task docs
└── docs/                    # Documentation
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

@CommandRegistry.register("mycommand")
class MyCommand(BaseCommand):
    name = "mycommand"
    description = "Does something useful"
    usage = "/mycommand <arg>"

    async def execute(self, context: CommandContext) -> CommandResult:
        # Implementation
        return CommandResult(success=True, message="Done!")
```

## Documentation

- [Installation Guide](docs/INSTALLATION.md) - Complete setup instructions
- [Configuration Guide](docs/CONFIGURATION.md) - All configuration options
- [API Documentation](docs/API.md) - REST API reference
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
