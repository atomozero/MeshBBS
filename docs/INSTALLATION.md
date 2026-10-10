# MeshBBS Installation Guide

Guida all'installazione di MeshBBS su Raspberry Pi (incluso Pi Zero W).

## Requisiti

### Hardware
- **Raspberry Pi** (qualsiasi modello, incluso Pi Zero W)
- **MeshCore Companion Radio** (Heltec V3, T-Beam, o compatibile)
- Connessione al companion via **TCP/WiFi** o **USB seriale**

### Software
- **Raspberry Pi OS** (Lite consigliato per Pi Zero)
- **Python 3.9+**
- **SQLite 3**

**Non serve Node.js** — l'interfaccia web usa bottle.py (zero dipendenze compilate).

---

## Installazione Automatica

```bash
git clone https://github.com/atomozero/MeshBBS.git
cd MeshBBS
sudo ./deploy/install.sh
```

Lo script genera una **password admin casuale**, la salva come `ADMIN_PASSWORD` in
`/var/lib/meshbbs/config.env` e la stampa **una sola volta** a fine installazione: annotala.

---

## Installazione Manuale

### 1. Prepara il sistema

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git sqlite3
```

### 2. Crea utente e directory

```bash
sudo useradd -r -s /bin/false -m -d /opt/meshbbs meshbbs
sudo mkdir -p /var/lib/meshbbs/backups /var/log/meshbbs
```

### 3. Clona il repository

```bash
sudo git clone https://github.com/atomozero/MeshBBS.git /opt/meshbbs
sudo chown -R meshbbs:meshbbs /opt/meshbbs
```

### 4. Crea virtualenv e installa dipendenze

```bash
sudo -u meshbbs python3 -m venv /opt/meshbbs/venv
sudo -u meshbbs /opt/meshbbs/venv/bin/pip install --upgrade pip

# Installazione leggera (Pi Zero, niente BLE)
sudo -u meshbbs /opt/meshbbs/venv/bin/pip install --no-deps meshcore
sudo -u meshbbs /opt/meshbbs/venv/bin/pip install SQLAlchemy pycryptodome pycayennelpp pyserial pyserial-asyncio-fast

# RSS news per !news (incluso in requirements.txt / requirements-light.txt)
sudo -u meshbbs /opt/meshbbs/venv/bin/pip install feedparser
```

### 5. Crea configurazione

```bash
# Genera una password admin casuale (annotala!)
ADMIN_PW="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 20)"
echo "Password admin web: $ADMIN_PW"

sudo tee /var/lib/meshbbs/config.env << EOF
BBS_NAME=MeshBBS
DATABASE_PATH=/var/lib/meshbbs/meshbbs.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=$ADMIN_PW
LOG_LEVEL=INFO
LOG_FILE=/var/log/meshbbs/meshbbs.log
EOF

sudo chmod 600 /var/lib/meshbbs/config.env
sudo chown meshbbs:meshbbs /var/lib/meshbbs/config.env
```

> Non esiste una password predefinita: se `ADMIN_PASSWORD` è vuota o vale `meshbbs123`
> (o un segnaposto di esempio) il login web resta **disabilitato** finché non imposti
> una password robusta e riavvii il servizio. Opzionale: `WEB_SESSION_TTL` (secondi,
> default 28800 = 8 ore) imposta la scadenza della sessione per inattività.

### 6. Crea servizio systemd

#### Connessione TCP (WiFi companion)

```bash
sudo tee /etc/systemd/system/meshbbs.service << 'EOF'
[Unit]
Description=MeshBBS (BBS + Web)
After=network.target

[Service]
Type=simple
User=meshbbs
Group=meshbbs
WorkingDirectory=/opt/meshbbs/src
EnvironmentFile=/var/lib/meshbbs/config.env
ExecStart=/opt/meshbbs/venv/bin/python launcher.py \
    --tcp \
    --tcp-host 192.168.1.100 \
    --tcp-port 5000 \
    -n "MeshBBS" \
    -d /var/lib/meshbbs/meshbbs.db \
    --log-file /var/log/meshbbs/meshbbs.log \
    --web-port 8080
Restart=always
RestartSec=10

NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/meshbbs /var/log/meshbbs
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
```

Modifica `--tcp-host` con l'IP del tuo companion radio.

Non usare `--mock` nei servizi di produzione: senza quel flag il BBS si avvia anche se
il companion è spento o irraggiungibile e ritenta la connessione da solo (backoff fino a 5 minuti).

#### Connessione seriale (USB companion)

```bash
sudo tee /etc/systemd/system/meshbbs.service << 'EOF'
[Unit]
Description=MeshBBS (BBS + Web)
After=network.target

[Service]
Type=simple
User=meshbbs
Group=meshbbs
WorkingDirectory=/opt/meshbbs/src
EnvironmentFile=/var/lib/meshbbs/config.env
ExecStart=/opt/meshbbs/venv/bin/python launcher.py \
    -p /dev/ttyUSB0 \
    -n "MeshBBS" \
    -d /var/lib/meshbbs/meshbbs.db \
    --log-file /var/log/meshbbs/meshbbs.log \
    --web-port 8080
Restart=always
RestartSec=10

NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/meshbbs /var/log/meshbbs
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
```

### 7. Permessi e avvio

```bash
sudo chown -R meshbbs:meshbbs /opt/meshbbs /var/lib/meshbbs /var/log/meshbbs
sudo systemctl daemon-reload
sudo systemctl enable meshbbs
sudo systemctl start meshbbs
```

### 8. Verifica

```bash
# Stato servizio
sudo systemctl status meshbbs

# Log in tempo reale
sudo journalctl -u meshbbs -f

# Test web
curl http://localhost:8080/api/health
```

Apri nel browser: `http://<IP-DELLA-PI>:8080`

Credenziali: `admin` / la password `ADMIN_PASSWORD` del config.env
(generata da `install.sh` oppure scelta da te al passo 5)

---

## Aggiornamento

```bash
cd /opt/meshbbs
sudo -u meshbbs git pull
sudo -u meshbbs /opt/meshbbs/venv/bin/pip install feedparser   # nuova dipendenza dalla 1.6.0
sudo systemctl restart meshbbs
```

Aggiornando alla 1.6.0:
- se `config.env` contiene ancora `ADMIN_PASSWORD=meshbbs123` il login web viene disabilitato:
  imposta una nuova password e riavvia
- `COOKIE_SECRET` non è più usato e può essere rimosso
- al primo avvio le chiavi utente vengono normalizzate automaticamente (eventuali duplicati
  dello stesso nodo vengono uniti)

---

## Comandi utili

```bash
# Riavvia
sudo systemctl restart meshbbs

# Ferma
sudo systemctl stop meshbbs

# Log
sudo journalctl -u meshbbs -f

# Stato
sudo systemctl status meshbbs
```

---

## Troubleshooting

### Porta seriale non trovata

```bash
ls -la /dev/ttyUSB* /dev/ttyACM*
sudo usermod -aG dialout meshbbs
```

### Companion TCP non raggiungibile

```bash
ping 192.168.1.100
nc -zv 192.168.1.100 5000
```

### Permessi database

```bash
sudo chown -R meshbbs:meshbbs /var/lib/meshbbs
```

### Errore "Read-only file system"

Verifica che `ReadWritePaths` nel file service includa `/var/lib/meshbbs` e `/var/log/meshbbs`.
