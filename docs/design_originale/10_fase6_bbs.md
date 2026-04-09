# 10 — Fase 6: Moduli BBS — Bacheche e Mailbox

> Riferimento: Roadmap Fase 6

---

## Obiettivo

Funzionalita' BBS complete per gli utenti locali: bacheche tematiche con post e mailbox privata con store-and-forward.

## Dipendenze

- Fase 5 completata (dispatcher e comandi base)

---

## Comandi Bacheche

| Comando | Parametri | Comportamento |
|---------|-----------|---------------|
| `!boards` | — | Lista board con numero post totali |
| `!read <board>` | `[pagina]` | Ultimi 5 post, paginati (default pag. 1) |
| `!post <board> <testo>` | — | Pubblica post, triggera push federazione |

## F6.1 — modules/boards.py

```python
# modules/boards.py
import time
from dispatcher import command
from database import make_global_id, execute_fetchone, execute_fetchall
from config import BBS_NAME, MAX_POST_LEN
from utils import rel_time

PAGE_SIZE = 5  # post per pagina

@command("!boards")
async def cmd_boards(from_pubkey, args, db) -> str:
    rows = await execute_fetchall(db, """
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

    board = await execute_fetchone(
        db, "SELECT id FROM boards WHERE name=?", (board_name,)
    )
    if not board:
        return f"Board '{board_name}' non trovata. Usa !boards"

    rows = await execute_fetchall(db, """
        SELECT author_nick, text, timestamp, origin_node
        FROM posts WHERE board_id=?
        ORDER BY timestamp DESC LIMIT ? OFFSET ?
    """, (board["id"], PAGE_SIZE, offset))

    if not rows:
        return f"Nessun post in {board_name} (pag. {page})"

    lines = []
    for r in rows:
        origin = "" if r["origin_node"] == BBS_NAME else f"[{r['origin_node'][:6]}] "
        nick   = r["author_nick"] or "???"
        ts     = rel_time(r["timestamp"])
        snippet = r["text"][:60] + ("..." if len(r["text"]) > 60 else "")
        lines.append(f"{origin}{nick} ({ts}): {snippet}")

    return "\n".join(lines)

@command("!post")
async def cmd_post(from_pubkey, args, db) -> str:
    if len(args) < 2:
        return "Uso: !post <board> <testo>"

    board_name = args[0]
    text = " ".join(args[1:])[:MAX_POST_LEN]

    board = await execute_fetchone(
        db, "SELECT id FROM boards WHERE name=?", (board_name,)
    )
    if not board:
        return f"Board '{board_name}' non trovata. Usa !boards"

    user = await execute_fetchone(
        db, "SELECT nickname FROM users WHERE pubkey=?", (from_pubkey,)
    )
    nick = user["nickname"] if user and user["nickname"] else from_pubkey[:8]

    # NOTA: origin_pubkey deve essere la pubkey del NODO BBS, non dell'utente.
    # In v1, usiamo BBS_NAME come placeholder finche' non otteniamo la pubkey
    # reale del companion alla prima connessione (da salvare in config a runtime).
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
```

**Correzioni rispetto alla roadmap originale**:
- Usa `execute_fetchone/fetchall` come funzioni standalone
- `_rel_time` spostata in `utils.py` come `rel_time`
- `origin_node` nel display troncato a 6 char per risparmiare spazio
- Nota sulla correzione `make_global_id` (pubkey vs BBS_NAME)

---

## Comandi Mailbox

| Comando | Parametri | Comportamento |
|---------|-----------|---------------|
| `!inbox` | — | Lista mail non lette |
| `!mail <dest_nick> <testo>` | — | Invia mail (store-and-forward, anche inter-nodo) |
| `!mail read <id>` | — | Legge mail per ID |

> **Nota comando `!read`**: il conflitto con `!read <board>` e' risolto usando `!mail read <id>` come sottocomando di `!mail`, non come variante di `!read`.

## F6.2 — modules/mail.py

