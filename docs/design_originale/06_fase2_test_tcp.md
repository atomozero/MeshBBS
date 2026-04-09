# 06 — Fase 2: Test Connessione TCP

> Riferimento: Roadmap Fase 2
> **Puo' procedere in parallelo con Fase 3** — il database non dipende dalla connessione TCP.

---

## Obiettivo

Verificare ricezione e invio eventi dalla libreria Python meshcore. Questa fase produce **script standalone di test**, non la struttura definitiva del progetto (quella e' Fase 4).

## Prerequisiti

- Fase 1 completata (Heltec V3 raggiungibile su porta 5000)
- Python 3.10+ sul RPi
- Dipendenze installate: `pip install meshcore`

## F2.1 — Installazione Dipendenze

```bash
pip install meshcore aiosqlite structlog
```

## F2.2 — Script Test Connessione

```python
# scripts/test_connection.py
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
        print(f"[MSG] type={event.type}")
        print(f"      payload={event.payload}")
        # Documentare qui la struttura esatta di event.payload
        # per usarla nelle fasi successive

    mc.subscribe(EventType.MSG_RECEIVED, on_message)

    # Resta in ascolto 60 secondi
    print("In ascolto per 60 secondi — manda un messaggio al nodo...")
    await asyncio.sleep(60)
    await mc.disconnect()

asyncio.run(main())
```

**IMPORTANTE**: durante questo test, documentare:
1. La struttura esatta di `event.payload` (campi disponibili, tipi)
2. Come si identifica il mittente (campo `from`? `pubkey`? oggetto?)
3. Il tipo restituito da `get_contacts()` (dict, list, oggetti custom?)

## F2.3 — Script Test Invio

```python
# scripts/test_send.py — da eseguire DOPO aver verificato la ricezione
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

## F2.4 — Verifica Struttura Payload (da compilare durante il test)

Dopo aver eseguito i test, compilare questa tabella:

| Campo | Tipo | Esempio | Note |
|-------|------|---------|------|
| `event.payload["from"]` | ? | ? | Pubkey mittente? |
| `event.payload["text"]` | ? | ? | Testo del messaggio? |
| `contacts.payload` | ? | ? | Dict o List? |
| `contact.pubkey` | ? | ? | Come accedere alla pubkey? |

Questa informazione e' **critica** per le fasi successive (dispatcher, federation).

## Troubleshooting

| Problema | Causa | Soluzione |
|----------|-------|-----------|
| `ConnectionRefused` su porta 5000 | Firmware non WiFi o Heltec spento | Verificare Fase 1 |
| `create_tcp()` timeout | Firewall o IP errato | `ping` + `nc -zv` |
| `get_contacts()` lista vuota | Nessun nodo ha fatto advert | Invia advert da app MeshCore |
| `MSG_RECEIVED` non triggera | Messaggio non diretto al companion | Inviare specificamente al nodo BBS |
| `send_msg()` errore | Contatto non raggiungibile | Verificare mesh, inviare advert |

## Criteri di Completamento

- [ ] `create_tcp()` si connette senza eccezioni
- [ ] `get_contacts()` restituisce lista (anche vuota e' OK)
- [ ] `MSG_RECEIVED` viene triggerato quando arriva un messaggio
- [ ] `send_msg()` non restituisce errore
- [ ] Struttura di `event.payload` documentata nella tabella sopra
