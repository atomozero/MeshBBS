# 14 — Aree da Analizzare e Sicurezza

> Riferimento: Roadmap sezione "Aree da Analizzare"
> Questo documento espande e dettaglia le aree identificate nella roadmap.

---

## Priorita' CRITICA

### 1. Sicurezza Applicativa (Spam/Flood)

**Problema**: senza rate limiting, un utente malevolo potrebbe:
- Inviare centinaia di comandi al secondo
- Riempire le board di spam
- Saturare la mailbox di altri utenti
- Consumare tutto lo storage con post

**Soluzione proposta**:

```python
# In dispatcher.py o come modulo separato security.py

import time
from collections import defaultdict
from config import RATE_LIMIT_USER, BLACKLIST_PUBKEYS

_user_commands = defaultdict(list)  # pubkey -> [timestamps]

def check_rate_limit(pubkey: str) -> bool:
    """Restituisce True se l'utente ha superato il rate limit."""
    if pubkey in BLACKLIST_PUBKEYS:
        return True  # sempre bloccato
    
    now = time.time()
    window = 60  # finestra di 1 minuto
    
    # Rimuovi timestamp vecchi
    _user_commands[pubkey] = [
        ts for ts in _user_commands[pubkey] if now - ts < window
    ]
    
    if len(_user_commands[pubkey]) >= RATE_LIMIT_USER:
        return True  # limite raggiunto
    
    _user_commands[pubkey].append(now)
    return False
```

**Integrazione nel dispatcher**:
```python
async def dispatch(from_pubkey, text, db):
    if check_rate_limit(from_pubkey):
        return None  # silenziosamente ignora (non rispondere al flood)
    # ... resto del dispatch
```

### 2. Parser Comandi Robusto

**Problema**: input malformati potrebbero causare crash o comportamenti inattesi.

**Casi da gestire**:
- Input con encoding non-UTF8
- Stringhe lunghissime (> MTU, possibili da connessioni malformate)
- Caratteri null o di controllo
- Tentativi di SQL injection (mitigati dai parametri, ma verificare)
- Comandi con spazi multipli o tab

**Soluzione**: sanitizzare l'input prima del dispatch:

```python
def sanitize_input(text: str, max_len: int = 500) -> str:
    """Sanitizza input utente."""
    # Tronca
    text = text[:max_len]
    # Rimuovi caratteri non stampabili (eccetto newline)
    text = "".join(c for c in text if c.isprintable() or c == "\n")
    # Normalizza spazi
    text = " ".join(text.split())
    return text.strip()
```

### 3. Risoluzione Contatto per Pubkey

**Problema**: il `sender_loop` chiama `get_contacts()` per ogni messaggio, poi cerca il contatto per prefisso pubkey (8 char). Questo e':
- Lento (query alla radio per ogni risposta)
- Fragile (matching parziale potrebbe collidere)

**Soluzioni da investigare**:
1. Cache locale dei contatti, aggiornata periodicamente
2. Metodo diretto nella libreria meshcore per inviare per pubkey
3. Tabella locale `contact_cache` nel DB

**Azione richiesta**: alla prima connessione reale (Fase 2), documentare come la libreria gestisce i contatti.

---

## Priorita' ALTA

### 4. Interfaccia Sysop Locale

**Problema**: il sysop non ha modo di gestire il BBS senza modificare il database a mano.

**Comandi sysop proposti** (CLI locale sul RPi, non via LoRa):

```bash
# Gestione utenti
meshbbs-cli ban <pubkey>        # blocca utente
meshbbs-cli unban <pubkey>      # sblocca
meshbbs-cli users               # lista utenti

# Gestione contenuti
meshbbs-cli delpost <id>        # elimina post
meshbbs-cli delmail <id>        # elimina mail

# Federazione
meshbbs-cli addpeer <pubkey> <nome>   # aggiungi peer
meshbbs-cli rmpeer <pubkey>           # rimuovi peer
meshbbs-cli peers                     # lista peer

# Sistema
meshbbs-cli status               # stato sistema
meshbbs-cli backup               # backup database
```

**Implementazione**: script Python separato che si connette allo stesso DB SQLite.

### 5. Versioning Pacchetti Federazione

**Problema**: se due nodi hanno versioni diverse del protocollo di federazione, i pacchetti potrebbero essere incompatibili.

**Soluzione**: aggiungere un byte di versione nell'header:

```
Byte 0: 0xBB (marker)
Byte 1: versione protocollo (0x01 per v1)
Byte 2: tipo messaggio
Byte 3: ttl
...
```

Questo aggiunge 1 byte all'header (20 byte totale) ma garantisce compatibilita' futura.

### 6. Backup e Recovery

**Cosa backuppare**:
- `bbs.db` — tutto lo stato del BBS
- `config.py` — configurazione
- Chiave privata del companion (se accessibile)

