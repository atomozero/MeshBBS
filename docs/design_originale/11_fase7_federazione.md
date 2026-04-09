# 11 — Fase 7: Protocollo di Federazione

> Riferimento: Roadmap Fase 7

---

## Obiettivo

Push immediato tra nodi BBS, anti-loop, sincronizzazione post/utenti/stato/mail.

## Dipendenze

- Tutte le fasi precedenti completate
- Almeno 2 nodi BBS operativi per il testing

---

## Formato Pacchetto Federazione

```
Byte  Campo        Dimensione  Descrizione
----  ---------    ----------  ----------------------------------------
 0    marker       1 byte      0xBB — identifica pacchetto federazione
 1    type         1 byte      0x01=POST 0x02=USER_SYNC
                               0x03=NODE_STATUS 0x04=MAIL
 2    ttl          1 byte      Default=3, decrementa ad ogni hop BBS
                               (reserved in v1 con peering statico)
 3-10 msg_id       8 byte      SHA256[:8] — chiave anti-loop
11-14 origin       4 byte      pubkey prefix nodo BBS di origine
15-18 timestamp    4 byte      unix timestamp little-endian
19+   payload      variabile   Specifico per tipo (vedi sotto)
```

**Header totale: 19 byte** (non 20 come indicato nel `struct.pack` della roadmap originale — vedi correzione sotto).

> Il campo `ttl` e' **reserved in v1** (peering statico, nessun hop BBS intermedio). Viene mantenuto nel formato per compatibilita' futura.

### Correzione struct.pack

La roadmap originale usava `struct.pack("<BBBBB", ...)` che produce 5 byte, ma l'header dovrebbe avere:
- 1 byte marker + 1 byte type + 1 byte ttl = 3 byte (non 5)
- Seguiti da 8 byte msg_id + 4 byte origin + 4 byte timestamp = 16 byte
- Totale: 19 byte

Il `struct.pack` corretto e':

```python
header = struct.pack("<BBB", MARKER, msg_type, ttl) + msg_id[:8] + origin[:4] + struct.pack("<I", ts)
# 3 + 8 + 4 + 4 = 19 byte
```

## Payload per Tipo

### POST (0x01) — max ~200 byte

```
Offset  Campo        Lunghezza   Encoding
------  ----------   ---------   --------
0       gid_len      1 byte      lunghezza global_id
1       global_id    gid_len     hex string (16 chars = 16 byte)
+0      board_len    1 byte      lunghezza nome board
+1      board_name   board_len   UTF-8
+0      nick_len     1 byte      lunghezza nickname autore
+1      author_nick  nick_len    UTF-8
+0      text         restante    UTF-8 (fino a fine pacchetto)
```

> Il `global_id` viene trasmesso per garantire la deduplicazione: il nodo ricevente usa lo stesso ID del nodo originante per il constraint UNIQUE.

### USER_SYNC (0x02)

```
Offset  Campo        Lunghezza   Encoding
------  ----------   ---------   --------
0       pubkey_len   1 byte      lunghezza pubkey
1       pubkey       pubkey_len  hex string
+0      nick_len     1 byte      lunghezza nickname
+1      nickname     nick_len    UTF-8
```

### NODE_STATUS (0x03)

```
Offset  Campo        Lunghezza   Encoding
------  ----------   ---------   --------
0       name_len     1 byte      lunghezza nome nodo
1       name         name_len    UTF-8
+0      uptime       4 byte      uint32 little-endian (secondi)
+0      ver_len      1 byte      lunghezza versione
+1      version      ver_len     ASCII
```

### MAIL (0x04)

```
Offset  Campo        Lunghezza   Encoding
------  ----------   ---------   --------
0       gid_len      1 byte      lunghezza global_id
1       global_id    gid_len     hex string (16 chars)
+0      to_nick_len  1 byte      lunghezza nick destinatario
+1      to_nick      to_nick_len UTF-8
+0      from_nick_len 1 byte     lunghezza nick mittente
+1      from_nick    from_nick_len UTF-8
+0      text         restante    UTF-8
```

> **Nota**: il `to_pubkey` viene risolto dal nodo ricevente tramite `to_nick`. Se il nick non e' trovato, la mail viene scartata (in v1 — in v2 potrebbe essere inoltrata). Il `global_id` e' trasmesso per deduplicazione.

## F7.1 — modules/federation.py

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
    return (struct.pack("<BBB", MARKER, msg_type, ttl)
            + msg_id[:8]
            + origin_prefix[:4]
            + struct.pack("<I", ts))

