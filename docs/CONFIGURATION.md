# MeshBBS Configuration Guide

Guida completa alla configurazione di MeshBBS.

## Gerarchia Configurazione

MeshBBS usa un sistema di configurazione a 3 livelli (in ordine di priorità):

1. **Variabili d'ambiente** (massima priorità)
2. **File settings.json** (persistente via API)
3. **Valori default** (fallback)

### File di Configurazione Persistente

Le impostazioni modificate via Web Admin vengono salvate in `data/settings.json`:

```json
{
  "bbs_name": "My MeshBBS",
  "default_area": "generale",
  "max_message_length": 200,
  "pm_retention_days": 30,
  "activity_log_retention_days": 90,
  "allow_ephemeral_pm": true
}
```

**Nota**: Le variabili d'ambiente hanno sempre priorità sul file JSON.

### Campi Modificabili via API

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `bbs_name` | string | Nome visualizzato del BBS |
| `default_area` | string | Area messaggi predefinita |
| `max_message_length` | int | Lunghezza massima messaggio |
| `latitude` | float | Latitudine BBS (-90/+90) |
| `longitude` | float | Longitudine BBS (-180/+180) |
| `pm_retention_days` | int | Giorni retention PM (0=infinito) |
| `activity_log_retention_days` | int | Giorni retention log |
| `allow_ephemeral_pm` | bool | Abilita messaggi effimeri |
| `min_message_interval` | float | Secondi minimi tra messaggi |
| `max_messages_per_minute` | int | Messaggi max al minuto |
| `advert_interval_minutes` | int | Minuti tra advertisement |
| `send_delay` | float | Secondi tra chunk di risposta (default: 3.0) |
| `max_send_attempts` | int | Tentativi massimi invio (default: 2) |
| `send_retry_delay` | float | Secondi base tra retry invio (default: 2.0) |
| `stats_publish_interval` | int | Secondi tra pubblicazioni stats MQTT (default: 300) |

---

## Configurazione via Environment

MeshBBS si configura principalmente tramite variabili d'ambiente. In produzione, queste sono definite nel file `/var/lib/meshbbs/config.env`.

## Variabili d'Ambiente

### BBS Core

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `BBS_NAME` | `MeshCore BBS` | Nome visualizzato del BBS |
| `BBS_WELCOME` | `Welcome to MeshBBS!` | Messaggio di benvenuto |
| `BBS_DEFAULT_AREA` | `generale` | Area messaggi predefinita |
| `BBS_RESPONSE_PREFIX` | `[BBS]` | Prefisso risposte |
| `BBS_ADVERT_INTERVAL` | `15` | Minuti tra advertisement |
| `BBS_LATITUDE` | (vuoto) | Latitudine BBS (es. 45.4642) |
| `BBS_LONGITUDE` | (vuoto) | Longitudine BBS (es. 9.1900) |

### Throttling Invio

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `SEND_DELAY` | `3.0` | Secondi di pausa tra chunk di risposta multi-riga |
| `MAX_SEND_ATTEMPTS` | `2` | Tentativi massimi di invio messaggio |
| `SEND_RETRY_DELAY` | `2.0` | Secondi base tra retry (backoff lineare) |
| `STATS_PUBLISH_INTERVAL` | `300` | Secondi tra pubblicazioni stats MQTT |

### Connessione Radio

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `SERIAL_PORT` | `/dev/ttyUSB0` | Porta seriale companion radio |
| `BAUD_RATE` | `115200` | Baud rate seriale |
| `SERIAL_TIMEOUT` | `1.0` | Timeout connessione (secondi) |
| `USE_MOCK_FALLBACK` | `true` | Fallback a mock se hardware non disponibile |

### Database

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `DATABASE_PATH` | `/var/lib/meshbbs/meshbbs.db` | Path database SQLite |
| `DATABASE_KEY` | (vuoto) | Chiave SQLCipher (vuoto = no crittografia) |

### Web Interface

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `WEB_HOST` | `0.0.0.0` | Indirizzo bind server web |
| `WEB_PORT` | `8080` | Porta server web |
| `WEB_DEBUG` | `false` | Modalità debug (abilita /api/docs) |
| `CORS_ORIGINS` | `*` | Origini CORS permesse (separati da virgola) |

