# 07 — Fase 3: Database e Schema

> Riferimento: Roadmap Fase 3
> **Puo' procedere in parallelo con Fase 2** — non dipende dalla connessione TCP.

---

## Obiettivo

Creare il database SQLite con schema completo e verificare insert/query per ogni tabella.

## F3.1 — Script di Inizializzazione

```python
# scripts/init_db.py
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

PRAGMA journal_mode=WAL;
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

**Differenze rispetto alla roadmap originale**:
- Aggiunta colonna `federation_status` nella tabella `mail`
- Aggiunto `PRAGMA journal_mode=WAL` per performance

## F3.2 — database.py Wrapper Asincrono

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
    """Genera global_id univoco per record federati.
    IMPORTANTE: origin_pubkey deve essere la pubkey del nodo, non il nome."""
    raw = f"{origin_pubkey}:{time.time_ns()}:{content}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

# --- Helper methods ---
# aiosqlite NON ha execute_fetchone/execute_fetchall nativamente.
# Questi helper vanno implementati come funzioni standalone.

async def execute_fetchone(db, query: str, params=()) -> dict | None:
    """Esegue query e restituisce una riga o None."""
    cursor = await db.execute(query, params)
    row = await cursor.fetchone()
    return row

async def execute_fetchall(db, query: str, params=()) -> list:
    """Esegue query e restituisce tutte le righe."""
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return rows

async def get_or_create_user(db, pubkey: str, nickname: str, origin_node: str):
    now = int(time.time())
    await db.execute("""
        INSERT INTO users (pubkey, nickname, first_seen, last_seen, origin_node)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(pubkey) DO UPDATE SET last_seen=excluded.last_seen
    """, (pubkey, nickname, now, now, origin_node))
    await db.commit()

async def cleanup_federation_seen(db, days: int = 7):
    """Rimuove msg_id piu' vecchi di N giorni dall'anti-loop table."""
    cutoff = int(time.time()) - (days * 86400)
    await db.execute(
        "DELETE FROM federation_seen WHERE received_at < ?", (cutoff,)
    )
    await db.commit()
```

**Nota critica**: la roadmap originale usava `db.execute_fetchone()` e `db.execute_fetchall()` come se fossero metodi di `aiosqlite.Connection`, ma **non esistono**. Le funzioni helper sopra risolvono il problema.

## F3.3 — Script di Verifica

```python
# scripts/test_db.py
import sqlite3

DB_PATH = "bbs.db"

def verify():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Verifica tabelle
    tables = [r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    expected = {"users", "boards", "posts", "mail", "federation_nodes", "federation_seen"}
    assert expected.issubset(set(tables)), f"Tabelle mancanti: {expected - set(tables)}"

    # Verifica board predefinite
    boards = conn.execute("SELECT name FROM boards").fetchall()
    assert len(boards) == 3, f"Board attese: 3, trovate: {len(boards)}"

    # Test insert/query users
    import time, hashlib
    now = int(time.time())
    conn.execute(
        "INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?)",
        ("test_pubkey_abc123", "TestUser", now, now, "BBS-Test")
    )
    conn.commit()

    user = conn.execute("SELECT * FROM users WHERE pubkey=?", ("test_pubkey_abc123",)).fetchone()
    assert user["nickname"] == "TestUser"

    # Cleanup
    conn.execute("DELETE FROM users WHERE pubkey='test_pubkey_abc123'")
    conn.commit()
    conn.close()
    print("Tutte le verifiche superate!")

if __name__ == "__main__":
    verify()
```

## Criteri di Completamento

- [ ] `python scripts/init_db.py` crea il DB senza errori
- [ ] Tutte e 6 le tabelle presenti
- [ ] 3 board predefinite inserite
- [ ] `make_global_id()` produce ID diversi per chiamate successive
- [ ] `get_or_create_user()` funziona con upsert (non duplica)
- [ ] `execute_fetchone()` e `execute_fetchall()` testati e funzionanti
- [ ] `PRAGMA journal_mode` confermato come WAL