def make_msg_id(content: str) -> bytes:
    return hashlib.sha256(f"{time.time_ns()}:{content}".encode()).digest()[:8]

async def is_seen(db, msg_id: bytes) -> bool:
    """Controlla se il msg_id e' gia' stato processato (anti-loop)."""
    from database import execute_fetchone
    mid_hex = msg_id.hex()
    row = await execute_fetchone(
        db, "SELECT 1 FROM federation_seen WHERE msg_id=?", (mid_hex,)
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
    Restituisce True se processato, False se scartato.
    """
    if len(raw) < 19 or raw[0] != MARKER:
        return False

    msg_type = raw[1]
    # ttl = raw[2]  # reserved in v1
    msg_id   = raw[3:11]

    if await is_seen(db, msg_id):
        log.debug(f"Fed packet gia' visto: {msg_id.hex()}")
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
    """Riceve un post federato e lo salva localmente.
    
    IMPORTANTE: il global_id deve essere trasmesso nel payload dal nodo
    di origine, NON rigenerato dal ricevente. Rigenerarlo produrrebbe
    un ID diverso, vanificando la deduplicazione anti-loop.
    """
    try:
        pos = 0
        # global_id: 16 byte hex string trasmessa dal nodo di origine
        gid_len = payload[pos]; pos += 1
        global_id = payload[pos:pos+gid_len].decode(); pos += gid_len
        board_len = payload[pos]; pos += 1
        board_name = payload[pos:pos+board_len].decode(); pos += board_len
        nick_len = payload[pos]; pos += 1
        author_nick = payload[pos:pos+nick_len].decode(); pos += nick_len
        text = payload[pos:].decode()

        from database import execute_fetchone
        board = await execute_fetchone(
            db, "SELECT id FROM boards WHERE name=?", (board_name,)
        )
        if not board:
            log.warning(f"Board federata '{board_name}' non trovata, scarto post")
            return

        # Usa il global_id originale per deduplicazione
        origin_hex = "federation"  # in v2: estrarre dall'header origin
        now = int(time.time())
        await db.execute("""
            INSERT OR IGNORE INTO posts
            (global_id, board_id, author_pubkey, author_nick,
             origin_node, text, timestamp, is_local)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (global_id, board["id"], "", author_nick, origin_hex, text, now))
        await db.commit()
        log.info(f"Post federato ricevuto: {author_nick} in {board_name}")
    except Exception as e:
        log.error(f"Errore parsing post federato: {e}")

async def _handle_user_sync(db, payload: bytes):
    """Sincronizza un utente da un nodo federato."""
    try:
        pos = 0
        pk_len = payload[pos]; pos += 1
        pubkey = payload[pos:pos+pk_len].decode(); pos += pk_len
        nick_len = payload[pos]; pos += 1
        nickname = payload[pos:pos+nick_len].decode()

        from database import get_or_create_user
        await get_or_create_user(db, pubkey, nickname, "federation")
        log.info(f"User sync federato: {nickname} ({pubkey[:8]})")
    except Exception as e:
        log.error(f"Errore parsing user sync: {e}")

async def _handle_node_status(db, payload: bytes):
    """Aggiorna lo stato di un nodo federato."""
    try:
        pos = 0
        name_len = payload[pos]; pos += 1
        name = payload[pos:pos+name_len].decode(); pos += name_len
        uptime = struct.unpack_from("<I", payload, pos)[0]; pos += 4
        ver_len = payload[pos]; pos += 1
        version = payload[pos:pos+ver_len].decode()

        now = int(time.time())
        await db.execute("""
            UPDATE federation_nodes
            SET status='online', last_seen=?, name=?
            WHERE is_peer=1 AND name=?
        """, (now, name, name))
        await db.commit()
        log.info(f"NODE_STATUS da {name}: up={uptime}s v={version}")
    except Exception as e:
        log.error(f"Errore parsing node status: {e}")