### Autenticazione JWT

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `JWT_SECRET` | (richiesto) | Chiave segreta per firmare JWT |
| `JWT_ACCESS_EXPIRE` | `30` | Minuti validità access token |
| `JWT_REFRESH_EXPIRE` | `7` | Giorni validità refresh token |
| `AUTH_MAX_ATTEMPTS` | `5` | Tentativi login prima del blocco |
| `AUTH_LOCKOUT_MINUTES` | `15` | Minuti blocco dopo troppi tentativi |

### Admin Iniziale

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ADMIN_USERNAME` | `admin` | Username admin iniziale |
| `ADMIN_PASSWORD` | `meshbbs123` | Password admin iniziale |

⚠️ **Cambia la password dopo il primo login!**

### Privacy e Retention

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `PM_RETENTION_DAYS` | `30` | Giorni retention messaggi privati (0=infinito) |
| `LOG_RETENTION_DAYS` | `90` | Giorni retention log (0=infinito) |
| `ALLOW_EPHEMERAL_PM` | `true` | Abilita messaggi effimeri (/msg!) |

### Rate Limiting

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Abilita rate limiting |
| `RATE_LIMIT_MIN_INTERVAL` | `1` | Secondi minimi tra comandi |
| `RATE_LIMIT_PER_MINUTE` | `30` | Comandi massimi al minuto |
| `RATE_LIMIT_BLOCK_SECONDS` | `60` | Secondi blocco per violazione |

### Backup

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `BACKUP_ENABLED` | `true` | Abilita backup automatici |
| `BACKUP_INTERVAL_HOURS` | `24` | Ore tra backup automatici |
| `BACKUP_MAX_COUNT` | `7` | Numero massimo backup da mantenere |
| `BACKUP_COMPRESS` | `true` | Comprimi backup con gzip |
| `BACKUP_PATH` | `/var/lib/meshbbs/backups` | Directory backup |

### MQTT (Opzionale)

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `MQTT_ENABLED` | `false` | Abilita integrazione MQTT |
| `MQTT_HOST` | `localhost` | Host broker MQTT |
| `MQTT_PORT` | `1883` | Porta broker MQTT |
| `MQTT_USERNAME` | (vuoto) | Username MQTT |
| `MQTT_PASSWORD` | (vuoto) | Password MQTT |
| `MQTT_CLIENT_ID` | `meshbbs` | Client ID MQTT |
| `MQTT_TOPIC_PREFIX` | `meshbbs` | Prefisso topic |
| `MQTT_TLS_ENABLED` | `false` | Usa TLS |
| `MQTT_TLS_CA_CERTS` | (vuoto) | Path certificato CA |
| `MQTT_QOS` | `1` | QoS level (0, 1, 2) |
| `MQTT_RETAIN` | `false` | Retain messages |

### Logging

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Livello log: DEBUG, INFO, WARNING, ERROR |
| `LOG_FILE` | `/var/log/meshbbs/meshbbs.log` | Path file log |
| `LOG_MAX_SIZE` | `10485760` | Dimensione max file log (bytes) |
| `LOG_BACKUP_COUNT` | `5` | Numero file log da mantenere |

---

## File di Configurazione

### Esempio config.env

```bash
# MeshBBS Configuration
# /var/lib/meshbbs/config.env

# === BBS Identity ===
BBS_NAME=MeshBBS Italia
BBS_WELCOME="Benvenuto su MeshBBS Italia!"
BBS_DEFAULT_AREA=generale

# === Location (opzionale) ===
# BBS_LATITUDE=45.4642
# BBS_LONGITUDE=9.1900

# === Radio Connection ===
SERIAL_PORT=/dev/ttyUSB0
BAUD_RATE=115200

# === Database ===
DATABASE_PATH=/var/lib/meshbbs/meshbbs.db
# DATABASE_KEY=your-encryption-key  # Decommentare per crittografia

# === Web Interface ===
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_DEBUG=false

# === Authentication ===
JWT_SECRET=cambia-questa-chiave-segreta-molto-lunga
JWT_ACCESS_EXPIRE=30
JWT_REFRESH_EXPIRE=7
ADMIN_USERNAME=admin
ADMIN_PASSWORD=password-sicura-cambiami

# === Privacy ===
PM_RETENTION_DAYS=30
LOG_RETENTION_DAYS=90

# === Rate Limiting ===
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=30

# === Backup ===
BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24
BACKUP_MAX_COUNT=7

# === MQTT (opzionale) ===
MQTT_ENABLED=false
# MQTT_HOST=mqtt.example.com
# MQTT_USERNAME=meshbbs
# MQTT_PASSWORD=secret

