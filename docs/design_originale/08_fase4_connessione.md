# 08 — Fase 4: Layer di Connessione e Resilienza

> Riferimento: Roadmap Fase 4

---

## Obiettivo

Nucleo del software BBS — connessione con auto-reconnect, coda messaggi con priorita', logging strutturato, servizio systemd.

## Dipendenze

- Fase 1 completata (hardware operativo)
- Fase 2 completata (API meshcore verificata)
- Fase 3 completata (database pronto)

## F4.1 — connection.py — Auto-Reconnect

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

    @property
    def is_connected(self) -> bool:
        return self._connected

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
                delay = min(delay * 2, 60)  # backoff: 5->10->20->40->60s max

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
            if self._mc is None or not self._connected:
                log.warning("Companion disconnesso — tentativo riconnessione")
                self._connected = False
                await self.connect()
```

**Miglioramenti rispetto alla roadmap originale**:
- Aggiunta property `is_connected` per uso esterno
- Watch loop controlla anche `self._connected` oltre a `self._mc`

## F4.2 — queue.py — Coda Messaggi con Priorita'

```python
# queue.py
import asyncio

# Priorita': minore = piu' urgente
PRIO_USER        = 1   # risposte dirette all'utente
PRIO_NOTIFY      = 2   # notifiche (mail in attesa, ecc.)
PRIO_FEDERATION  = 3   # messaggi verso peer federati

class OutboxQueue:
    def __init__(self):
        self._queue = asyncio.PriorityQueue()
        self._seq   = 0  # sequenza per FIFO dentro stessa priorita'

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

    @property
    def size(self):
        return self._queue.qsize()
```

## F4.3 — main.py — Entry Point

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
                log.warning(f"Contatto {contact_pubkey[:8]} non trovato")
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
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(conn)))

    await asyncio.gather(
        conn.watch(),
        sender_loop(conn),
    )

async def shutdown(conn):
    """Graceful shutdown."""
    log.info("Shutdown in corso...")
    # Qui si possono aggiungere cleanup tasks
    raise SystemExit(0)

if __name__ == "__main__":
    asyncio.run(main())
```

**Miglioramenti rispetto alla roadmap originale**:
- Aggiunto graceful shutdown con signal handler (SIGTERM/SIGINT)
- Aggiunta funzione `shutdown()` per cleanup

## F4.4 — Servizio systemd

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

### Comandi di gestione

```bash
sudo systemctl daemon-reload
sudo systemctl enable meshbbs
sudo systemctl start meshbbs
sudo systemctl status meshbbs
sudo journalctl -u meshbbs -f   # log in tempo reale
```

## Note sulla Risoluzione Contatti

Il `sender_loop` usa `get_contacts()` per trovare il contatto dalla pubkey. Questo approccio ha limiti:

1. **Performance**: chiama `get_contacts()` per ogni messaggio in uscita
2. **Matching parziale**: usa solo i primi 8 caratteri della pubkey — rischio collisioni
3. **Contatto non in lista**: se il mittente non e' nei contatti del companion, non si puo' rispondere

**Da verificare con la libreria reale** (Area critica dalla roadmap):
- Esiste un metodo per risolvere un contatto direttamente dalla pubkey?
- Si puo' cachare la lista contatti e aggiornarla periodicamente?
- Come gestire il caso in cui il contatto non e' nella lista?

## Criteri di Completamento

- [ ] Disconnessione simulata (spegni Heltec): sistema riconnette con backoff
- [ ] Riavvio RPi: il servizio riparte e si riconnette entro 60s
- [ ] Messaggio in ingresso appare nel log
- [ ] `OutboxQueue` gestisce priorita' (risposta utente prima di federazione)
- [ ] Graceful shutdown su SIGTERM non lascia processi orfani
- [ ] `systemctl status meshbbs` mostra Active (running)
