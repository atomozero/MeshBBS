# MeshCore BBS — Roadmap di Sviluppo v1.1

> **Documento di lavoro** — base per lo sviluppo iterativo  
> Hardware: Heltec V3 + Raspberry Pi W | Connessione: WiFi TCP porta 5000 | Frequenza: 868 MHz EU  
> 📁 Documentazione dettagliata per capitolo: `docs/`

---

## ⚠️ Incongruenze rilevate e corrette rispetto alla bozza iniziale

| # | Problema | Correzione applicata |
|---|---|---|
| 1 | `pip install asyncio` — `asyncio` è stdlib Python 3.4+, non va su PyPI | Rimosso da tutte le dipendenze |
| 2 | Numerazione interna fasi: ogni fase ripartiva da "2.1" | Ogni fase usa numerazione propria (es. F3.1, F3.2) |
| 3 | F3 (Database) dichiarata dipendente da F2 (TCP) | F3 è **indipendente** da F2, può partire in parallelo |
| 4 | Comando `!read` ambiguo: usato sia per bacheche che per mail | Separato in `!read <board>` e `!mail read <id>` |
| 5 | `!read mail <id>` assente nella tabella comandi v1 finale | Aggiunto come sottocomando di `!mail` |
| 6 | MTU 255 byte confuso con caratteri utili del testo | Chiarito: 255 byte = payload totale pacchetto MeshCore; testo utile ~180 byte dopo header BBS |
| 7 | Routing mail inter-nodo via `dest_nick` non risolto: come trova la pubkey su nodo remoto? | Aggiunto meccanismo: la mail viene inoltrata a tutti i peer che la recapitano se conoscono il destinatario (store-and-forward federato) |
| 8 | `global_id` definito concettualmente ma non come si genera in Python | Aggiunto snippet preciso con `hashlib` |
| 9 | TTL nel pacchetto federazione ridondante con peering statico v1 | Mantenuto per compatibilità futura v2, documentato come "reserved in v1" |
| 10 | `get_self_info()` non verificato nella libreria meshcore Python | Sostituito con API verificata dalla documentazione PyPI |
| 11 | Struttura progetto definita in F4 ma F2 già scrive codice | Chiarito: F2 = script standalone di test; struttura progetto parte da F4 |
| 12 | NODE_STATUS ogni 15 min con molti peer può saturare rate limit 3 msg/min | Aggiunto: NODE_STATUS inviato sequenzialmente, uno per ciclo, non in burst |
| 13 | `make_global_id()` chiamata con `BBS_NAME` invece di pubkey nodo | Corretto: usare sempre la pubkey del nodo BBS come `origin_pubkey` |
| 14 | `modules/system.py` mancante dalla struttura progetto | Aggiunto nella struttura directory |
| 15 | `_rel_time()` duplicata in `boards.py` e `mail.py` | Estratta in `utils.py` come funzione condivisa |
| 16 | `execute_fetchone`/`execute_fetchall` usati come metodi di `db` | Non esistono in `aiosqlite` — implementati come funzioni standalone in `database.py` |
| 17 | Mail inter-nodo: `to_pubkey` salvata come stringa vuota | Corretto: usa sentinel `"PENDING"` + colonna `federation_status` |
| 18 | `struct.pack("<BBBBB")` in header federazione produce 5 byte | Corretto: `struct.pack("<BBB")` — header totale 19 byte, non 20 |
| 19 | Mancanza graceful shutdown in `main.py` | Aggiunto signal handler per SIGTERM/SIGINT |
| 20 | Nessuna sezione testing/simulazione offline | Aggiunto mock companion e struttura test |

---

## 0. Indice