**Script backup**:
```bash
#!/bin/bash
# backup_bbs.sh
BACKUP_DIR="/home/pi/meshbbs/backups"
DATE=$(date +%Y%m%d_%H%M)
mkdir -p "$BACKUP_DIR"
sqlite3 /home/pi/meshbbs/bbs.db ".backup '$BACKUP_DIR/bbs_$DATE.db'"
cp /home/pi/meshbbs/config.py "$BACKUP_DIR/config_$DATE.py"
# Retention: mantieni ultimi 7 backup
ls -t "$BACKUP_DIR"/bbs_*.db | tail -n +8 | xargs -r rm
echo "Backup completato: $BACKUP_DIR/bbs_$DATE.db"
```

### 7. Helper execute_fetchone / execute_fetchall

**Problema**: il codice della roadmap li usa come metodi di `aiosqlite.Connection`, ma non esistono.

**Stato**: risolto nel documento `07_fase3_database.md` — implementati come funzioni standalone in `database.py`.

---

## Priorita' MEDIA

### 8. Testing e Simulazione Offline

**Problema**: testare il BBS richiede hardware LoRa. Serve un mock del companion.

**Approccio**:

```python
# tests/mock_companion.py
class MockCompanionConnection:
    """Simula CompanionConnection per test senza hardware."""
    
    def __init__(self):
        self.sent_messages = []
        self._contacts = {}
    
    async def connect(self):
        pass
    
    async def send(self, contact, text):
        self.sent_messages.append((contact, text))
    
    async def get_contacts(self):
        class Result:
            payload = self._contacts
        return Result()
    
    def add_mock_contact(self, pubkey, name):
        self._contacts[pubkey] = {"pubkey": pubkey, "name": name}
```

**Test da implementare**:
- Dispatcher: ogni comando produce la risposta attesa
- Database: CRUD su tutte le tabelle
- Federazione: encoding/decoding pacchetti
- Anti-loop: deduplicazione corretta
- Rate limiting: blocco dopo N comandi

### 9. Script Deploy Automatico

```bash
#!/bin/bash
# deploy.sh — da eseguire sul RPi
set -e

echo "=== Deploy MeshCore BBS ==="

# Dipendenze sistema
sudo apt update && sudo apt install -y python3 python3-pip python3-venv

# Crea utente e directory
sudo useradd -r -m -d /home/pi/meshbbs meshbbs 2>/dev/null || true
sudo mkdir -p /home/pi/meshbbs
sudo chown meshbbs:meshbbs /home/pi/meshbbs

# Virtual environment
python3 -m venv /home/pi/meshbbs/venv
source /home/pi/meshbbs/venv/bin/activate
pip install meshcore aiosqlite structlog

# Copia codice
cp -r meshbbs/* /home/pi/meshbbs/

# Inizializza DB
python3 /home/pi/meshbbs/scripts/init_db.py

# Installa servizio
sudo cp meshbbs.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable meshbbs
sudo systemctl start meshbbs

echo "=== Deploy completato ==="
sudo systemctl status meshbbs
```

---

## Priorita' BASSA

### 10. Discovery Utenti Inter-Nodo

Comando `!whois <nick>` che interroga i peer federati. Richiede:
- Nuovo tipo pacchetto federazione (`TYPE_WHOIS_REQ/RESP`)
- Timeout per risposte dai peer
- Aggregazione risultati

### 11. Quote e Limiti per Utente

- Max post al giorno per utente (es. 20)
- Retention automatica post (es. max 500 post per board, cancella i piu' vecchi)
- Quota mailbox (gia' presente: `MAX_INBOX = 20`)

### 12. Documentazione !help Compatta

La risposta di `!help` deve stare in < 180 chars. Formato attuale verificato: ~110 chars. OK.
Se si aggiungono comandi in futuro, considerare:
- `!help` mostra solo categorie
- `!help <categoria>` mostra dettagli (es. `!help mail`)

---

## Riepilogo Priorita'

| # | Area | Priorita' | Fase Impattata | Stato |
|---|------|----------|----------------|-------|
| 1 | Rate limiting / anti-spam | CRITICA | F5 | Da implementare |
| 2 | Input sanitization | CRITICA | F5 | Da implementare |
| 3 | Risoluzione contatto | CRITICA | F4 | Da verificare con hardware |
| 4 | CLI sysop | ALTA | Post-F7 | Da pianificare |
| 5 | Versioning federazione | ALTA | F7 | Da implementare |
| 6 | Backup/recovery | ALTA | Post-F3 | Script proposto |
| 7 | Helper DB | ALTA | F3 | Risolto |
| 8 | Testing offline | MEDIA | Tutte | Mock proposto |
| 9 | Deploy automatico | MEDIA | Post-F7 | Script proposto |
| 10 | !whois inter-nodo | BASSA | v2 | Da pianificare |
| 11 | Quote utente | BASSA | v2 | Da pianificare |
| 12 | !help esteso | BASSA | v2 | Da pianificare |