# === Logging ===
LOG_LEVEL=INFO
LOG_FILE=/var/log/meshbbs/meshbbs.log
```

---

## Configurazione Avanzata

### Crittografia Database

Per proteggere i dati a riposo con SQLCipher:

1. Installa pysqlcipher3:
   ```bash
   pip install pysqlcipher3
   ```

2. Imposta la chiave:
   ```bash
   DATABASE_KEY=chiave-crittografia-molto-lunga-e-sicura
   ```

⚠️ **Non perdere la chiave!** Senza di essa i dati non saranno recuperabili.

### MQTT per Home Assistant

Esempio configurazione per Home Assistant:

```yaml
# configuration.yaml
mqtt:
  sensor:
    - name: "MeshBBS Users"
      state_topic: "meshbbs/stats"
      value_template: "{{ value_json.users.total }}"

    - name: "MeshBBS Active Users 24h"
      state_topic: "meshbbs/stats"
      value_template: "{{ value_json.users.active_24h }}"

    - name: "MeshBBS Messages Today"
      state_topic: "meshbbs/stats"
      value_template: "{{ value_json.messages.public.today }}"

    - name: "MeshBBS Messages Last Hour"
      state_topic: "meshbbs/stats"
      value_template: "{{ value_json.messages.public.last_hour }}"

    - name: "MeshBBS Delivery Success Rate"
      state_topic: "meshbbs/stats"
      value_template: "{{ value_json.delivery.success_rate }}"
      unit_of_measurement: "%"

    - name: "MeshBBS Radio Connected"
      state_topic: "meshbbs/stats"
      value_template: "{{ value_json.radio.connected }}"

    - name: "MeshBBS Radio Battery"
      state_topic: "meshbbs/stats"
      value_template: "{{ value_json.radio.battery_level }}"
      unit_of_measurement: "%"

    - name: "MeshBBS Status"
      state_topic: "meshbbs/status"
      value_template: "{{ value_json.status }}"
```

Le statistiche vengono pubblicate ogni `STATS_PUBLISH_INTERVAL` secondi (default: 300 = 5 minuti) sul topic `meshbbs/stats` con flag `retain`.

Il payload completo e disponibile anche via REST API: `GET /api/v1/stats`.

### Reverse Proxy con Nginx

```nginx
server {
    listen 80;
    server_name meshbbs.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name meshbbs.example.com;

    ssl_certificate /etc/letsencrypt/live/meshbbs.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/meshbbs.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Porte Seriali Multiple

Se hai più dispositivi USB:

```bash
# Trova la porta corretta
ls -la /dev/ttyUSB*
ls -la /dev/ttyACM*

# Usa udev rules per nome fisso
# /etc/udev/rules.d/99-meshcore.rules
SUBSYSTEM=="tty", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", SYMLINK+="meshcore"

# Ricarica udev
sudo udevadm control --reload-rules
sudo udevadm trigger

# Usa /dev/meshcore nella config
SERIAL_PORT=/dev/meshcore
```

---

## Sicurezza

### Checklist Produzione

- [ ] Cambia password admin default
- [ ] Genera JWT_SECRET unico e forte
- [ ] Configura HTTPS con reverse proxy
- [ ] Limita CORS_ORIGINS agli host necessari
- [ ] Abilita firewall, esponi solo porta 443
- [ ] Considera crittografia database
- [ ] Configura backup automatici
- [ ] Monitora i log

### Generare JWT Secret Sicuro

```bash
openssl rand -hex 32
```

---

## Troubleshooting

### Porta Seriale Non Trovata

```bash
# Verifica permessi
ls -la /dev/ttyUSB0
sudo usermod -aG dialout meshbbs

# Verifica dispositivo collegato
dmesg | grep tty
```

### Database Locked

```bash
# Verifica processi
fuser /var/lib/meshbbs/meshbbs.db

# Rimuovi lock (attenzione!)
rm /var/lib/meshbbs/meshbbs.db-wal
rm /var/lib/meshbbs/meshbbs.db-shm
```

### Token JWT Non Valido

Verifica:
1. JWT_SECRET uguale in tutti i servizi
2. Orologio di sistema sincronizzato (NTP)
3. Token non scaduto

### MQTT Non Si Connette

```bash
# Test connessione
mosquitto_pub -h mqtt.example.com -t test -m "hello"

# Verifica firewall
sudo ufw allow 1883/tcp
```
