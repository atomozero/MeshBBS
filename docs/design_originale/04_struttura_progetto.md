# 04 — Struttura del Progetto

> Riferimento: Roadmap sezione 4

---

## Layout Directory

```
meshbbs/
├── main.py              # entry point: avvia asyncio event loop
├── config.py            # configurazione centralizzata
├── connection.py        # gestione connessione TCP + auto-reconnect
├── dispatcher.py        # router messaggi in arrivo -> modulo corretto
├── queue.py             # coda messaggi in uscita con priorita'
├── database.py          # wrapper aiosqlite + query helpers
├── logger.py            # logging strutturato con structlog
├── utils.py             # utility condivise (es. _rel_time, sanitize)
├── modules/
│   ├── __init__.py
│   ├── system.py        # comandi base: !help !ping !info !nick !nodes
│   ├── users.py         # registrazione, gestione utenti
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

**Nota**: rispetto alla roadmap originale sono stati aggiunti:
- `modules/system.py` — mancava nella struttura ma il codice era gia' presente
- `utils.py` — per funzioni condivise come `_rel_time()` (duplicata in boards.py e mail.py)
- `tests/` — directory test, assente nella roadmap originale
- `scripts/` — per script standalone (init_db.py, test_connection.py) separati dal codice principale

## config.py — Struttura Completa

```python
# config.py
import os

# --- Connessione Companion ---
COMPANION_HOST = os.getenv("BBS_HOST", "192.168.1.50")
COMPANION_PORT = int(os.getenv("BBS_PORT", "5000"))

# --- Identita' BBS ---
BBS_NAME     = os.getenv("BBS_NAME", "BBS-NomeNodo")
BBS_VERSION  = "1.0.0"

# --- Database ---
DB_PATH      = os.getenv("BBS_DB", "/home/pi/meshbbs/bbs.db")

# --- Federazione ---
FEDERATION_PEERS = []  # lista pubkey peer statici — popolata manualmente
FEDERATION_RATE_LIMIT = 3       # max msg federazione al minuto per peer
NODE_STATUS_INTERVAL  = 900     # secondi tra NODE_STATUS (15 min)
PEER_TIMEOUT          = 2700    # secondi prima di marcare peer offline (45 min)

# --- Limiti ---
MAX_POST_LEN  = 180   # caratteri — vedi nota MTU
MAX_MAIL_LEN  = 180
MAX_INBOX     = 20    # mail per utente
MAX_NICK_LEN  = 20    # lunghezza massima nickname

# --- Sicurezza ---
RATE_LIMIT_USER  = 10   # max comandi per minuto per utente
BLACKLIST_PUBKEYS = []  # pubkey bannate

# --- Logging ---
LOG_FILE     = "/home/pi/meshbbs/bbs.log"
LOG_LEVEL    = "INFO"
```

## Nota MTU

Il pacchetto MeshCore ha MTU fisico di **255 byte**:

```
255 byte totali
 - ~25 byte header protocollo MeshCore
 = ~230 byte payload applicativo
 - ~10 byte prefisso risposta BBS ("[BBS] " ecc.)
 = ~220 byte per testo utente

Limite prudenziale adottato: 180 caratteri
```

Questo vincolo impatta:
- Lunghezza massima post e mail
- Formato risposte dei comandi (devono stare in un pacchetto)
- Design del protocollo di federazione (header compatto)

## Convenzioni di Codice

- Tutto il codice e' **asincrono** (`async/await`)
- Le connessioni DB vengono aperte e chiuse per ogni richiesta (no connection pool — SQLite non ne beneficia)
- I moduli registrano i loro comandi tramite il decoratore `@command("!nome")`
- Il logging usa `structlog` per output strutturato e filtrabile
