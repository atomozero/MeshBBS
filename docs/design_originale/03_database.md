# 03 — Schema Database

> Riferimento: Roadmap sezione 3

---

## Filosofia

Il database e' progettato **federation-ready dalla v1**. Ogni record che puo' essere sincronizzato tra nodi ha un `global_id` univoco che serve come chiave di deduplicazione.

## Generazione global_id

```python
import hashlib, time

def make_global_id(origin_pubkey: str, content: str) -> str:
    """Genera un ID globale univoco per un record federato."""
    raw = f"{origin_pubkey}:{time.time_ns()}:{content}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]  # 16 hex chars = 8 byte
```

**Nota critica**: il parametro `origin_pubkey` deve essere la **pubkey del nodo BBS**, non il nome del nodo (`BBS_NAME`). Nel codice della roadmap originale, `boards.py` passava `BBS_NAME` — questo e' stato corretto: usare sempre la pubkey del nodo come origin.

## DDL Completo

### Tabella `users`

```sql
CREATE TABLE IF NOT EXISTS users (
    pubkey       TEXT PRIMARY KEY,       -- pubkey crittografica MeshCore
    nickname     TEXT,                   -- nickname scelto dall'utente
    first_seen   INTEGER NOT NULL,       -- timestamp prima apparizione
    last_seen    INTEGER NOT NULL,       -- timestamp ultima attivita'
    origin_node  TEXT                    -- pubkey del nodo BBS di registrazione
);
```

**Note**:
- La `pubkey` e' l'identita' principale — non esiste login/password
- `origin_node` permette di sapere su quale BBS l'utente si e' registrato per la prima volta
- `last_seen` viene aggiornato ad ogni comando ricevuto (upsert)

### Tabella `boards`

```sql
CREATE TABLE IF NOT EXISTS boards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,    -- nome board (case-sensitive)
    description TEXT                     -- descrizione per !boards
);
```

**Board predefinite v1**:

```sql
INSERT OR IGNORE INTO boards (name, description) VALUES
    ('Generale', 'Discussioni generali'),
    ('Annunci',  'Comunicazioni importanti'),
    ('Tecnica',  'Radio, elettronica, software');
```

### Tabella `posts`

```sql
CREATE TABLE IF NOT EXISTS posts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    global_id     TEXT UNIQUE NOT NULL,  -- deduplicazione federazione
    board_id      INTEGER NOT NULL REFERENCES boards(id),
    author_pubkey TEXT NOT NULL,
    author_nick   TEXT,                  -- denormalizzato per display veloce
    origin_node   TEXT NOT NULL,         -- nodo BBS di origine
    text          TEXT NOT NULL,
    timestamp     INTEGER NOT NULL,
    is_local      BOOLEAN NOT NULL DEFAULT 1  -- 0 = ricevuto via federazione
);
```

**Note**:
- `author_nick` e' denormalizzato intenzionalmente: il nick potrebbe cambiare e vogliamo mostrare il nick al momento della pubblicazione
- `is_local` distingue post originati localmente da quelli ricevuti via federazione
- `global_id` impedisce che lo stesso post venga inserito due volte (UNIQUE constraint)

### Tabella `mail`

```sql
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
    read         BOOLEAN NOT NULL DEFAULT 0
);
```

**Nota critica — mail inter-nodo**: quando il destinatario non e' locale, `to_pubkey` non puo' essere vuota (impedirebbe il lookup in `!inbox`). Soluzioni:
1. Usare un valore sentinel come `"PENDING_FEDERATION"` per mail in attesa di risoluzione
2. Aggiungere una colonna `federation_status` (pending/delivered/failed)
3. Tabella separata `mail_outbox` per mail non ancora recapitate

La soluzione consigliata e' la **opzione 2**: aggiungere `federation_status TEXT DEFAULT NULL` — NULL per mail locali, 'pending'/'delivered'/'failed' per mail inter-nodo.

### Tabella `federation_nodes`

```sql
CREATE TABLE IF NOT EXISTS federation_nodes (
    pubkey       TEXT PRIMARY KEY,
    name         TEXT,
    last_seen    INTEGER,
    status       TEXT NOT NULL DEFAULT 'unknown',  -- online|offline|unknown
    is_peer      BOOLEAN NOT NULL DEFAULT 0        -- peer statico configurato
);
```

### Tabella `federation_seen` (anti-loop)

```sql
CREATE TABLE IF NOT EXISTS federation_seen (
    msg_id       TEXT PRIMARY KEY,
    received_at  INTEGER NOT NULL
);
```

**Manutenzione**: i record piu' vecchi di 7 giorni vengono rimossi periodicamente dal maintenance loop.

## Indici

```sql
CREATE INDEX IF NOT EXISTS idx_posts_board    ON posts(board_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_posts_global   ON posts(global_id);
CREATE INDEX IF NOT EXISTS idx_mail_to        ON mail(to_pubkey, read);
CREATE INDEX IF NOT EXISTS idx_fed_seen_time  ON federation_seen(received_at);
```

## Considerazioni

- **Backup**: il file `bbs.db` e' l'unico stato persistente del BBS. Va backuppato regolarmente.
- **WAL mode**: considerare `PRAGMA journal_mode=WAL` per migliori performance con letture/scritture concorrenti (asyncio).
- **Retention**: in v1 non c'e' pulizia automatica dei post. Per nodi con poco storage, considerare una retention policy (es. max 1000 post per board).
- **Migrazione schema**: in caso di aggiornamenti futuri, prevedere un meccanismo di migrazione (es. `PRAGMA user_version` per tracciare la versione dello schema).
