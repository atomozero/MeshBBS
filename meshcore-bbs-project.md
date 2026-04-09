# MeshCore BBS - Documento di Progetto

## Panoramica

Questo documento definisce le basi per la creazione di un sistema BBS (Bulletin Board System) compatibile con lo standard MeshCore, il protocollo di comunicazione mesh basato su LoRa.

### Obiettivi del Progetto

- Creare un sistema BBS che estenda le funzionalità del Room Server nativo di MeshCore
- Garantire piena compatibilità con i client MeshCore esistenti (smartphone app, T-Deck, web client)
- Offrire funzionalità avanzate: aree tematiche, archiviazione persistente, moderazione
- Mantenere il funzionamento offline e decentralizzato tipico delle reti mesh

---

## Architettura di Sistema

### Schema Generale

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RETE MESHCORE                                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │ Client   │    │ Client   │    │ Repeater │    │ Repeater │      │
│  │ T-Deck   │◄──►│ BLE+App  │◄──►│          │◄──►│          │      │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘      │
│        ▲              ▲                               ▲             │
│        │              │                               │             │
│        └──────────────┼───────────────────────────────┘             │
│                       │                                             │
│                       ▼                                             │
│              ┌─────────────────┐                                    │
│              │ Companion Radio │                                    │
│              │   (Gateway)     │                                    │
│              └────────┬────────┘                                    │
└───────────────────────┼─────────────────────────────────────────────┘
                        │ USB/BLE/TCP
                        ▼
              ┌─────────────────┐
              │  CONTROLLER     │
              │  (Raspberry Pi) │
              │                 │
              │  ┌───────────┐  │
              │  │ BBS       │  │
              │  │ Software  │  │
              │  └─────┬─────┘  │
              │        │        │
              │  ┌─────▼─────┐  │
              │  │ Database  │  │
              │  │ (SQLite)  │  │
              │  └───────────┘  │
              └─────────────────┘
```

### Componenti Principali

1. **Companion Radio (Gateway)**: Dispositivo LoRa che funge da ponte tra la rete mesh e il controller
2. **Controller**: Computer (Raspberry Pi o simile) che esegue il software BBS
3. **Software BBS**: Applicazione che gestisce la logica BBS e comunica via MeshCore
4. **Database**: Storage persistente per messaggi, utenti e configurazioni

---

## Hardware Consigliato

### Configurazione Minima

| Componente | Modello Consigliato | Note |
|------------|---------------------|------|
| Controller | Raspberry Pi 4 (2GB+) | Anche Pi 3B+ o Pi Zero 2W |
| Companion Radio | Heltec V3 | Firmware USB Serial Companion |
| Alimentazione | 5V 3A USB-C | Per Pi 4 |
| Storage | microSD 32GB+ | Classe 10 o superiore |

### Configurazione Consigliata (Maggiore Copertura)

| Componente | Modello Consigliato | Note |
|------------|---------------------|------|
| Controller | Raspberry Pi 4 (4GB) | Headless, con SSH |
| Companion Radio | RAK4631 (WisBlock) | Migliore sensibilità RF |
| Antenna | 868/915MHz esterna | Gain 3-6 dBi |
| Alimentazione | PoE HAT + alimentatore | Per installazioni remote |
| Storage | SSD USB 128GB+ | Per archivi estesi |
| UPS | PiJuice o simile | Continuità operativa |

### Dispositivi LoRa Compatibili

**Per il Gateway (Companion Radio):**

| Dispositivo | Chip | Pro | Contro |
|-------------|------|-----|--------|
| Heltec V3 | ESP32-S3 + SX1262 | Economico, facile da trovare | BLE a corto raggio |
| RAK4631 | nRF52840 + SX1262 | Ottima sensibilità, BLE stabile | Richiede base WisBlock |
| Heltec T114 | nRF52840 + SX1262 | Compatto, schermo integrato | Meno diffuso |
| Station G2 | ESP32 + SX1262 | Potente, antenna esterna | Più costoso |

**Frequenze per Regione:**

| Regione | Frequenza | Note |
|---------|-----------|------|
| EU/UK | 869.525 MHz | BW 250kHz, SF 11 |
| USA/Canada | 910.525 MHz | BW 250kHz, SF 10/11 |
| Australia/NZ | 915.8 MHz | BW 250kHz, SF 10 |

### Schema Connessioni Hardware

```
┌────────────────────────────────────────────────────────┐
│                   RASPBERRY PI 4                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ USB-A ──────────► Companion Radio (Heltec V3)    │  │
│  │ USB-A ──────────► SSD esterno (opzionale)        │  │
│  │ Ethernet ───────► Router/Switch (SSH, backup)    │  │
│  │ GPIO ───────────► Sensori (opzionale, futuro)    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  microSD: OS + Software BBS                            │
│  RAM: Database in-memory cache                         │
└────────────────────────────────────────────────────────┘
         │
         │ USB
         ▼