1. [Introduzione e Architettura](#1-introduzione-e-architettura)
2. [Stack e Dipendenze](#2-stack-e-dipendenze)
3. [Schema Database](#3-schema-database)
4. [Struttura del Progetto](#4-struttura-del-progetto)
5. [Fase 1 — Hardware e Firmware](#fase-1--hardware-e-firmware)
6. [Fase 2 — Test Connessione TCP](#fase-2--test-connessione-tcp)
7. [Fase 3 — Database e Schema](#fase-3--database-e-schema)
8. [Fase 4 — Layer di Connessione e Resilienza](#fase-4--layer-di-connessione-e-resilienza)
9. [Fase 5 — Command Parser e Comandi Base](#fase-5--command-parser-e-comandi-base)
10. [Fase 6 — Moduli BBS: Bacheche e Mailbox](#fase-6--moduli-bbs-bacheche-e-mailbox)
11. [Fase 7 — Protocollo di Federazione](#fase-7--protocollo-di-federazione)
12. [Comandi v1 — Riepilogo Completo](#comandi-v1--riepilogo-completo)
13. [Fuori Scope v1](#fuori-scope-v1)
14. [Aree da Analizzare](#aree-da-analizzare)

---

## 1. Introduzione e Architettura

MeshCore BBS è un sistema bulletin board distribuito e federato che opera su rete LoRa mesh senza dipendenza da infrastrutture Internet. Il firmware del Companion radio rimane **originale e non modificato**: tutta la logica BBS risiede nel software Python sul Raspberry Pi.

### Principi

- Firmware MeshCore originale — nessuna modifica al layer radio
- Logica BBS interamente su Raspberry Pi in Python `asyncio`
- Connessione Heltec V3 ↔ RPi via TCP WiFi (porta 5000)
- Database SQLite con schema **federazione-ready** fin dalla v1
- Federazione push immediata tra nodi BBS via messaggi diretti LoRa
- Autenticazione implicita tramite pubkey crittografica MeshCore

### Schema a layer

```
┌─────────────────────────────────────────────────────────┐
│              RASPBERRY PI W (Software BBS)              │
│  main.py · dispatcher.py · queue.py · database.py       │
│  modules/: system · users · boards · mail · federation  │
│                                                         │
│  config.py → COMPANION_HOST=192.168.1.50                │
│              COMPANION_PORT=5000                        │
└──────────────────┬──────────────────────────────────────┘
                   │ TCP socket (WiFi LAN)
┌──────────────────▼──────────────────────────────────────┐
│         HELTEC V3 — MeshCore companion_radio_wifi       │
│         ESP32 + SX1262 · 868 MHz EU · IP fisso          │
└──────────────────┬──────────────────────────────────────┘
                   │ LoRa 868 MHz
        ┌──────────▼──────────┐
        │   Mesh Network      │
        │  Repeater ··· Node  │
        │  BBS-B ··· BBS-C    │  ← federazione
        └─────────────────────┘
```

---

## 2. Stack e Dipendenze

### Hardware

| Componente | Modello | Note |
|---|---|---|
| Radio companion | Heltec WiFi LoRa 32 V3 | ESP32 + SX1262, OLED 128×64 |
| Host | Raspberry Pi W (Zero W o 3/4) | Alimentazione stabile 5V |
| Antenna | Dipolo 868 MHz | Esterna se possibile |

### Software — Dipendenze Python

```bash
# Sul Raspberry Pi
pip install meshcore          # libreria ufficiale MeshCore companion
pip install aiosqlite         # SQLite asincrono per asyncio
pip install structlog          # logging strutturato
```

> ⚠️ **`asyncio` NON va installato via pip** — è parte della stdlib Python 3.4+.

### Riferimento libreria Python

- PyPI: https://pypi.org/project/meshcore/
- GitHub: https://github.com/meshcore-dev/meshcore_py
- Connessioni supportate: `create_serial()`, `create_ble()`, **`create_tcp()`** ← nostra scelta

### API principale meshcore (verificata da documentazione PyPI)

```python
import asyncio
from meshcore import MeshCore, EventType

# Connessione TCP
mc = await MeshCore.create_tcp("192.168.1.50", 5000)

# Comandi disponibili
await mc.commands.get_contacts()        # → lista contatti
await mc.commands.send_msg(contact, "testo")  # → invia messaggio diretto
await mc.commands.get_bat()             # → livello batteria
await mc.commands.send_advert(flood=True)  # → broadcast advert

# Subscribe agli eventi
mc.subscribe(EventType.MSG_RECEIVED, handler)
mc.subscribe(EventType.ACK, handler)
mc.subscribe(EventType.BATTERY, handler)

# Ogni handler riceve un Event con .type e .payload
async def handler(event):
    print(event.type, event.payload)
```

> ℹ️ **Nota**: verificare i nomi esatti dei metodi alla prima connessione reale — la libreria è in sviluppo attivo.

---

## 3. Schema Database

Il database è progettato federation-ready dalla v1. Ogni record che può essere sincronizzato tra nodi ha un `global_id` univoco generato così:

```python
import hashlib, time

def make_global_id(origin_pubkey: str, content: str) -> str:
    """Genera un ID globale univoco per un record federato."""
    raw = f"{origin_pubkey}:{time.time_ns()}:{content}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]  # 16 hex chars = 8 byte
```

### DDL completo

```sql
-- Utenti registrati (locali e federati)
CREATE TABLE IF NOT EXISTS users (
    pubkey       TEXT PRIMARY KEY,
    nickname     TEXT,
    first_seen   INTEGER NOT NULL,
    last_seen    INTEGER NOT NULL,
    origin_node  TEXT    -- pubkey del nodo BBS di registrazione
);

-- Bacheche tematiche
CREATE TABLE IF NOT EXISTS boards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    description TEXT
);

-- Post delle bacheche
CREATE TABLE IF NOT EXISTS posts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    global_id     TEXT UNIQUE NOT NULL,  -- per federazione anti-loop
    board_id      INTEGER NOT NULL REFERENCES boards(id),
    author_pubkey TEXT NOT NULL,
    author_nick   TEXT,                  -- denormalizzato per display veloce
    origin_node   TEXT NOT NULL,         -- nodo BBS di origine
    text          TEXT NOT NULL,
    timestamp     INTEGER NOT NULL,
    is_local      BOOLEAN NOT NULL DEFAULT 1
);

-- Mailbox privata (store-and-forward)
CREATE TABLE IF NOT EXISTS mail (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    global_id    TEXT UNIQUE NOT NULL,
    from_pubkey  TEXT NOT NULL,
    from_nick    TEXT,
    to_pubkey    TEXT NOT NULL,          -- pubkey del destinatario
    to_nick      TEXT,                   -- nick del destinatario (hint per routing)
    text         TEXT NOT NULL,
    timestamp    INTEGER NOT NULL,
    delivered    BOOLEAN NOT NULL DEFAULT 0,
    read         BOOLEAN NOT NULL DEFAULT 0,
    federation_status TEXT DEFAULT NULL  -- NULL=locale, pending/delivered/failed=inter-nodo
);

-- Nodi BBS federati conosciuti
CREATE TABLE IF NOT EXISTS federation_nodes (
    pubkey       TEXT PRIMARY KEY,
    name         TEXT,
    last_seen    INTEGER,
    status       TEXT NOT NULL DEFAULT 'unknown',  -- online|offline|unknown
    is_peer      BOOLEAN NOT NULL DEFAULT 0        -- peer statico configurato
);

-- Messaggi federazione già processati (anti-loop)
CREATE TABLE IF NOT EXISTS federation_seen (
    msg_id       TEXT PRIMARY KEY,
    received_at  INTEGER NOT NULL
);

-- Indici per performance
CREATE INDEX IF NOT EXISTS idx_posts_board    ON posts(board_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_posts_global   ON posts(global_id);
CREATE INDEX IF NOT EXISTS idx_mail_to        ON mail(to_pubkey, read);
CREATE INDEX IF NOT EXISTS idx_fed_seen_time  ON federation_seen(received_at);
```

### Board predefinite v1

```sql
INSERT OR IGNORE INTO boards (name, description) VALUES
    ('Generale', 'Discussioni generali'),
    ('Annunci',  'Comunicazioni importanti'),
    ('Tecnica',  'Radio, elettronica, software');
```

---

## 4. Struttura del Progetto

```
meshbbs/
├── main.py              # entry point: avvia asyncio event loop
├── config.py            # configurazione centralizzata
├── connection.py        # gestione connessione TCP + auto-reconnect
├── dispatcher.py        # router messaggi in arrivo → modulo corretto
├── queue.py             # coda messaggi in uscita con priorità
├── database.py          # wrapper aiosqlite + query helpers
├── logger.py            # logging strutturato con structlog
├── utils.py             # utility condivise (rel_time, sanitize)
├── modules/
│   ├── __init__.py
│   ├── system.py        # comandi base: !help !ping !info !nick !nodes
│   ├── users.py         # registrazione, nickname
│   ├── boards.py        # bacheche: !boards !read !post
│   ├── mail.py          # mailbox: !inbox !mail
│   └── federation.py    # protocollo federazione
├── tests/               # test unitari e di integrazione
│   ├── __init__.py
│   ├── test_dispatcher.py
│   ├── test_database.py
│   ├── test_boards.py
│   ├── test_mail.py
│   ├── test_federation.py
│   └── mock_companion.py  # mock per test senza hardware
├── scripts/
│   ├── init_db.py       # inizializzazione database standalone
│   └── test_connection.py  # test connessione TCP standalone
├── requirements.txt
└── meshbbs.service      # unit file systemd
```

### `config.py` — struttura base

```python
# config.py
import os

# Connessione Companion
COMPANION_HOST = os.getenv("BBS_HOST", "192.168.1.50")
COMPANION_PORT = int(os.getenv("BBS_PORT", "5000"))

# Identità BBS
BBS_NAME     = os.getenv("BBS_NAME", "BBS-NomeNodo")
BBS_VERSION  = "1.0.0"

# Database
DB_PATH      = os.getenv("BBS_DB", "/home/pi/meshbbs/bbs.db")

# Federazione
FEDERATION_PEERS = []  # lista pubkey peer statici — popolata manualmente
FEDERATION_RATE_LIMIT = 3       # max msg federazione al minuto per peer
NODE_STATUS_INTERVAL  = 900     # secondi tra NODE_STATUS (15 min)
PEER_TIMEOUT          = 2700    # secondi prima di marcare peer offline (45 min)

# Limiti
MAX_POST_LEN  = 180   # caratteri — vedi nota MTU sotto
MAX_MAIL_LEN  = 180
MAX_INBOX     = 20    # mail per utente
MAX_NICK_LEN  = 20    # lunghezza massima nickname

# Sicurezza
RATE_LIMIT_USER  = 10   # max comandi per minuto per utente
BLACKLIST_PUBKEYS = []  # pubkey bannate

# Logging
LOG_FILE     = "/home/pi/meshbbs/bbs.log"
LOG_LEVEL    = "INFO"
```

> ℹ️ **Nota MTU**: Il pacchetto MeshCore ha MTU fisico di 255 byte. Di questi, l'header di protocollo occupa ~20-30 byte, lasciando ~225 byte utili. Il BBS aggiunge il proprio prefisso di risposta (es. `[BBS] `) di ~10 byte, quindi il testo utente va limitato a **~180 caratteri** per stare sicuri in un singolo pacchetto.

---

## Fase 1 — Hardware e Firmware

**Obiettivo**: Heltec V3 operativo con firmware WiFi MeshCore, IP fisso, porta TCP 5000 raggiungibile dal RPi.

### F1.1 — Compilazione firmware WiFi

Il firmware WiFi non è disponibile precompilato: SSID e password vengono incorporati a compile-time.

**Opzione A — Script automatico (consigliata)**

```bash
git clone https://github.com/ilikehamradio/meshcore_heltecv3_wifi
cd meshcore_heltecv3_wifi
./build.sh
# Richiede: regione LoRa → 868 MHz EU (opzione 4)
#           SSID e password WiFi
# Output:   firmware-merged.bin
```

**Opzione B — Compilazione manuale con PlatformIO**

```bash
git clone https://github.com/meshcore-dev/MeshCore
cd MeshCore
# Editare variants/heltec_v3/platformio.ini:
#   -D WIFI_SSID="NomeTuaRete"
#   -D WIFI_PWD="TuaPassword"
pio run -e Heltec_v3_companion_radio_wifi
```

> ⚠️ **Non condividere mai il binario compilato** — contiene SSID e password in chiaro.

### F1.2 — Flash dell'Heltec V3

```bash
# Modalità bootloader: tieni BOOT, collega USB, rilascia BOOT
# Nota: Heltec V3 usa ESP32-S3, non ESP32 generico
esptool.py --chip esp32s3 --baud 921600 \
           write_flash 0x0 firmware-merged.bin
```

### F1.3 — Configurazione rete

1. Trovare il MAC address dell'Heltec V3 dal display OLED o dal router
2. Creare DHCP reservation sul router → assegnare es. `192.168.1.50`
3. Verificare raggiungibilità dal RPi:

```bash
# Dal Raspberry Pi
ping 192.168.1.50
nc -zv 192.168.1.50 5000   # deve rispondere
```

### ✅ Criteri completamento F1

- [ ] Heltec V3 appare in rete con IP fisso `192.168.1.50`
- [ ] Porta TCP 5000 raggiungibile (`nc` risponde)
- [ ] Display OLED mostra nome nodo e stato radio
- [ ] Firmware non modificato rispetto al sorgente ufficiale

---

## Fase 2 — Test Connessione TCP

**Obiettivo**: Verificare ricezione eventi dalla libreria Python. Questa fase produce **script standalone di test**, non la struttura definitiva del progetto (quella è Fase 4).

> ℹ️ **Fase 2 e Fase 3 possono procedere in parallelo** — il database non dipende dalla connessione TCP.

### F2.1 — Installazione dipendenze

```bash
pip install meshcore aiosqlite structlog
```

### F2.2 — Script test connessione

```python
# test_connection.py
import asyncio
from meshcore import MeshCore, EventType

async def main():
    print("Connessione a 192.168.1.50:5000 ...")
    mc = await MeshCore.create_tcp("192.168.1.50", 5000)
    print("Connesso!")

    # Verifica informazioni nodo
    contacts = await mc.commands.get_contacts()
    print(f"Contatti trovati: {contacts.payload}")

    # Handler messaggi in arrivo
    async def on_message(event):
        print(f"[MSG] {event.payload}")

    mc.subscribe(EventType.MSG_RECEIVED, on_message)

    # Resta in ascolto 60 secondi
    print("In ascolto per 60 secondi — manda un messaggio al nodo...")
    await asyncio.sleep(60)
    await mc.disconnect()

asyncio.run(main())
```

### F2.3 — Script test invio

```python
# test_send.py — da eseguire DOPO aver verificato la ricezione
import asyncio
from meshcore import MeshCore, EventType

async def main():
    mc = await MeshCore.create_tcp("192.168.1.50", 5000)

    contacts = await mc.commands.get_contacts()
    if not contacts.payload:
        print("Nessun contatto — aggiungi almeno un nodo dalla app MeshCore")
        return

    # Prende il primo contatto disponibile
    first = next(iter(contacts.payload.values()))
    result = await mc.commands.send_msg(first, "Test BBS OK")
    print(f"Invio: {result.type} — {result.payload}")

    await mc.disconnect()

asyncio.run(main())
```

### ✅ Criteri completamento F2

- [ ] `create_tcp()` si connette senza eccezioni
- [ ] `get_contacts()` restituisce lista (anche vuota è OK)
- [ ] `MSG_RECEIVED` viene triggerato quando arriva un messaggio
- [ ] `send_msg()` non restituisce errore

---

## Fase 3 — Database e Schema

**Obiettivo**: Creare il database SQLite con schema completo e verificare insert/query per ogni tabella.

### F3.1 — Script di inizializzazione

```python
# init_db.py
import sqlite3
import time

DB_PATH = "bbs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    pubkey       TEXT PRIMARY KEY,
    nickname     TEXT,
    first_seen   INTEGER NOT NULL,
    last_seen    INTEGER NOT NULL,
    origin_node  TEXT
);

CREATE TABLE IF NOT EXISTS boards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS posts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    global_id     TEXT UNIQUE NOT NULL,
    board_id      INTEGER NOT NULL REFERENCES boards(id),
    author_pubkey TEXT NOT NULL,
    author_nick   TEXT,
    origin_node   TEXT NOT NULL,
    text          TEXT NOT NULL,
    timestamp     INTEGER NOT NULL,
    is_local      BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS mail (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    global_id    TEXT UNIQUE NOT NULL,
    from_pubkey  TEXT NOT NULL,
    from_nick    TEXT,
    to_pubkey    TEXT NOT NULL,
    to_nick      TEXT,
    text         TEXT NOT NULL,
    timestamp    INTEGER NOT NULL,
    delivered    BOOLEAN NOT NULL DEFAULT 0,
    read         BOOLEAN NOT NULL DEFAULT 0,
    federation_status TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS federation_nodes (
    pubkey       TEXT PRIMARY KEY,
    name         TEXT,
    last_seen    INTEGER,
    status       TEXT NOT NULL DEFAULT 'unknown',
    is_peer      BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS federation_seen (
    msg_id       TEXT PRIMARY KEY,
    received_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_posts_board  ON posts(board_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_posts_global ON posts(global_id);
CREATE INDEX IF NOT EXISTS idx_mail_to      ON mail(to_pubkey, read);
CREATE INDEX IF NOT EXISTS idx_fed_seen     ON federation_seen(received_at);
"""

BOARDS_DEFAULT = [
    ("Generale", "Discussioni generali"),
    ("Annunci",  "Comunicazioni importanti, eventi, avvisi"),
    ("Tecnica",  "Radio, elettronica, software"),
]

def init():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT OR IGNORE INTO boards (name, description) VALUES (?, ?)",
        BOARDS_DEFAULT
    )
    conn.commit()
    conn.close()
    print(f"Database inizializzato: {DB_PATH}")

if __name__ == "__main__":
    init()
```

### F3.2 — `database.py` wrapper asincrono (stub iniziale)

```python
# database.py
import aiosqlite
import hashlib
import time
from config import DB_PATH

async def get_db() -> aiosqlite.Connection:
    """Restituisce connessione aiosqlite con row_factory."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

def make_global_id(origin_pubkey: str, content: str) -> str:
    """Genera global_id univoco per record federati."""
    raw = f"{origin_pubkey}:{time.time_ns()}:{content}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

async def execute_fetchone(db, query: str, params=()) -> dict | None:
    """Helper: aiosqlite non ha questo metodo nativamente."""
    cursor = await db.execute(query, params)
    return await cursor.fetchone()

async def execute_fetchall(db, query: str, params=()) -> list:
    """Helper: aiosqlite non ha questo metodo nativamente."""
    cursor = await db.execute(query, params)
    return await cursor.fetchall()

async def get_or_create_user(db, pubkey: str, nickname: str, origin_node: str):
    now = int(time.time())
    await db.execute("""
        INSERT INTO users (pubkey, nickname, first_seen, last_seen, origin_node)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(pubkey) DO UPDATE SET last_seen=excluded.last_seen
    """, (pubkey, nickname, now, now, origin_node))
    await db.commit()

async def cleanup_federation_seen(db, days: int = 7):
    """Rimuove msg_id più vecchi di N giorni dall'anti-loop table."""
    cutoff = int(time.time()) - (days * 86400)
    await db.execute(
        "DELETE FROM federation_seen WHERE received_at < ?", (cutoff,)
    )
    await db.commit()
```

### ✅ Criteri completamento F3

- [ ] `python init_db.py` crea il DB senza errori
- [ ] Tutte le tabelle presenti e board predefinite inserite
- [ ] `make_global_id()` produce ID diversi per chiamate diverse
- [ ] `get_or_create_user()` funziona con upsert (non duplica)

---

## Fase 4 — Layer di Connessione e Resilienza

**Obiettivo**: Nucleo del software BBS — connessione con auto-reconnect, coda messaggi, logging, servizio systemd.

### F4.1 — `connection.py` — auto-reconnect

```python
# connection.py
import asyncio
import logging
from meshcore import MeshCore, EventType
from config import COMPANION_HOST, COMPANION_PORT

log = logging.getLogger(__name__)

class CompanionConnection:
    def __init__(self, on_message):
        self._on_message = on_message
        self._mc = None
        self._connected = False

    async def connect(self):
        """Connessione con backoff esponenziale."""
        delay = 5
        while True:
            try:
                log.info(f"Connessione a {COMPANION_HOST}:{COMPANION_PORT}...")
                self._mc = await MeshCore.create_tcp(COMPANION_HOST, COMPANION_PORT)
                self._mc.subscribe(EventType.MSG_RECEIVED, self._on_message)
                self._connected = True
                log.info("Connesso al Companion.")
                return
            except Exception as e:
                log.warning(f"Connessione fallita: {e}. Retry in {delay}s")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)  # backoff: 5→10→20→40→60s max

    async def send(self, contact, text: str):
        """Invia messaggio — rilancia eccezione se non connesso."""
        if not self._mc or not self._connected:
            raise ConnectionError("Companion non connesso")
        return await self._mc.commands.send_msg(contact, text)

    async def get_contacts(self):
        if not self._mc:
            raise ConnectionError("Companion non connesso")
        return await self._mc.commands.get_contacts()

    async def watch(self):
        """Loop di monitoraggio — rileva disconnessioni e riconnette."""
        while True:
            await asyncio.sleep(30)
            if self._mc is None:
                log.warning("Companion disconnesso — tentativo riconnessione")
                self._connected = False
                await self.connect()
```

### F4.2 — `queue.py` — coda messaggi con priorità

```python
# queue.py
import asyncio

# Priorità: minore = più urgente
PRIO_USER        = 1   # risposte dirette all'utente
PRIO_NOTIFY      = 2   # notifiche (mail in attesa, ecc.)
PRIO_FEDERATION  = 3   # messaggi verso peer federati

class OutboxQueue:
    def __init__(self):
        self._queue = asyncio.PriorityQueue()
        self._seq   = 0  # sequenza per FIFO dentro stessa priorità

    async def put(self, contact, text: str, priority: int = PRIO_USER):
        self._seq += 1
        await self._queue.put((priority, self._seq, contact, text))

    async def get(self):
        priority, _, contact, text = await self._queue.get()
        return contact, text

    def task_done(self):
        self._queue.task_done()

    def empty(self):
        return self._queue.empty()
```

### F4.3 — `main.py` — entry point

```python
# main.py
import asyncio
import signal
import logging
from connection import CompanionConnection
from queue import OutboxQueue, PRIO_USER
from dispatcher import dispatch
from database import get_db

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("meshbbs")

outbox = OutboxQueue()

async def on_message(event):
    """Callback: messaggio ricevuto dal Companion."""
    payload = event.payload
    from_pubkey = payload.get("from", "")
    text        = payload.get("text", "").strip()
    log.info(f"MSG from={from_pubkey[:8]} text={text[:40]}")

    db = await get_db()
    try:
        response = await dispatch(from_pubkey, text, db)
        if response:
            # La risposta viene messa in coda — non inviata direttamente
            # Il contatto viene risolto dalla connection tramite pubkey
            await outbox.put(from_pubkey, response, PRIO_USER)
    finally:
        await db.close()

async def sender_loop(conn: CompanionConnection):
    """Loop che svuota la outbox e manda i messaggi."""
    while True:
        contact_pubkey, text = await outbox.get()
        try:
            contacts_result = await conn.get_contacts()
            contacts = contacts_result.payload or {}
            # Trova il contatto per pubkey
            contact = next(
                (c for c in contacts.values()
                 if str(c.get("pubkey","")).startswith(contact_pubkey[:8])),
                None
            )
            if contact:
                await conn.send(contact, text)
            else:
                log.warning(f"Contatto {contact_pubkey[:8]} non trovato per risposta")
        except Exception as e:
            log.error(f"Errore invio: {e}")
        finally:
            outbox.task_done()

async def main():
    conn = CompanionConnection(on_message)
    await conn.connect()

    # Graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown()))

    await asyncio.gather(
        conn.watch(),
        sender_loop(conn),
    )

async def _shutdown():
    log.info("Shutdown in corso...")
    raise SystemExit(0)

if __name__ == "__main__":
    asyncio.run(main())
```

### F4.4 — Servizio systemd

```ini
# /etc/systemd/system/meshbbs.service
[Unit]
Description=MeshCore BBS
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/meshbbs
ExecStart=/usr/bin/python3 /home/pi/meshbbs/main.py
Restart=always
RestartSec=10
StandardOutput=append:/home/pi/meshbbs/bbs.log
StandardError=append:/home/pi/meshbbs/bbs.log

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable meshbbs
sudo systemctl start meshbbs
sudo systemctl status meshbbs
```

### ✅ Criteri completamento F4

- [ ] Disconnessione simulata (spegni Heltec): sistema riconnette automaticamente con backoff
- [ ] Riavvio RPi: il servizio riparte e si riconnette entro 60s
- [ ] Messaggio in ingresso → appare nel log
- [ ] `OutboxQueue` gestisce priorità (risposta utente prima di federazione)

---

## Fase 5 — Command Parser e Comandi Base

**Obiettivo**: Dispatcher funzionante e 5 comandi di sistema operativi.

### F5.1 — `dispatcher.py`

```python
# dispatcher.py
import time
import logging
from database import get_or_create_user
from config import BBS_NAME, BBS_VERSION

log = logging.getLogger(__name__)

# Registro comandi: "!comando" → funzione handler
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
        return None  # non è un comando BBS — ignora silenziosamente

    parts = text.strip().split(maxsplit=2)
    cmd   = parts[0].lower()           # es. "!post"
    args  = parts[1:] if len(parts)>1 else []

    handler = _HANDLERS.get(cmd)
    if handler is None:
        return f"Cmd sconosciuto: {cmd}\n!help per la lista"

    try:
        return await handler(from_pubkey, args, db)
    except Exception as e:
        log.error(f"Errore handler {cmd}: {e}")
        return "Errore interno BBS"
```

### F5.2 — `modules/system.py` — comandi base

```python
# modules/system.py
import time
from dispatcher import command
from config import BBS_NAME, BBS_VERSION
from database import get_db

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
    row = await db.execute_fetchone(
        "SELECT COUNT(*) as c FROM federation_nodes WHERE status='online'"
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
    rows = await db.execute_fetchall(
        "SELECT name, status FROM federation_nodes ORDER BY status, name"
    )
    if not rows:
        return "Nessun nodo federato configurato"
    lines = [f"{'[ON]' if r['status']=='online' else '[--]'} {r['name']}"
             for r in rows]
    return "\n".join(lines)
```

### ✅ Criteri completamento F5

- [ ] `!ping` risponde entro 30s
- [ ] `!nick Mario` aggiorna il DB e risponde
- [ ] `!help` entra in un singolo messaggio (< 180 chars)
- [ ] Comando sconosciuto → risposta di errore
- [ ] Registrazione automatica utente al primo `!` verificata

---

## Fase 6 — Moduli BBS: Bacheche e Mailbox

**Obiettivo**: Funzionalità BBS complete per gli utenti locali.

### Comandi bacheche

| Comando | Parametri | Comportamento |
|---|---|---|
| `!boards` | — | Lista board con numero post totali |
| `!read <board>` | `[pagina]` | Ultimi 5 post, paginati (default pag. 1) |
| `!post <board> <testo>` | — | Pubblica post, triggera push federazione |

### F6.1 — `modules/boards.py`

```python
# modules/boards.py
import time
from dispatcher import command
from database import make_global_id
from config import BBS_NAME, MAX_POST_LEN

PAGE_SIZE = 5  # post per pagina

@command("!boards")
async def cmd_boards(from_pubkey, args, db) -> str:
    rows = await db.execute_fetchall("""
        SELECT b.name, COUNT(p.id) as cnt
        FROM boards b LEFT JOIN posts p ON b.id = p.board_id
        GROUP BY b.id ORDER BY b.name
    """)
    lines = [f"{r['name']} ({r['cnt']} post)" for r in rows]
    return "Bacheche:\n" + "\n".join(lines)

@command("!read")
async def cmd_read(from_pubkey, args, db) -> str:
    if not args:
        return "Uso: !read <board> [pagina]"

    board_name = args[0]
    page = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
    offset = (page - 1) * PAGE_SIZE

    board = await db.execute_fetchone(
        "SELECT id FROM boards WHERE name=?", (board_name,)
    )
    if not board:
        return f"Board '{board_name}' non trovata. Usa !boards"

    rows = await db.execute_fetchall("""
        SELECT author_nick, text, timestamp, origin_node
        FROM posts WHERE board_id=?
        ORDER BY timestamp DESC LIMIT ? OFFSET ?
    """, (board["id"], PAGE_SIZE, offset))

    if not rows:
        return f"Nessun post in {board_name} (pag. {page})"

    lines = []
    for r in rows:
        origin = "" if r["origin_node"] == BBS_NAME else f"[{r['origin_node']}] "
        nick   = r["author_nick"] or "???"
        ts     = _rel_time(r["timestamp"])
        # Tronca il testo se necessario per rispettare il budget di caratteri
        snippet = r["text"][:60] + ("…" if len(r["text"]) > 60 else "")
        lines.append(f"{origin}{nick} ({ts}): {snippet}")

    return "\n".join(lines)

@command("!post")
async def cmd_post(from_pubkey, args, db) -> str:
    if len(args) < 2:
        return "Uso: !post <board> <testo>"

    board_name = args[0]
    text = " ".join(args[1:])[:MAX_POST_LEN]

    board = await db.execute_fetchone(
        "SELECT id FROM boards WHERE name=?", (board_name,)
    )
    if not board:
        return f"Board '{board_name}' non trovata. Usa !boards"

    # Recupera nickname utente
    user = await db.execute_fetchone(
        "SELECT nickname FROM users WHERE pubkey=?", (from_pubkey,)
    )
    nick = user["nickname"] if user and user["nickname"] else from_pubkey[:8]

    gid = make_global_id(BBS_NAME, text)
    now = int(time.time())

    await db.execute("""
        INSERT INTO posts (global_id, board_id, author_pubkey, author_nick,
                           origin_node, text, timestamp, is_local)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    """, (gid, board["id"], from_pubkey, nick, BBS_NAME, text, now))
    await db.commit()

    # TODO Fase 7: triggera push federazione con questo post
    return f"Post pubblicato in {board_name}"

def _rel_time(ts: int) -> str:
    """Restituisce tempo relativo compatto: '5m', '2h', '3g'."""
    delta = int(time.time()) - ts
    if delta < 3600:   return f"{delta//60}m"
    if delta < 86400:  return f"{delta//3600}h"
    return f"{delta//86400}g"
```

### Comandi mailbox

| Comando | Parametri | Comportamento |
|---|---|---|
| `!inbox` | — | Lista mail non lette |
| `!mail <dest_nick> <testo>` | — | Invia mail (store-and-forward, anche inter-nodo) |
| `!mail read <id>` | — | Legge mail per ID |

> ℹ️ **Nota comando `!read`**: il conflitto con `!read <board>` è risolto usando `!mail read <id>` come sottocomando di `!mail`, non come variante di `!read`.

### F6.2 — `modules/mail.py`

```python
# modules/mail.py
import time
from dispatcher import command
from database import make_global_id
from config import BBS_NAME, MAX_MAIL_LEN, MAX_INBOX

@command("!inbox")
async def cmd_inbox(from_pubkey, args, db) -> str:
    rows = await db.execute_fetchall("""
        SELECT id, from_nick, timestamp, read
        FROM mail WHERE to_pubkey=?
        ORDER BY timestamp DESC LIMIT ?
    """, (from_pubkey, MAX_INBOX))

    if not rows:
        return "Inbox vuota"

    unread = sum(1 for r in rows if not r["read"])
    lines = [f"[{'N' if not r['read'] else 'L'}] #{r['id']} {r['from_nick'] or '???'} ({_rel_time(r['timestamp'])})"
             for r in rows]
    return f"Inbox ({unread} nuove):\n" + "\n".join(lines)

@command("!mail")
async def cmd_mail(from_pubkey, args, db) -> str:
    if not args:
        return "Uso: !mail <nick_dest> <testo>  |  !mail read <id>"

    # Sottocomando: !mail read <id>
    if args[0].lower() == "read":
        return await _read_mail(from_pubkey, args[1:], db)

    # Invio: !mail <nick_dest> <testo>
    if len(args) < 2:
        return "Uso: !mail <nick_dest> <testo>"

    dest_nick = args[0]
    text = " ".join(args[1:])[:MAX_MAIL_LEN]

    # Cerca destinatario nel DB locale
    dest = await db.execute_fetchone(
        "SELECT pubkey FROM users WHERE nickname=?", (dest_nick,)
    )

    gid = make_global_id(BBS_NAME, text)
    now = int(time.time())

    # Recupera nick mittente
    sender = await db.execute_fetchone(
        "SELECT nickname FROM users WHERE pubkey=?", (from_pubkey,)
    )
    from_nick = sender["nickname"] if sender and sender["nickname"] else from_pubkey[:8]

    if dest:
        # Destinatario locale — salva direttamente
        await db.execute("""
            INSERT INTO mail (global_id, from_pubkey, from_nick,
                              to_pubkey, to_nick, text, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (gid, from_pubkey, from_nick, dest["pubkey"], dest_nick, text, now))
        await db.commit()
        return f"Mail inviata a {dest_nick}"
    else:
        # Destinatario non trovato localmente — salva come da recapitare via federazione
        await db.execute("""
            INSERT INTO mail (global_id, from_pubkey, from_nick,
                              to_pubkey, to_nick, text, timestamp,
                              delivered, federation_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'pending')
        """, (gid, from_pubkey, from_nick, "PENDING", dest_nick, text, now))
        await db.commit()
        # TODO Fase 7: push mail ai peer federati
        return f"Mail in coda per {dest_nick} (ricerca su nodi federati)"

async def _read_mail(from_pubkey, args, db) -> str:
    if not args or not args[0].isdigit():
        return "Uso: !mail read <id>"
    mail_id = int(args[0])
    row = await db.execute_fetchone(
        "SELECT * FROM mail WHERE id=? AND to_pubkey=?", (mail_id, from_pubkey)
    )
    if not row:
        return f"Mail #{mail_id} non trovata"
    await db.execute(
        "UPDATE mail SET read=1 WHERE id=?", (mail_id,)
    )
    await db.commit()
    return f"Da: {row['from_nick'] or '???'}\n{row['text']}"

def _rel_time(ts: int) -> str:
    delta = int(time.time()) - ts
    if delta < 3600:   return f"{delta//60}m"
    if delta < 86400:  return f"{delta//3600}h"
    return f"{delta//86400}g"
```

### ✅ Criteri completamento F6

- [ ] `!boards` elenca le 3 board predefinite con conteggio post
- [ ] `!post Generale "ciao"` → post salvato e visibile con `!read Generale`
- [ ] `!mail Mario "ciao"` → mail salvata, `!inbox` la mostra, `!mail read 1` la legge
- [ ] Paginazione `!read Generale 2` funzionante
- [ ] Store-and-forward: mail visibile anche dopo riavvio BBS

---

## Fase 7 — Protocollo di Federazione

**Obiettivo**: Push immediato tra nodi BBS, anti-loop, sincronizzazione post/utenti/stato/mail.

### Formato pacchetto federazione

```
Byte  Campo        Dimensione  Descrizione
────  ─────────    ──────────  ────────────────────────────────────────
 0    marker       1 byte      0xBB — identifica pacchetto federazione
 1    type         1 byte      0x01=POST 0x02=USER_SYNC
                               0x03=NODE_STATUS 0x04=MAIL
 2    ttl          1 byte      Default=3, decrementa ad ogni hop BBS
                               (reserved in v1 con peering statico)
 3–10 msg_id       8 byte      SHA256[:8] — chiave anti-loop
11–14 origin       4 byte      pubkey prefix nodo BBS di origine
15–18 timestamp    4 byte      unix timestamp little-endian
19+   payload      variabile   Specifico per tipo (vedi sotto)
```

> ℹ️ Il campo `ttl` è **reserved in v1** (peering statico, nessun hop BBS intermedio). Viene mantenuto nel formato per compatibilità futura.

### Payload per tipo

```
POST (0x01)
  global_id   : length-prefixed string (16 hex chars) — per deduplicazione
  board_name  : length-prefixed string fino a 20 byte
  author_nick : length-prefixed string fino a 20 byte
  text        : string fino a fine pacchetto

USER_SYNC (0x02)
  pubkey      : 32 byte (pubkey completa)
  nickname    : string fino a 20 byte

NODE_STATUS (0x03)
  name        : string fino a 20 byte
  uptime_secs : 4 byte uint32
  version     : string fino a 10 byte

MAIL (0x04)
  global_id   : length-prefixed string (16 hex chars) — per deduplicazione
  to_nick     : length-prefixed string fino a 20 byte  (hint routing)
  from_nick   : length-prefixed string fino a 20 byte
  text        : string fino a fine pacchetto
  (il to_pubkey viene risolto dal nodo ricevente tramite to_nick)
```

### F7.1 — `modules/federation.py` (struttura base)

```python
# modules/federation.py
import time
import struct
import hashlib
import logging
from config import (BBS_NAME, BBS_VERSION, FEDERATION_PEERS,
                    NODE_STATUS_INTERVAL, PEER_TIMEOUT,
                    FEDERATION_RATE_LIMIT)

log = logging.getLogger(__name__)

MARKER        = 0xBB
TYPE_POST     = 0x01
TYPE_USER     = 0x02
TYPE_STATUS   = 0x03
TYPE_MAIL     = 0x04

def build_header(msg_type: int, origin_prefix: bytes, msg_id: bytes) -> bytes:
    """Costruisce i 19 byte di header federazione."""
    ttl = 3
    ts  = int(time.time())
    return struct.pack("<BBB", MARKER, msg_type, ttl) \
           + msg_id[:8] \
           + origin_prefix[:4] \
           + struct.pack("<I", ts)  # totale: 3+8+4+4 = 19 byte

def make_msg_id(content: str) -> bytes:
    return hashlib.sha256(f"{time.time_ns()}:{content}".encode()).digest()[:8]

async def is_seen(db, msg_id: bytes) -> bool:
    """Controlla se il msg_id è già stato processato (anti-loop)."""
    mid_hex = msg_id.hex()
    row = await db.execute_fetchone(
        "SELECT 1 FROM federation_seen WHERE msg_id=?", (mid_hex,)
    )
    return row is not None

async def mark_seen(db, msg_id: bytes):
    await db.execute(
        "INSERT OR IGNORE INTO federation_seen (msg_id, received_at) VALUES (?, ?)",
        (msg_id.hex(), int(time.time()))
    )
    await db.commit()

async def process_incoming(db, raw: bytes) -> bool:
    """
    Processa un pacchetto federazione in arrivo.
    Restituisce True se processato, False se scartato (già visto o malformato).
    """
    if len(raw) < 19 or raw[0] != MARKER:
        return False

    msg_type = raw[1]
    msg_id   = raw[3:11]

    if await is_seen(db, msg_id):
        log.debug(f"Fed packet già visto: {msg_id.hex()}")
        return False

    await mark_seen(db, msg_id)

    if   msg_type == TYPE_POST:   await _handle_post(db, raw[19:])
    elif msg_type == TYPE_USER:   await _handle_user_sync(db, raw[19:])
    elif msg_type == TYPE_STATUS: await _handle_node_status(db, raw[19:])
    elif msg_type == TYPE_MAIL:   await _handle_mail(db, raw[19:])
    else:
        log.warning(f"Tipo federazione sconosciuto: {msg_type}")

    return True

async def _handle_post(db, payload: bytes):
    # TODO: parsing payload, INSERT INTO posts con is_local=0
    pass

async def _handle_user_sync(db, payload: bytes):
    # TODO: upsert users con nick aggiornato
    pass

async def _handle_node_status(db, payload: bytes):
    # TODO: UPDATE federation_nodes SET status='online', last_seen=now
    pass

async def _handle_mail(db, payload: bytes):
    # TODO: risolvi to_nick → to_pubkey locale, INSERT INTO mail se destinatario locale
    pass
```

### F7.2 — Loop NODE_STATUS periodico

```python
# Da aggiungere in main.py
async def federation_status_loop(conn, db):
    """Invia NODE_STATUS ai peer ogni NODE_STATUS_INTERVAL secondi.
    Invia UN peer per ciclo (evita burst che saturano il rate limit)."""
    peer_index = 0
    while True:
        await asyncio.sleep(NODE_STATUS_INTERVAL)
        peers = await db.execute_fetchall(
            "SELECT pubkey, name FROM federation_nodes WHERE is_peer=1"
        )
        if not peers:
            continue
        peer = peers[peer_index % len(peers)]
        peer_index += 1
        # TODO: costruisci e invia pacchetto NODE_STATUS al peer
        log.debug(f"NODE_STATUS inviato a {peer['name']}")
```

### F7.3 — Cleanup periodico

```python
# Da aggiungere in main.py
async def maintenance_loop(db):
    """Task di manutenzione periodica."""
    while True:
        await asyncio.sleep(3600)  # ogni ora
        # Pulizia federation_seen più vecchi di 7 giorni
        from database import cleanup_federation_seen
        await cleanup_federation_seen(db, days=7)
        # Marca offline i peer che non rispondono da > PEER_TIMEOUT
        from config import PEER_TIMEOUT
        cutoff = int(time.time()) - PEER_TIMEOUT
        await db.execute(
            "UPDATE federation_nodes SET status='offline' WHERE last_seen < ? AND is_peer=1",
            (cutoff,)
        )
        await db.commit()
        log.info("Manutenzione completata")
```

### ✅ Criteri completamento F7

- [ ] Post su BBS-A appare su BBS-B senza loop (testato con 2 nodi)
- [ ] Anti-loop: stesso post non duplicato con 3 nodi in rete
- [ ] Mail da utente BBS-A recapitata a utente BBS-B
- [ ] `!nodes` mostra correttamente stati online/offline
- [ ] NODE_STATUS non satura il rate limit (invio sequenziale verificato)

---

## Comandi v1 — Riepilogo Completo

| Comando | Parametri | Modulo | Note |
|---|---|---|---|
| `!help` | — | Sistema | Max 180 chars di risposta |
| `!ping` | — | Sistema | Test connettività |
| `!info` | — | Sistema | Stato BBS e nodi federati |
| `!nick <n>` | nickname | Utenti | Max 20 chars |
| `!nodes` | — | Federazione | Lista peer online/offline |
| `!boards` | — | Bacheche | Lista con conteggio post |
| `!read <board>` | `[pagina]` | Bacheche | 5 post per pagina |
| `!post <board> <testo>` | — | Bacheche | Max 180 chars testo |
| `!inbox` | — | Mailbox | Lista mail non lette |
| `!mail <nick> <testo>` | — | Mailbox | Store-and-forward, anche inter-nodo |
| `!mail read <id>` | — | Mailbox | Legge mail per ID |

---

## Fuori Scope v1

| Feature | Motivo |
|---|---|
| Moderazione post | Complessità non necessaria — sysop gestisce manualmente |
| Creazione board dinamica | Rischio spam — board fisse in v1 |
| Thread e risposte | Troppo complesso con MTU 255 byte |
| File e allegati | Impossibile: MTU 255 byte per pacchetto |
| Ruoli utente multipli | Solo sysop hardcoded — sistema ruoli in v2 |
| Web dashboard | Fuori scope: BBS opera interamente via LoRa |
| Gossip peer list | Discovery transitiva automatica → v2 |
| Canali pubblici come trigger | Solo messaggi diretti in v1 |

---

## Aree da Analizzare

| Area | Priorità | Note |
|---|---|---|
| Sicurezza applicativa (spam/flood) | 🔴 CRITICA | Rate limiting per utente, blacklist pubkey |
| Parser comandi robusto | 🔴 CRITICA | Input malformati, encoding, injection |
| Risoluzione contatto per pubkey in `sender_loop` | 🔴 CRITICA | Il modo esatto per trovare il contatto dalla pubkey va verificato con la libreria reale |
| Interfaccia sysop locale | 🟡 ALTA | CLI sul RPi: ban, delpost, addpeer |
| Versioning pacchetti federazione | 🟡 ALTA | Compatibilità tra nodi con versioni diverse |
| Backup e recovery | 🟡 ALTA | Backup SQLite + chiave privata Companion |
| `execute_fetchone` / `execute_fetchall` | 🟡 ALTA | Aggiungere questi helper nel `database.py` — non esistono nativamente in aiosqlite |
| Testing e simulazione offline | 🟠 MEDIA | Mock del Companion senza hardware |
| Script deploy automatico RPi | 🟠 MEDIA | Installazione, aggiornamenti |
| Discovery utenti inter-nodo | 🟢 BASSA | `!whois <nick>` su nodi federati |
| Quote e limiti per utente | 🟢 BASSA | Max post/giorno, retention automatica |
| Documentazione `!help` compatta | 🟢 BASSA | < 180 chars, comprensibile |

---

---

> 📁 **Documentazione dettagliata per capitolo**: vedi cartella `docs/` con 14 documenti specifici che espandono ogni sezione di questa roadmap con codice corretto, diagrammi, troubleshooting e criteri di completamento ampliati.

*MeshCore BBS Roadmap v1.1 — documento di lavoro — aggiornato iterativamente*