async def _handle_mail(db, payload: bytes):
    """Riceve mail federata e la recapita se il destinatario e' locale.
    
    IMPORTANTE: il global_id viene trasmesso nel payload per deduplicazione.
    Il to_pubkey viene risolto localmente tramite to_nick.
    """
    try:
        pos = 0
        # global_id trasmesso dal nodo mittente
        gid_len = payload[pos]; pos += 1
        global_id = payload[pos:pos+gid_len].decode(); pos += gid_len
        to_nick_len = payload[pos]; pos += 1
        to_nick = payload[pos:pos+to_nick_len].decode(); pos += to_nick_len
        from_nick_len = payload[pos]; pos += 1
        from_nick = payload[pos:pos+from_nick_len].decode(); pos += from_nick_len
        text = payload[pos:].decode()

        from database import execute_fetchone
        dest = await execute_fetchone(
            db, "SELECT pubkey FROM users WHERE nickname=?", (to_nick,)
        )
        if not dest:
            log.info(f"Mail federata per '{to_nick}' — destinatario non locale, scarto")
            return

        now = int(time.time())
        # to_pubkey e' la pubkey REALE del destinatario locale,
        # risolta dal nick. Questo permette a !inbox di funzionare.
        await db.execute("""
            INSERT OR IGNORE INTO mail
            (global_id, from_pubkey, from_nick, to_pubkey, to_nick,
             text, timestamp, delivered, read, federation_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 'delivered')
        """, (global_id, "", from_nick, dest["pubkey"], to_nick, text, now))
        await db.commit()
        log.info(f"Mail federata recapitata a {to_nick}")
    except Exception as e:
        log.error(f"Errore parsing mail federata: {e}")
```

## F7.2 — Loop NODE_STATUS Periodico

```python
# Da aggiungere in main.py
async def federation_status_loop(conn, db):
    """Invia NODE_STATUS ai peer ogni NODE_STATUS_INTERVAL secondi.
    Invia UN peer per ciclo per evitare burst che saturano il rate limit."""
    peer_index = 0
    while True:
        await asyncio.sleep(NODE_STATUS_INTERVAL)
        from database import execute_fetchall
        peers = await execute_fetchall(
            db, "SELECT pubkey, name FROM federation_nodes WHERE is_peer=1"
        )
        if not peers:
            continue
        peer = peers[peer_index % len(peers)]
        peer_index += 1
        # Costruisci e invia pacchetto NODE_STATUS
        log.debug(f"NODE_STATUS inviato a {peer['name']}")
```

> **Rate limit**: con NODE_STATUS_INTERVAL=900s e invio sequenziale di 1 peer per ciclo, anche con 10 peer il rate e' ~0.67 msg/min — ben sotto il limite di 3 msg/min.

## F7.3 — Cleanup Periodico

```python
# Da aggiungere in main.py
async def maintenance_loop(db):
    """Task di manutenzione periodica — ogni ora."""
    while True:
        await asyncio.sleep(3600)
        # Pulizia federation_seen > 7 giorni
        from database import cleanup_federation_seen
        await cleanup_federation_seen(db, days=7)
        # Marca offline peer non visti da > PEER_TIMEOUT
        cutoff = int(time.time()) - PEER_TIMEOUT
        await db.execute(
            "UPDATE federation_nodes SET status='offline' "
            "WHERE last_seen < ? AND is_peer=1",
            (cutoff,)
        )
        await db.commit()
        log.info("Manutenzione completata")
```

## Anti-Loop: Come Funziona

```
BBS-A crea post -> genera msg_id (SHA256[:8])
    |
    +-> Invia a BBS-B con msg_id nel header
    +-> Invia a BBS-C con msg_id nel header
    
BBS-B riceve:
    1. Controlla federation_seen per msg_id
    2. Non trovato -> processa e salva msg_id in federation_seen
    3. (In v2) Potrebbe inoltrare a BBS-D decrementando TTL

BBS-C riceve:
    1. Stessa procedural

Se BBS-B dovesse ri-inoltrare a BBS-A (v2):
    1. BBS-A controlla federation_seen -> gia' visto -> SCARTA
    -> Loop evitato
```

## Diagramma Sequenza — Post Federato

```
BBS-A                    BBS-B                    BBS-C
  |                        |                        |
  |-- !post Generale hi -->|                        |
  |  (salva localmente)   |                        |
  |                        |                        |
  |===[0xBB|POST|msg_id]==>|                        |
  |                        | (check anti-loop: OK) |
  |                        | (salva is_local=0)    |
  |                        |                        |
  |===[0xBB|POST|msg_id]=========================>|
  |                        |                        | (check: OK)
  |                        |                        | (salva is_local=0)
```

## Criteri di Completamento

- [ ] Post su BBS-A appare su BBS-B senza loop (testato con 2 nodi)
- [ ] Anti-loop: stesso post non duplicato con 3 nodi in rete
- [ ] Mail da utente BBS-A recapitata a utente BBS-B
- [ ] `!nodes` mostra correttamente stati online/offline
- [ ] NODE_STATUS non satura il rate limit (invio sequenziale verificato)
- [ ] Cleanup federation_seen rimuove record > 7 giorni
- [ ] Header federazione esattamente 19 byte
- [ ] Parsing payload robusto (non crasha su pacchetti malformati)
