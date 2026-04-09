# Task 01: Setup Ambiente di Sviluppo

## Stato: ✅ PARZIALMENTE COMPLETATO

> **Nota**: I task software sono stati completati. I task hardware (companion radio, porte seriali) sono in attesa dell'hardware.

## Analisi

### Contesto
Il progetto MeshCore BBS richiede un ambiente di sviluppo che integri:
- **Hardware**: Raspberry Pi (controller) + dispositivo LoRa (companion radio)
- **Software**: Python 3.9+ con libreria meshcore_py per comunicazione seriale
- **Database**: SQLite per persistenza dati
- **Sistema operativo**: Raspberry Pi OS Lite (64-bit) o equivalente Debian/Ubuntu

### Requisiti Tecnici dal Progetto
Dal documento di progetto emergono i seguenti requisiti:

**Stack tecnologico scelto (Python):**
- Python 3.9+
- meshcore_py (https://github.com/fdlamotte/meshcore_py)
- SQLAlchemy per ORM
- pyserial per comunicazione seriale

**Hardware di riferimento:**
- Raspberry Pi 4 (2GB+ RAM)
- Heltec V3 o RAK4631 come companion radio
- Connessione USB tra Pi e radio

### Dipendenze Chiave
- `meshcore-py`: Libreria Python per comunicazione con companion radio
- `pyserial`: Gestione porta seriale
- `sqlalchemy`: ORM per database SQLite
- Accesso alla porta `/dev/ttyUSB0` (ESP32) o `/dev/ttyACM0` (nRF)

### Sfide Identificate
1. Permessi di accesso alle porte seriali su Linux
2. Configurazione corretta del companion radio (frequenza, SF, BW)
3. Gestione virtualenv per isolamento dipendenze
4. Struttura del progetto modulare per future espansioni

---

## Task Dettagliati

### Task 1.1: Preparazione Sistema Operativo
**Stato**: ⏳ In attesa hardware

**Descrizione**: Installare e configurare Raspberry Pi OS Lite sul controller

**Sotto-attività**:
- [ ] Scaricare Raspberry Pi OS Lite (64-bit) da raspberrypi.com
- [ ] Flashare l'immagine su microSD (32GB+) con Raspberry Pi Imager
- [ ] Abilitare SSH durante la configurazione iniziale
- [ ] Configurare hostname (es. `meshbbs`)
- [ ] Configurare connessione WiFi/Ethernet
- [ ] Primo boot e aggiornamento sistema: `sudo apt update && sudo apt upgrade -y`

**Verifica**: SSH al Raspberry Pi funzionante

---

### Task 1.2: Installazione Python e Dipendenze Sistema
**Stato**: ⏳ In attesa hardware (per Raspberry Pi) / ✅ Completato per sviluppo locale

**Descrizione**: Preparare l'ambiente Python con tutte le dipendenze di sistema

**Sotto-attività**:
- [x] Verificare versione Python: `python3 --version` (deve essere 3.9+)
- [x] Installare pip
- [x] Installare python3-venv
- [ ] Installare libpython3-dev (richiesto su Pi)
- [x] Installare git
- [ ] Installare picocom per debug seriale

**Verifica**: `python3 -m venv --help` restituisce l'help senza errori

---

### Task 1.3: Creazione Struttura Progetto
**Stato**: ✅ COMPLETATO

**Descrizione**: Creare la struttura di directory del progetto BBS

**Struttura creata**:
```
MeshBBS/
├── src/
│   ├── main.py
│   ├── bbs/
│   │   ├── __init__.py
│   │   ├── core.py
│   │   ├── commands/
│   │   ├── models/
│   │   └── repositories/
│   ├── meshcore/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── messages.py
│   │   └── protocol.py
│   └── utils/
│       ├── __init__.py
│       ├── config.py
│       └── logger.py
├── tests/
├── tasks/
├── data/
├── logs/
├── venv/
├── README.md
├── LICENSE
├── CHANGELOG.md
├── requirements.txt
└── pytest.ini
```

**Verifica**: ✅ Struttura conforme

---

### Task 1.4: Configurazione Virtual Environment
**Stato**: ✅ COMPLETATO

**Descrizione**: Creare e attivare l'ambiente virtuale Python isolato

**Sotto-attività**:
- [x] Creare virtualenv: `python3 -m venv venv`
- [x] Attivare virtualenv: `source venv/bin/activate`
- [x] Aggiornare pip: `pip install --upgrade pip`
- [x] Verificare che l'ambiente sia isolato

**Verifica**: ✅ Virtual environment funzionante

---

### Task 1.5: Installazione Dipendenze Python
**Stato**: ✅ COMPLETATO

**Descrizione**: Installare tutte le librerie Python necessarie

**File `requirements.txt` creato**:
```
SQLAlchemy>=2.0.0
pyserial-asyncio>=0.6
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-cov>=4.0.0
black>=23.0.0
isort>=5.12.0
mypy>=1.0.0
```

**Verifica**: ✅ Tutti gli import funzionano

---

### Task 1.6: Configurazione Permessi Porta Seriale
**Stato**: ⏳ In attesa hardware

**Descrizione**: Configurare i permessi per accesso alla porta seriale USB

**Sotto-attività**:
- [ ] Identificare gruppo dialout
- [ ] Aggiungere utente al gruppo dialout
- [ ] Creare regola udev per persistenza
- [ ] Ricaricare regole udev
- [ ] Effettuare logout/login

**Verifica**: In attesa

---

### Task 1.7: Preparazione Companion Radio
**Stato**: ⏳ In attesa hardware

**Descrizione**: Flashare e configurare il companion radio con firmware USB Serial

**Sotto-attività**:
- [ ] Connettere dispositivo LoRa via USB
- [ ] Verificare riconoscimento
- [ ] Flashare firmware USB Serial Companion
- [ ] Configurare frequenza per la propria regione
- [ ] Verificare comunicazione base con picocom

**Verifica**: In attesa

---

### Task 1.8: Creazione File di Configurazione
**Stato**: ✅ COMPLETATO

**Descrizione**: Creare i file di configurazione per il progetto

**File creati**:
- `src/utils/config.py` - Configurazione con dataclass
- Supporto per variabili d'ambiente

**Verifica**: ✅ Import di config funziona

---

### Task 1.9: Setup Logging
**Stato**: ✅ COMPLETATO

**Descrizione**: Configurare sistema di logging per debug e monitoraggio

**File creato**: `src/utils/logger.py`

**Funzionalità**:
- Rotazione file con RotatingFileHandler
- Output su console e file
- Livelli configurabili (DEBUG/INFO)
- Formato con timestamp, livello, modulo

**Verifica**: ✅ Logging funzionante

---

### Task 1.10: Verifica Finale e Documentazione
**Stato**: ✅ COMPLETATO

**Descrizione**: Verificare l'intero setup e documentare il processo

**Sotto-attività**:
- [x] Creato test suite completa (66 test)
- [x] Tutti i test passano
- [x] Documentato nel README.md
- [x] Creato CHANGELOG.md
- [ ] Creare primo commit git

**Verifica**: ✅ Test suite completa con 66 test passati

---

## Checklist Finale

- [ ] Sistema operativo installato e aggiornato (attesa hardware)
- [x] Python 3.9+ installato con venv
- [x] Struttura progetto creata
- [x] Virtual environment configurato
- [x] Dipendenze Python installate
- [ ] Permessi porta seriale configurati (attesa hardware)
- [ ] Companion radio flashato e configurato (attesa hardware)
- [x] File di configurazione creati
- [x] Sistema di logging funzionante
- [x] Documentazione aggiornata

---

## Risorse Utili

- Repository meshcore_py: https://github.com/fdlamotte/meshcore_py
- Flasher MeshCore: https://flasher.meshcore.co.uk/
- Configuratore MeshCore: https://config.meshcore.dev
- Documentazione SQLAlchemy: https://docs.sqlalchemy.org/
- Raspberry Pi OS: https://www.raspberrypi.com/software/

---

## Note Tecniche

### Frequenze per Regione
| Regione | Frequenza | SF | BW |
|---------|-----------|----|----|
| EU/UK | 869.525 MHz | 11 | 250kHz |
| USA/Canada | 910.525 MHz | 10/11 | 250kHz |
| Australia/NZ | 915.8 MHz | 10 | 250kHz |

### Dispositivi Porte Seriali
| Dispositivo | Chip | Porta Tipica |
|-------------|------|--------------|
| Heltec V3 | ESP32-S3 | /dev/ttyUSB0 |
| RAK4631 | nRF52840 | /dev/ttyACM0 |
| Heltec T114 | nRF52840 | /dev/ttyACM0 |
