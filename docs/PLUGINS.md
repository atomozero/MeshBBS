# MeshBBS Plugin System

Guida allo sviluppo e utilizzo dei plugin per MeshBBS.

## Introduzione

Il sistema plugin permette di estendere le funzionalità di MeshBBS senza modificare il codice core. I plugin possono:

- Aggiungere nuovi comandi personalizzati
- Intercettare e processare messaggi
- Reagire a eventi del sistema (login utente, nuovi messaggi, ecc.)
- Integrare servizi esterni

## Struttura Directory

```
MeshBBS/
├── plugins/              # Directory plugin esterni
│   ├── example_plugin.py
│   ├── my_custom_plugin.py
│   └── my_package_plugin/
│       ├── __init__.py
│       └── commands.py
├── data/
│   └── plugins.json      # Configurazione plugin
└── src/
    └── bbs/plugins/      # Sistema plugin core
        ├── base.py
        └── manager.py
```

## Creare un Plugin

### Struttura Base

```python
from bbs.plugins.base import BasePlugin, PluginInfo
from bbs.commands.base import BaseCommand, CommandContext, CommandResult

class MyCommand(BaseCommand):
    """Un comando personalizzato."""

    name = "mycommand"
    description = "Il mio comando custom"
    usage = "/mycommand [argomenti]"
    aliases = ["mc"]
    admin_only = False

    def __init__(self, session=None):
        self.session = session

    async def execute(self, ctx: CommandContext, args: list) -> CommandResult:
        return CommandResult.ok(f"Ciao {ctx.sender_display}!")


class MyPlugin(BasePlugin):
    """Il mio plugin per MeshBBS."""

    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="my-plugin",
            version="1.0.0",
            description="Descrizione del plugin",
            author="Il Tuo Nome",
            min_bbs_version="1.0.0",
            homepage="https://github.com/...",
        )

    def get_commands(self):
        return [MyCommand]

    async def on_load(self) -> bool:
        # Inizializzazione (connessioni DB, config, ecc.)
        return True

    async def on_unload(self):
        # Pulizia risorse
        pass

# Export obbligatorio
Plugin = MyPlugin
```

### PluginInfo

Metadati del plugin:

| Campo | Tipo | Obbligatorio | Descrizione |
|-------|------|--------------|-------------|
| `name` | str | Si | Nome univoco del plugin |
| `version` | str | Si | Versione (semantic versioning) |
| `description` | str | Si | Descrizione breve |
| `author` | str | Si | Autore/Maintainer |
| `min_bbs_version` | str | No | Versione minima MeshBBS |
| `dependencies` | list | No | Lista dipendenze |
| `homepage` | str | No | URL homepage/repo |
| `license` | str | No | Licenza (default: MIT) |

### Hook Disponibili

I plugin possono implementare questi hook:

```python
class MyPlugin(BasePlugin):

    async def on_load(self) -> bool:
        """Chiamato al caricamento. Ritorna False per fallire."""
        return True

    async def on_unload(self):
        """Chiamato allo scaricamento."""
        pass

    async def on_enable(self) -> bool:
        """Chiamato all'abilitazione."""
        return True

    async def on_disable(self):
        """Chiamato alla disabilitazione."""
        pass

    async def on_message(self, sender_key: str, message: str, is_command: bool):
        """Chiamato per ogni messaggio ricevuto."""
        # Ritorna una stringa per iniettare una risposta
        return None

    async def on_command(self, command: str, args: list, sender_key: str):
        """Chiamato prima dell'esecuzione di un comando."""
        # Ritorna una stringa per intercettare il comando
        return None

    async def on_user_join(self, user_key: str, nickname: str):
        """Chiamato quando un nuovo utente si registra."""
        pass

    async def on_user_leave(self, user_key: str):
        """Chiamato quando un utente si disconnette."""
        pass
```

### Creare Comandi

I comandi ereditano da `BaseCommand`:

```python
class WeatherCommand(BaseCommand):
    name = "weather"
    description = "Mostra meteo località"
    usage = "/weather <città>"
    aliases = ["meteo", "w"]
    admin_only = False
    hidden = False  # True per nascondere da /help

    def __init__(self, session=None):
        self.session = session

    async def execute(self, ctx: CommandContext, args: list) -> CommandResult:
        if not args:
            return CommandResult.fail("Specifica una città: /weather Roma")

        city = " ".join(args)
        # Logica per ottenere meteo...
        weather = await self._get_weather(city)

        if weather:
            return CommandResult.ok(f"Meteo {city}: {weather}")
        else:
            return CommandResult.fail(f"Città non trovata: {city}")

    async def _get_weather(self, city):
        # Implementazione...
        return "Soleggiato, 22°C"
```

### CommandContext

Informazioni sul messaggio ricevuto:

