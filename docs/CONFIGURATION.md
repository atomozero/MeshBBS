# MeshBBS Configuration Guide

Guida alla configurazione di MeshBBS.

## File di Configurazione

In produzione le impostazioni sono nel file `/var/lib/meshbbs/config.env`:

```bash
BBS_NAME=0Bit BBS
DATABASE_PATH=/var/lib/meshbbs/meshbbs.db
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<password generata da install.sh>
LOG_LEVEL=INFO
LOG_FILE=/var/log/meshbbs/meshbbs.log
```

Le impostazioni runtime vengono salvate anche in `settings.json` accanto al database.

> **Password admin**: non esiste una password predefinita. `deploy/install.sh` ne genera
> una casuale, la scrive in `config.env` e la mostra una sola volta a fine installazione.
> Se `ADMIN_PASSWORD` non è impostata o vale `meshbbs123` (o uno dei segnaposto della
> documentazione), il login web resta **disabilitato** e la pagina di login lo segnala.
> Per cambiarla: modifica `ADMIN_PASSWORD` in `config.env` e riavvia il servizio.

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
| `--mock` | | **Solo sviluppo**: se la radio reale non risponde usa una radio simulata |

Senza `--mock` (produzione) il BBS non passa mai alla radio simulata: si avvia comunque
anche con il companion offline e ritenta la connessione in background con backoff
esponenziale (5s → 10s → ... → 300s). Il link viene verificato ogni 150s; se il companion
non risponde parte la riconnessione automatica. Il timeout di connessione è 15s.

### Opzioni BBS

| Opzione | Default | Descrizione |
|---------|---------|-------------|
| `-n`, `--name` | `MeshCore BBS` | Nome del BBS |
| `-d`, `--database` | `data/bbs.db` | Path database SQLite |
| `--log-file` | `logs/bbs.log` | Path file di log |
| `--debug` | | Abilita log debug (il testo dei messaggi di canale è loggato solo in DEBUG) |

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

# Sviluppo senza hardware (radio simulata)
python launcher.py --mock --debug
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
| `ADMIN_PASSWORD` | (nessuno) | Password per login web. **Obbligatoria**: se vuota o predefinita il login è disabilitato |
| `WEB_SESSION_TTL` | `28800` | Scadenza sessione per inattività, in secondi (8 ore, minimo 60) |
| `WEB_NODES_CACHE_TTL` | `60` | Secondi di cache della lista nodi mesh nel pannello (minimo 5) |
| `WEB_CONTACTS_REFRESH` | `60` | Secondi minimi tra due refresh dei contatti dalla radio (minimo 10) |

Le sessioni web sono lato server con id casuale, cookie `HttpOnly` e `SameSite=Strict`
(`Secure` se servito in HTTPS). Le richieste che modificano dati richiedono un token CSRF
e un `Origin` coerente. `COOKIE_SECRET` non è più utilizzato e può essere rimosso.

### Database

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `DATABASE_PATH` | `data/bbs.db` | Path database SQLite |
| `BBS_DATABASE_KEY` | (vuoto) | Chiave SQLCipher — *non ancora attivo*: viene letta ma non applicata |

All'avvio il BBS normalizza le chiavi utente: l'identità di ogni utente è il prefisso di
12 caratteri esadecimali minuscoli della chiave pubblica. Gli utenti salvati con la chiave
completa (64 caratteri) vengono convertiti o uniti al duplicato. La migrazione è idempotente
e non richiede interventi manuali.

### Privacy e Retention

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `BBS_PM_RETENTION_DAYS` | `30` | Giorni retention PM (0=infinito) |
| `BBS_LOG_RETENTION_DAYS` | `90` | Giorni retention log (0=infinito) |
| `BBS_ALLOW_EPHEMERAL_PM` | `true` | Abilita messaggi effimeri (`!msg!`); con `false` il comando viene rifiutato |

La pulizia automatica di PM e log scaduti viene eseguita una volta al giorno.

### Rate Limiting

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `RATE_LIMIT_MIN_INTERVAL` | `1` | Secondi minimi tra comandi |
| `RATE_LIMIT_PER_MINUTE` | `30` | Comandi massimi al minuto |

Il rate limiter è attivo per tutti gli utenti tranne gli admin (ruolo verificato a ogni comando).
Nota: al momento il launcher usa i valori predefiniti (1s, 30/min, blocco 60s); queste
variabili d'ambiente non vengono ancora lette.

### Throttling Invio

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `SEND_DELAY` | `5.0` | Secondi pausa tra chunk di risposta |
| `MAX_SEND_ATTEMPTS` | `2` | Tentativi massimi invio |
| `SEND_RETRY_DELAY` | `2.0` | Secondi base tra retry |

Nota: questi valori si leggono da `settings.json` (`send_delay`, `max_send_attempts`,
`send_retry_delay`), non dalle variabili d'ambiente; `send_delay` è modificabile anche dalla pagina `/settings`.

Le risposte sono spezzate in chunk da massimo 140 byte UTF-8. Ogni destinatario ha la
propria coda di invio; se un chunk fallisce i successivi non vengono inviati.

### Beacon

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `beacon_interval` | `0` | Minuti tra beacon broadcast (0=off) |
| `beacon_message` | `{name} attivo! Scrivi !help per i comandi` | Testo beacon |

Configurabile dalla pagina web Impostazioni (`/settings`). Un errore nel template del
messaggio viene loggato ma non ferma il beacon.

### Logging

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Livello: DEBUG, INFO, WARNING, ERROR |
| `LOG_FILE` | `logs/bbs.log` | Path file log |

### MQTT (non ancora attivo)

> Il client MQTT esiste nel codice ma il launcher non lo connette mai: queste variabili
> al momento non hanno effetto.

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
| `stats_publish_interval` | int | Secondi tra publish MQTT stats (*non ancora attivo*) |

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

Richiede `feedparser`, incluso in `requirements.txt` e `requirements-light.txt`.
Download e parsing hanno un timeout (5s download, 8s totali): un feed lento non blocca il BBS.

---

## MQTT per Home Assistant (non ancora attivo)

Esempio per quando l'integrazione MQTT sarà collegata al launcher:

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
