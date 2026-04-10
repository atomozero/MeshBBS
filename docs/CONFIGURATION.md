# MeshBBS Configuration Guide

Guida alla configurazione di MeshBBS.

## File di Configurazione

In produzione le impostazioni sono nel file `/var/lib/meshbbs/config.env`:

```bash
BBS_NAME=0Bit BBS
DATABASE_PATH=/var/lib/meshbbs/meshbbs.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=password_sicura
LOG_LEVEL=INFO
LOG_FILE=/var/log/meshbbs/meshbbs.log
```

Le impostazioni runtime vengono salvate anche in `settings.json` accanto al database.

---

## Launcher

Il launcher unificato (`python launcher.py`) avvia BBS e web server insieme.

### Opzioni connessione

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `--tcp` | | Usa connessione TCP invece di seriale |
| `--tcp-host` | `192.168.1.100` | IP del companion radio |
| `--tcp-port` | `5000` | Porta TCP del companion |
| `-p`, `--port` | `/dev/ttyUSB0` | Porta seriale (se non TCP) |
| `-b`, `--baud` | `115200` | Baud rate seriale |

### Opzioni BBS

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `-n`, `--name` | `MeshCore BBS` | Nome del BBS |
| `-d`, `--database` | `data/bbs.db` | Path database SQLite |
| `--log-file` | `logs/bbs.log` | Path file di log |
| `--debug` | | Abilita log debug |

### Opzioni web server

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `--web-host` | `0.0.0.0` | Indirizzo bind web server |
| `--web-port` | `8080` | Porta web server |
| `--web-only` | | Avvia solo il web server |
| `--bbs-only` | | Avvia solo il BBS radio |

### Esempi

```bash
# TCP companion + web
python launcher.py --tcp --tcp-host 192.168.188.93 --tcp-port 5000 -n "0Bit BBS"

# Serial companion + web su porta custom
python launcher.py -p /dev/ttyACM0 --web-port 9090

# Solo web (per debug)
python launcher.py --web-only --debug
```

---

## Variabili d'Ambiente (config.env)

### BBS

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `BBS_NAME` | `MeshCore BBS` | Nome visualizzato |
| `BBS_DEFAULT_AREA` | `generale` | Area messaggi predefinita |
| `BBS_RESPONSE_PREFIX` | `[BBS]` | Prefisso risposte |
| `BBS_ADVERT_INTERVAL` | `180` | Minuti tra advertisement automatici |
| `BBS_LATITUDE` | (vuoto) | Latitudine BBS per la mappa |
| `BBS_LONGITUDE` | (vuoto) | Longitudine BBS per la mappa |

### Web Admin

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ADMIN_USERNAME` | `admin` | Username per login web |
| `ADMIN_PASSWORD` | `meshbbs123` | Password per login web |

### Database

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `DATABASE_PATH` | `data/bbs.db` | Path database SQLite |

### Privacy e Retention

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `PM_RETENTION_DAYS` | `30` | Giorni retention PM (0=infinito) |
| `LOG_RETENTION_DAYS` | `90` | Giorni retention log (0=infinito) |
| `ALLOW_EPHEMERAL_PM` | `true` | Abilita messaggi effimeri (!msg!) |

### Rate Limiting

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `RATE_LIMIT_MIN_INTERVAL` | `1` | Secondi minimi tra comandi |
| `RATE_LIMIT_PER_MINUTE` | `30` | Comandi massimi al minuto |

### Throttling Invio

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `SEND_DELAY` | `5.0` | Secondi pausa tra chunk di risposta |
| `MAX_SEND_ATTEMPTS` | `2` | Tentativi massimi invio |
| `SEND_RETRY_DELAY` | `2.0` | Secondi base tra retry |

### Beacon

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `beacon_interval` | `0` | Minuti tra beacon broadcast (0=off) |
| `beacon_message` | `{name} attivo! Scrivi !help per i comandi` | Testo beacon |

Configurabile dalla pagina web Impostazioni (`/settings`).

### Logging

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Livello: DEBUG, INFO, WARNING, ERROR |
| `LOG_FILE` | `logs/bbs.log` | Path file log |

### MQTT (Opzionale)

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `MQTT_ENABLED` | `false` | Abilita integrazione MQTT |
| `MQTT_HOST` | `localhost` | Host broker MQTT |
| `MQTT_PORT` | `1883` | Porta broker |
| `MQTT_USERNAME` | (vuoto) | Username MQTT |
| `MQTT_PASSWORD` | (vuoto) | Password MQTT |
| `MQTT_TOPIC_PREFIX` | `meshbbs` | Prefisso topic |

---

## Configurazione Runtime (settings.json)

Le impostazioni modificabili a runtime vengono salvate in `settings.json`:

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `bbs_name` | string | Nome BBS |
| `default_area` | string | Area predefinita |
| `max_message_length` | int | Max lunghezza messaggio (default: 200) |
| `latitude` | float | Latitudine BBS (-90/+90) |
| `longitude` | float | Longitudine BBS (-180/+180) |
| `pm_retention_days` | int | Giorni retention PM |
| `activity_log_retention_days` | int | Giorni retention log |
| `send_delay` | float | Secondi tra chunk |
| `advert_interval_minutes` | int | Minuti tra advert automatici |
| `beacon_interval` | int | Minuti tra beacon broadcast (0=off) |
| `beacon_message` | string | Testo beacon ({name} = nome BBS) |
| `stats_publish_interval` | int | Secondi tra publish MQTT stats |

Modificabili dalla pagina web `/settings` senza SSH.

---

## RSS Feed News

Il comando `!news` usa feed RSS configurabili. I feed predefiniti sono:

| Nome | URL |
|------|-----|
| `ansa` | https://www.ansa.it/sito/ansait_rss.xml |
| `ansa-tech` | https://www.ansa.it/sito/notizie/tecnologia/tecnologia_rss.xml |
| `ansa-scienza` | https://www.ansa.it/sito/notizie/scienza/scienza_rss.xml |

Per modificare i feed, editare `src/bbs/commands/news_cmd.py`.

Richiede `feedparser`: `pip install feedparser`

---

## MQTT per Home Assistant

```yaml
mqtt:
  sensor:
    - name: "MeshBBS Users"
      state_topic: "meshbbs/stats"
      value_template: "{{ value_json.users.total }}"

    - name: "MeshBBS Messages Today"
      state_topic: "meshbbs/stats"
      value_template: "{{ value_json.messages.public.today }}"

    - name: "MeshBBS Radio Connected"
      state_topic: "meshbbs/stats"
      value_template: "{{ value_json.radio.connected }}"

    - name: "MeshBBS Status"
      state_topic: "meshbbs/status"
      value_template: "{{ value_json.status }}"
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

### Database locked

```bash
fuser /var/lib/meshbbs/meshbbs.db
```

### Permessi

```bash
sudo chown -R meshbbs:meshbbs /opt/meshbbs /var/lib/meshbbs /var/log/meshbbs
```