┌────────────────────────────────────────────────────────┐
│              HELTEC V3 (Companion Radio)               │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Firmware: USB Serial Companion                   │  │
│  │ Frequenza: 869.525 MHz (EU)                      │  │
│  │ SF: 11, BW: 250kHz, CR: 5                        │  │
│  └──────────────────────────────────────────────────┘  │
│                          │                             │
│                    Antenna SMA                         │
│                          │                             │
└──────────────────────────┼─────────────────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   ANTENNA    │
                    │  868/915MHz  │
                    │  (esterna)   │
                    └──────────────┘
```

---

## Software e Librerie

### Stack Tecnologico Proposto

**Opzione A: Python (Consigliata per prototipazione)**

```
┌─────────────────────────────────────────┐
│            Applicazione BBS             │
├─────────────────────────────────────────┤
│  meshcore_py (comunicazione MeshCore)   │
│  https://github.com/fdlamotte/meshcore_py
├─────────────────────────────────────────┤
│  SQLite / SQLAlchemy (persistenza)      │
├─────────────────────────────────────────┤
│  Python 3.9+                            │
└─────────────────────────────────────────┘
```

**Opzione B: Node.js (Per integrazione web)**

```
┌─────────────────────────────────────────┐
│            Applicazione BBS             │
├─────────────────────────────────────────┤
│  meshcore.js (comunicazione MeshCore)   │
│  https://github.com/liamcottle/meshcore.js
├─────────────────────────────────────────┤
│  better-sqlite3 (persistenza)           │
├─────────────────────────────────────────┤
│  Node.js 18+                            │
└─────────────────────────────────────────┘
```

### Dipendenze Software

**Sistema Operativo:**
- Raspberry Pi OS Lite (64-bit) - consigliato
- Debian/Ubuntu Server

**Python (se Opzione A):**
```bash
pip install meshcore-py pyserial sqlalchemy
```

**Node.js (se Opzione B):**
```bash
npm install meshcore serialport better-sqlite3
```

---

## Protocollo MeshCore - Elementi Chiave

### Tipi di Pacchetto Rilevanti

| Tipo | Codice | Descrizione |
|------|--------|-------------|
| PAYLOAD_TYPE_TXT_MSG | 0x02 | Messaggio di testo diretto |
| PAYLOAD_TYPE_ACK | 0x03 | Conferma ricezione |
| PAYLOAD_TYPE_ADVERT | 0x04 | Annuncio identità nodo |
| PAYLOAD_TYPE_GRP_TXT | 0x05 | Messaggio canale/gruppo |
| PAYLOAD_TYPE_REQ | 0x00 | Richiesta generica |
| PAYLOAD_TYPE_RESPONSE | 0x01 | Risposta a richiesta |

### Routing e Delivery

- **Primo messaggio**: Flood routing (broadcast attraverso repeater)
- **Messaggi successivi**: Path routing (percorso diretto memorizzato)
- **Canali/Gruppi**: Sempre flood routing
- **Limite hop**: 64 (teorico), pratico dipende dall'ambiente

### Crittografia

- Ogni nodo ha una coppia di chiavi pubblica/privata
- I messaggi diretti sono crittografati end-to-end
- I canali usano una chiave condivisa (secret)

**Formato QR Canale:**
```
meshcore://channel/add?name=<nome>&secret=<chiave_hex>
```

**Formato QR Contatto:**
```
meshcore://contact/add?name=<nome>&public_key=<chiave>&type=<tipo>
```

Dove `type`: 1=chat, 2=repeater, 3=room, 4=sensor

---

## Struttura Database BBS

### Schema Proposto

```sql
-- Utenti registrati sulla BBS
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    public_key TEXT UNIQUE NOT NULL,
    nickname TEXT,
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME,
    is_admin BOOLEAN DEFAULT FALSE,
    is_banned BOOLEAN DEFAULT FALSE
);