```python
@dataclass
class CommandContext:
    sender_key: str          # Chiave pubblica mittente
    sender_name: str | None  # Nickname se impostato
    raw_message: str         # Messaggio originale
    timestamp: datetime      # Timestamp ricezione
    hops: int               # Numero hop nella mesh
    rssi: int | None        # Potenza segnale

    @property
    def sender_display(self) -> str:
        """Nome visualizzabile."""
```

### CommandResult

Risultato esecuzione comando:

```python
# Successo
return CommandResult.ok("Risposta positiva")

# Errore
return CommandResult.fail("Messaggio errore", error="Dettagli tecnici")

# Costruttore diretto
return CommandResult(success=True, response="...", error=None)
```

## Configurazione Plugin

### File plugins.json

```json
{
  "enabled": [
    "example_plugin",
    "my_plugin"
  ],
  "plugins": {
    "my_plugin": {
      "api_key": "xxx",
      "cache_ttl": 3600
    }
  }
}
```

### Accesso Configurazione

```python
class MyPlugin(BasePlugin):

    async def on_load(self) -> bool:
        # self.config contiene la configurazione del plugin
        api_key = self.config.get("api_key")
        if not api_key:
            return False
        return True
```

## Gestione Plugin

### Via API REST

```bash
# Lista plugin
GET /api/v1/plugins

# Stato plugin
GET /api/v1/plugins/{name}/status

# Abilita plugin
POST /api/v1/plugins/{name}/enable

# Disabilita plugin
POST /api/v1/plugins/{name}/disable

# Ricarica plugin
POST /api/v1/plugins/{name}/reload

# Configura plugin
PATCH /api/v1/plugins/{name}/config
```

### Via Codice

```python
from bbs.plugins import PluginManager

manager = PluginManager(
    plugins_dir="/path/to/plugins",
    config_file="/path/to/plugins.json"
)

# Scopri plugin disponibili
available = manager.discover_plugins()

# Carica tutti
await manager.load_all()

# Abilita quelli configurati
await manager.enable_configured()

# Carica singolo
await manager.load_plugin("my_plugin")

# Abilita/Disabilita
await manager.enable_plugin("my_plugin")
await manager.disable_plugin("my_plugin")

# Ricarica
await manager.reload_plugin("my_plugin")

# Stato
status = manager.get_status()

# Dispatch hooks
responses = await manager.dispatch_hook("on_message", sender_key, message, is_cmd)
```

## Stati Plugin

| Stato | Descrizione |
|-------|-------------|
| `unloaded` | Non caricato |
| `loading` | Caricamento in corso |
| `loaded` | Caricato ma non attivo |
| `enabled` | Attivo e funzionante |
| `disabled` | Disabilitato manualmente |
| `error` | Errore durante operazione |

## Best Practices

### 1. Gestione Errori

```python
async def execute(self, ctx, args):
    try:
        result = await self._do_work()
        return CommandResult.ok(result)
    except Exception as e:
        logger.error(f"Error: {e}")
        return CommandResult.fail("Errore interno")
```

### 2. Risorse Esterne

```python
class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self._client = None

    async def on_load(self):
        self._client = await ExternalClient.connect()
        return True

    async def on_unload(self):
        if self._client:
            await self._client.close()
```

### 3. Rate Limiting Custom

```python
from datetime import datetime, timedelta

class MyPlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self._last_call = {}

    async def on_command(self, command, args, sender_key):
        if command == "expensive":
            last = self._last_call.get(sender_key)
            if last and datetime.utcnow() - last < timedelta(minutes=5):
                return "Attendi 5 minuti tra le richieste"
            self._last_call[sender_key] = datetime.utcnow()
        return None
```

### 4. Database Access

```python
class MyCommand(BaseCommand):
    async def execute(self, ctx, args):
        # self.session è la sessione SQLAlchemy
        from bbs.models import User
        user = self.session.query(User).filter_by(
            public_key=ctx.sender_key
        ).first()
        return CommandResult.ok(f"Ciao {user.nickname}!")
```

## Esempio Completo

Vedi `/plugins/example_plugin.py` per un esempio funzionante con:

- Comando `/ping` - Test responsività
- Comando `/pluginup` - Uptime plugin
- Comando `/echo` - Echo text
- Hook messaggi
- Hook nuovi utenti

## Troubleshooting

### Plugin Non Carica

1. Verifica che il file sia in `plugins/`
2. Controlla la sintassi Python
3. Verifica che esista `Plugin = MyPluginClass`
4. Controlla i log per errori dettagliati

### Comando Non Registrato

1. Assicurati che `get_commands()` ritorni la classe
2. Verifica che il comando abbia `name` definito
3. Ricarica il plugin dopo modifiche

### Hook Non Chiamato

1. Verifica che il plugin sia `enabled` non solo `loaded`
2. Controlla che il metodo sia `async`
3. Verifica la firma del metodo
