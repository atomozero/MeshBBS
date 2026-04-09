# 02 — Stack e Dipendenze

> Riferimento: Roadmap sezione 2

---

## Hardware

| Componente | Modello | Note |
|------------|---------|------|
| Radio companion | Heltec WiFi LoRa 32 V3 | ESP32-S3 + SX1262, OLED 128x64 |
| Host BBS | Raspberry Pi W (Zero W o 3/4) | Alimentazione stabile 5V |
| Antenna | Dipolo 868 MHz | Esterna se possibile per miglior copertura |

### Note Hardware

- L'Heltec V3 funge da **bridge radio-TCP**: riceve/trasmette LoRa e espone una socket TCP
- Il Raspberry Pi non ha radio LoRa — comunica solo via WiFi con l'Heltec
- Alimentazione: entrambi i dispositivi richiedono alimentazione continua (no batteria per uso BBS)
- L'OLED dell'Heltec mostra nome nodo e stato radio — utile per debug

## Software — Dipendenze Python

```bash
# Sul Raspberry Pi
pip install meshcore          # libreria ufficiale MeshCore companion
pip install aiosqlite         # SQLite asincrono per asyncio
pip install structlog          # logging strutturato
```

> **`asyncio` NON va installato via pip** — e' parte della stdlib Python 3.4+.

### Versioni consigliate

| Pacchetto | Versione minima | Note |
|-----------|----------------|------|
| Python | 3.10+ | Per `match/case` e type hints moderni |
| meshcore | ultima disponibile | Libreria in sviluppo attivo |
| aiosqlite | 0.17+ | Supporto context manager asincrono |
| structlog | 23.0+ | Logging strutturato |

## Riferimento Libreria meshcore

- **PyPI**: https://pypi.org/project/meshcore/
- **GitHub**: https://github.com/meshcore-dev/meshcore_py
- **Connessioni supportate**: `create_serial()`, `create_ble()`, **`create_tcp()`** (nostra scelta)

## API Principale meshcore (verificata da documentazione PyPI)

```python
import asyncio
from meshcore import MeshCore, EventType

# Connessione TCP
mc = await MeshCore.create_tcp("192.168.1.50", 5000)

# Comandi disponibili
await mc.commands.get_contacts()           # lista contatti
await mc.commands.send_msg(contact, "testo")  # invia messaggio diretto
await mc.commands.get_bat()                # livello batteria
await mc.commands.send_advert(flood=True)  # broadcast advert

# Subscribe agli eventi
mc.subscribe(EventType.MSG_RECEIVED, handler)
mc.subscribe(EventType.ACK, handler)
mc.subscribe(EventType.BATTERY, handler)

# Ogni handler riceve un Event con .type e .payload
async def handler(event):
    print(event.type, event.payload)
```

> **IMPORTANTE**: verificare i nomi esatti dei metodi alla prima connessione reale — la libreria e' in sviluppo attivo. In particolare:
> - La struttura di `event.payload` per `MSG_RECEIVED` (campi `from`, `text`, ecc.)
> - Il tipo restituito da `get_contacts()` (dict? list? oggetti?)
> - Come risolvere un contatto dalla pubkey per `send_msg()`

## Dipendenze di Sistema (RPi)

```bash
# Sistema operativo
sudo apt update && sudo apt install -y python3 python3-pip python3-venv

# Virtual environment (consigliato)
python3 -m venv ~/meshbbs-venv
source ~/meshbbs-venv/bin/activate
pip install meshcore aiosqlite structlog
```

## Matrice Compatibilita'

| RPi Model | Python 3.10+ | WiFi integrato | Note |
|-----------|-------------|----------------|------|
| Zero W | Dipende da OS | Si | Risorse limitate, OK per BBS |
| Zero 2 W | Si (Bookworm) | Si | Consigliato come minimo |
| 3B+ | Si | Si | Buone risorse |
| 4B | Si | Si | Sovradimensionato ma OK |