-- Aree tematiche (come forum/newsgroup)
CREATE TABLE areas (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Messaggi
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    area_id INTEGER,
    sender_key TEXT NOT NULL,
    subject TEXT,
    body TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    parent_id INTEGER,  -- Per thread/risposte
    FOREIGN KEY (area_id) REFERENCES areas(id),
    FOREIGN KEY (sender_key) REFERENCES users(public_key),
    FOREIGN KEY (parent_id) REFERENCES messages(id)
);

-- Messaggi privati
CREATE TABLE private_messages (
    id INTEGER PRIMARY KEY,
    sender_key TEXT NOT NULL,
    recipient_key TEXT NOT NULL,
    body TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    read BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (sender_key) REFERENCES users(public_key),
    FOREIGN KEY (recipient_key) REFERENCES users(public_key)
);

-- Log attività
CREATE TABLE activity_log (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT,
    user_key TEXT,
    details TEXT
);
```

---

## Comandi BBS Proposti

### Sintassi Messaggi

Gli utenti interagiscono con la BBS inviando messaggi di testo con comandi. Il formato proposto:

```
/comando [argomenti]
```

### Lista Comandi

| Comando | Descrizione | Esempio |
|---------|-------------|---------|
| `/help` | Mostra aiuto | `/help` |
| `/areas` | Lista aree disponibili | `/areas` |
| `/join <area>` | Entra in un'area | `/join generale` |
| `/leave` | Esci dall'area corrente | `/leave` |
| `/list [n]` | Lista ultimi n messaggi | `/list 10` |
| `/read <id>` | Leggi messaggio specifico | `/read 42` |
| `/post <testo>` | Pubblica nell'area corrente | `/post Ciao a tutti!` |
| `/reply <id> <testo>` | Rispondi a un messaggio | `/reply 42 Grazie!` |
| `/msg <utente> <testo>` | Messaggio privato | `/msg ABC123 Ciao` |
| `/inbox` | Mostra messaggi privati | `/inbox` |
| `/who` | Utenti attivi recentemente | `/who` |
| `/info` | Info sulla BBS | `/info` |
| `/nick <nome>` | Imposta nickname | `/nick Mario` |

### Risposte della BBS

Le risposte seguono un formato compatto per ottimizzare l'uso della banda LoRa:

```
[BBS] <risposta>
```

Esempio:
```
[BBS] Aree: generale, tech, emergenze, trading
[BBS] #42 da Mario (2h fa): Qualcuno ha notizie?
[BBS] Msg inviato. ID: 43
```

---

## Implementazione - Fase 1 (MVP)

### Obiettivi MVP

1. Connessione al companion radio via USB serial
2. Ricezione e invio messaggi MeshCore
3. Comandi base: `/help`, `/post`, `/list`, `/read`
4. Storage messaggi in SQLite
5. Singola area "generale"

### Struttura Codice (Python)

```
meshcore-bbs/
├── main.py              # Entry point
├── config.py            # Configurazione
├── bbs/
│   ├── __init__.py
│   ├── core.py          # Logica principale BBS
│   ├── commands.py      # Parser e handler comandi
│   ├── database.py      # Gestione SQLite
│   └── messages.py      # Formattazione messaggi
├── meshcore/
│   ├── __init__.py
│   ├── connection.py    # Connessione seriale/BLE
│   └── protocol.py      # Encoding/decoding pacchetti
├── data/
│   └── bbs.db           # Database SQLite
├── logs/
│   └── bbs.log          # Log operazioni
├── requirements.txt
└── README.md
```

### Pseudocodice Main Loop

```python
# main.py - Struttura base

