# 09 — Fase 5: Command Parser e Comandi Base

> Riferimento: Roadmap Fase 5

---

## Obiettivo

Dispatcher funzionante con decoratore `@command` e 5 comandi di sistema operativi.

## Dipendenze

- Fase 4 completata (connessione, coda, main loop)

## F5.1 — dispatcher.py

```python
# dispatcher.py
import time
import logging
from database import get_or_create_user
from config import BBS_NAME, BBS_VERSION

log = logging.getLogger(__name__)

# Registro comandi: "!comando" -> funzione handler
_HANDLERS = {}

def command(name: str):
    """Decoratore per registrare un handler di comando."""
    def decorator(fn):
        _HANDLERS[name.lower()] = fn
        return fn
    return decorator

async def dispatch(from_pubkey: str, text: str, db) -> str | None:
    """
    Riceve il testo grezzo del messaggio.
    Se inizia con '!' lo smista all'handler corretto.
    Restituisce la stringa di risposta o None se ignorato.
    """
    # Registrazione automatica utente al primo contatto
    await get_or_create_user(db, from_pubkey, from_pubkey[:8], BBS_NAME)

    if not text.startswith("!"):
        return None  # non e' un comando BBS — ignora silenziosamente

    parts = text.strip().split(maxsplit=2)
    cmd   = parts[0].lower()           # es. "!post"
    args  = parts[1:] if len(parts) > 1 else []

    handler = _HANDLERS.get(cmd)
    if handler is None:
        return f"Cmd sconosciuto: {cmd}\n!help per la lista"

    try:
        return await handler(from_pubkey, args, db)
    except Exception as e:
        log.error(f"Errore handler {cmd}: {e}")
        return "Errore interno BBS"
```

### Note sul Design del Dispatcher

- **Decoratore `@command`**: ogni modulo registra i propri comandi importando `command` da `dispatcher.py`
- **Auto-registrazione utente**: ogni messaggio che inizia con `!` registra/aggiorna l'utente nel DB
- **split(maxsplit=2)**: limita il parsing a 3 parti massimo — il terzo elemento contiene tutto il testo rimanente
- **Silenziamento non-comandi**: messaggi senza `!` vengono ignorati (nessuna risposta)

### Punto critico — Import circolare

I moduli (`system.py`, `boards.py`, ecc.) importano `command` da `dispatcher.py`. Per evitare import circolari:
1. I moduli devono essere importati **dopo** la definizione di `_HANDLERS` e `command`
2. In `main.py` importare i moduli per triggerare la registrazione dei decoratori:

```python
# In main.py, prima del loop principale:
import modules.system
import modules.boards
import modules.mail
import modules.federation
```

## F5.2 — modules/system.py — Comandi Base

```python
# modules/system.py
import time
from dispatcher import command
from config import BBS_NAME, BBS_VERSION
from database import execute_fetchone

_START_TIME = int(time.time())

def _uptime() -> str:
    secs = int(time.time()) - _START_TIME
    h, m = divmod(secs // 60, 60)
    return f"{h}h{m}m"

@command("!help")
async def cmd_help(from_pubkey, args, db) -> str:
    return (
        f"{BBS_NAME} v{BBS_VERSION}\n"
        "!ping !info !nick <n> !nodes\n"
        "!boards !read <b> !post <b> <txt>\n"
        "!inbox !mail <dst> <txt>"
    )

@command("!ping")
async def cmd_ping(from_pubkey, args, db) -> str:
    return f"pong [{BBS_NAME}] up={_uptime()}"

@command("!info")
async def cmd_info(from_pubkey, args, db) -> str:
    row = await execute_fetchone(
        db, "SELECT COUNT(*) as c FROM federation_nodes WHERE status='online'"
    )
    online = row["c"] if row else 0
    return (
        f"{BBS_NAME} v{BBS_VERSION}\n"
        f"Nodi federati online: {online}\n"
        f"Uptime: {_uptime()}"
    )

@command("!nick")
async def cmd_nick(from_pubkey, args, db) -> str:
    if not args:
        return "Uso: !nick <nickname>"
    nick = args[0][:20]  # max 20 chars
    await db.execute(
        "UPDATE users SET nickname=? WHERE pubkey=?", (nick, from_pubkey)
    )
    await db.commit()
    return f"Nickname impostato: {nick}"

@command("!nodes")
async def cmd_nodes(from_pubkey, args, db) -> str:
    from database import execute_fetchall
    rows = await execute_fetchall(
        db, "SELECT name, status FROM federation_nodes ORDER BY status, name"
    )
    if not rows:
        return "Nessun nodo federato configurato"
    lines = [f"{'[ON]' if r['status']=='online' else '[--]'} {r['name']}"
             for r in rows]
    return "\n".join(lines)
```

**Correzioni rispetto alla roadmap originale**:
- Usa `execute_fetchone()` e `execute_fetchall()` come funzioni standalone (non metodi di `db`)
- `!help` risposta verificata < 180 caratteri

### Verifica lunghezza !help

```
"BBS-NomeNodo v1.0.0\n!ping !info !nick <n> !nodes\n!boards !read <b> !post <b> <txt>\n!inbox !mail <dst> <txt>"
```
= ~110 caratteri. OK, sta in un singolo pacchetto.

## Sicurezza — Input Validation

Il dispatcher attuale e' minimale. Aree da rafforzare:

1. **Sanitizzazione input**: il testo viene passato direttamente alle query SQL come parametro (OK, parametrizzato). Ma il nick potrebbe contenere caratteri di controllo.
2. **Rate limiting**: un utente potrebbe mandare comandi in rapida successione. Aggiungere un contatore per pubkey.
3. **Lunghezza input**: troncare messaggi troppo lunghi prima del parsing.

## Criteri di Completamento

- [ ] `!ping` risponde entro 30s
- [ ] `!nick Mario` aggiorna il DB e risponde
- [ ] `!help` entra in un singolo messaggio (< 180 chars)
- [ ] Comando sconosciuto -> risposta di errore
- [ ] Registrazione automatica utente al primo `!` verificata
- [ ] Import dei moduli non causa errori circolari