```python
# modules/mail.py
import time
from dispatcher import command
from database import make_global_id, execute_fetchone, execute_fetchall
from config import BBS_NAME, MAX_MAIL_LEN, MAX_INBOX
from utils import rel_time

@command("!inbox")
async def cmd_inbox(from_pubkey, args, db) -> str:
    rows = await execute_fetchall(db, """
        SELECT id, from_nick, timestamp, read
        FROM mail WHERE to_pubkey=?
        ORDER BY timestamp DESC LIMIT ?
    """, (from_pubkey, MAX_INBOX))

    if not rows:
        return "Inbox vuota"

    unread = sum(1 for r in rows if not r["read"])
    lines = [f"[{'N' if not r['read'] else 'L'}] #{r['id']} "
             f"{r['from_nick'] or '???'} ({rel_time(r['timestamp'])})"
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
    dest = await execute_fetchone(
        db, "SELECT pubkey FROM users WHERE nickname=?", (dest_nick,)
    )

    gid = make_global_id(from_pubkey, text)
    now = int(time.time())

    # Recupera nick mittente
    sender = await execute_fetchone(
        db, "SELECT nickname FROM users WHERE pubkey=?", (from_pubkey,)
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
        # Destinatario non locale — mail in attesa di federazione
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
    row = await execute_fetchone(
        db, "SELECT * FROM mail WHERE id=? AND to_pubkey=?",
        (mail_id, from_pubkey)
    )
    if not row:
        return f"Mail #{mail_id} non trovata"
    await db.execute(
        "UPDATE mail SET read=1 WHERE id=?", (mail_id,)
    )
    await db.commit()
    return f"Da: {row['from_nick'] or '???'}\n{row['text']}"
```

**Correzioni rispetto alla roadmap originale**:
- Mail inter-nodo: `to_pubkey` impostata a `"PENDING"` invece di stringa vuota `""`
- Aggiunta colonna `federation_status='pending'` per mail in attesa
- Usa funzioni helper da `database.py`
- `_rel_time` sostituita con `rel_time` da `utils.py`

## F6.3 — utils.py (modulo condiviso)

```python
# utils.py

def rel_time(ts: int) -> str:
    """Restituisce tempo relativo compatto: '5m', '2h', '3g'."""
    import time
    delta = int(time.time()) - ts
    if delta < 60:     return f"{delta}s"
    if delta < 3600:   return f"{delta//60}m"
    if delta < 86400:  return f"{delta//3600}h"
    return f"{delta//86400}g"

def sanitize_nick(nick: str, max_len: int = 20) -> str:
    """Rimuove caratteri non stampabili e tronca."""
    return "".join(c for c in nick if c.isprintable())[:max_len]
```

## Flusso Mail Inter-Nodo

```
Utente A su BBS-A: "!mail Mario ciao"
    |
    v
BBS-A cerca "Mario" nel DB locale
    |
    +-- Trovato: salva mail con to_pubkey di Mario
    |
    +-- Non trovato:
        salva mail con to_pubkey="PENDING", federation_status="pending"
        |
        v (Fase 7)
        Invia pacchetto MAIL (0x04) a tutti i peer
            |
            v
        BBS-B riceve, cerca "Mario" nel suo DB locale
            |
            +-- Trovato: salva mail, aggiorna federation_status="delivered"
            +-- Non trovato: scarta (o inoltra se TTL > 0 in v2)
```

## Criteri di Completamento

- [ ] `!boards` elenca le 3 board predefinite con conteggio post
- [ ] `!post Generale "ciao"` salva post e visibile con `!read Generale`
- [ ] `!mail Mario "ciao"` salva mail, `!inbox` la mostra, `!mail read 1` la legge
- [ ] Paginazione `!read Generale 2` funzionante
- [ ] Store-and-forward: mail visibile anche dopo riavvio BBS
- [ ] Mail a destinatario non locale salvata con `federation_status='pending'`
- [ ] `utils.py` importato correttamente da entrambi i moduli