import asyncio
from meshcore.connection import MeshCoreConnection
from bbs.core import BBSCore
from bbs.database import Database

async def main():
    # Inizializzazione
    db = Database("data/bbs.db")
    mesh = MeshCoreConnection("/dev/ttyUSB0")
    bbs = BBSCore(db, mesh)
    
    await mesh.connect()
    print("[BBS] Connesso al companion radio")
    
    # Invia advert periodico
    asyncio.create_task(bbs.periodic_advert())
    
    # Loop principale
    while True:
        # Attendi messaggi in arrivo
        message = await mesh.receive()
        
        if message:
            # Processa il messaggio
            response = await bbs.handle_message(message)
            
            if response:
                # Invia risposta
                await mesh.send(
                    destination=message.sender,
                    text=response
                )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Considerazioni sulla Compatibilità

### Interoperabilità con Room Server Nativo

La BBS può coesistere con Room Server nativi sulla stessa rete. Differenze chiave:

| Aspetto | Room Server Nativo | BBS Proposta |
|---------|-------------------|--------------|
| Storage | 32 messaggi | Illimitato (SQLite) |
| Aree | Singola | Multiple |
| Comandi | Login/Logout | Comandi testuali estesi |
| Hardware | Solo LoRa device | LoRa + Controller |
| Moderazione | Nessuna | Sì (admin) |

### Compatibilità Client

La BBS risponde come un normale nodo MeshCore. I client esistenti possono:
- Vedere la BBS nella lista contatti (dopo advert)
- Inviare messaggi diretti alla BBS
- Ricevere risposte come messaggi di testo

Non è richiesta alcuna modifica ai client.

---

## Roadmap di Sviluppo

### Fase 1: MVP (4-6 settimane)
- [ ] Setup ambiente di sviluppo
- [ ] Connessione base al companion radio
- [ ] Ricezione/invio messaggi
- [ ] Database SQLite
- [ ] Comandi base (`/help`, `/post`, `/list`)

### Fase 2: Funzionalità Core (4-6 settimane)
- [ ] Aree tematiche multiple
- [ ] Thread e risposte
- [ ] Messaggi privati
- [ ] Gestione utenti (nickname, registrazione)

### Fase 3: Amministrazione (3-4 settimane)
- [ ] Ruoli admin/moderatore
- [ ] Ban utenti
- [ ] Moderazione messaggi
- [ ] Statistiche e log

### Fase 4: Funzionalità Avanzate (ongoing)
- [ ] Integrazione MQTT
- [ ] Web interface di amministrazione
- [ ] Backup automatico
- [ ] Bridge tra BBS (federazione)
- [ ] Supporto file/allegati (QR code)

---

## Risorse e Riferimenti

### Repository Ufficiali
- MeshCore Firmware: https://github.com/meshcore-dev/MeshCore
- meshcore.js: https://github.com/liamcottle/meshcore.js
- meshcore_py: https://github.com/fdlamotte/meshcore_py
- MeshCore Web Client: https://github.com/liamcottle/meshcore-web

### Tool Utili
- Flasher: https://flasher.meshcore.co.uk/
- Configuratore: https://config.meshcore.dev
- Mappa: https://map.meshcore.co.uk/

### Documentazione
- CLI Repeater/Room Server: https://github.com/meshcore-dev/MeshCore/wiki/Repeater-&-Room-Server-CLI-Reference
- Guida T-Deck: https://buymeacoffee.com/ripplebiz/ultra-v7-7-guide-meshcore-users

### Community
- Discord MeshCore: https://discord.gg/meshcore
- Video tutorial Andy Kirby: https://www.youtube.com/@AndyKirby

---

## Note Finali

Questo documento è un punto di partenza. Il progetto è open source e aperto a contributi.

**Licenza proposta**: MIT (compatibile con MeshCore)

**Autore**: [Da definire]  
**Versione documento**: 0.1  
**Data**: Gennaio 2026
