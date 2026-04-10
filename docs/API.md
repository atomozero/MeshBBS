# MeshBBS Web API Documentation

API web leggera per l'amministrazione di MeshBBS.

Il web server usa bottle.py e serve pagine HTML con auto-refresh.
Tutte le pagine richiedono autenticazione tramite sessione cookie.

## Base URL

```
http://<ip-bbs>:8080
```

## Autenticazione

Login tramite form HTML su `/login`. Le sessioni usano cookie firmati.

Credenziali configurate in `config.env`:
- `ADMIN_USERNAME` (default: `admin`)
- `ADMIN_PASSWORD`

---

## Pagine Web

### Dashboard (`/`)

Pagina principale con:
- Card statistiche: utenti, messaggi oggi, PM, stato radio
- Alert repeater: notifica se un repeater scompare dalla rete
- Dettagli radio: nome, porta, batteria, uptime, messaggi processati
- Bottone "Invia Advert" per advertisement manuale
- Grafico attivita 24h: barre con messaggi (blu) e advert (giallo) per ora
- Attivita recente: ultimi 10 eventi
- Auto-refresh ogni 15 secondi

### Messaggi (`/messages`)

Lista ultimi 25 messaggi con:
- ID, autore, area, anteprima messaggio, data
- Auto-refresh ogni 15 secondi

### Utenti (`/users`)

Gestione utenti con azioni admin:
- Lista utenti con nome, chiave pubblica, stato, messaggi, ultimo accesso
- Bottoni azione per ogni utente:
  - **Mod** — promuove a moderatore
  - **Admin** — promuove moderatore ad admin
  - **Declassa** — rimuove ruolo admin/moderatore
  - **Ban** / **Sbanna** — banna/sbanna utente
  - **Mute** / **Smuta** — silenzia/ripristina utente
  - **Kick** — espelle per 60 minuti
- Conferma prima di ogni azione
- Toast di notifica successo/errore
- Auto-refresh ogni 15 secondi

### Rete (`/network`)

Visualizzazione rete mesh:
- Card conteggi: nodi totali (con GPS), ripetitori, client, BBS/room
- Mappa Leaflet (OpenStreetMap) con nodi colorati per tipo:
  - Rosso = BBS (posizione da config)
  - Giallo = Ripetitori (RPT)
  - Blu = Client (CLI)
  - Verde = Room/BBS (ROOM)
  - Viola = Sensori (SENS)
- Popup al click con nome, tipo, percorso
- Tabella nodi raggruppati per tipologia
- Indicatore GPS per nodi con coordinate
- Auto-refresh ogni 15 secondi

### Log (`/logs`)

Log attivita sistema:
- Ultimi 50 eventi con data, tipo, utente, dettagli
- Auto-refresh ogni 15 secondi

### Impostazioni (`/settings`)

Modifica configurazione BBS senza SSH:
- Nome BBS, prefisso risposte, area predefinita
- Coordinate GPS (latitudine, longitudine)
- Delay invio chunk, intervallo advert
- Beacon: intervallo e messaggio
- Retention PM e log
- Salva in settings.json senza riavvio

---

## API JSON

### GET `/api/health`

Health check (nessuna autenticazione richiesta).

**Risposta:**
```json
{
  "status": "ok",
  "radio_connected": true,
  "timestamp": "2026-04-09T18:30:00Z"
}
```

### GET `/api/stats`

Statistiche complete (richiede autenticazione).

**Risposta:**
```json
{
  "users": {"total": 15, "active_24h": 3, "new_today": 1, "banned": 0, "muted": 0},
  "messages": {
    "public": {"total": 120, "today": 5, "last_hour": 2, "week": 45},
    "private": {"total": 30, "today": 2, "unread": 5},
    "areas": 3
  },
  "radio": {"status": "connected", "connected": true, "messages_processed": 250},
  "system": {"bbs_name": "0Bit BBS", "uptime_seconds": 86400, "db_size_bytes": 524288},
  "collected_at": "2026-04-09T18:30:00Z"
}
```

### POST `/api/advert`

Invia advertisement manuale sulla rete mesh (richiede autenticazione).

**Risposta:**
```json
{"ok": true, "message": "Advertisement inviato"}
```

### POST `/api/user/<key>/<action>`

Esegue azione admin su un utente (richiede autenticazione).

**Azioni valide:** `ban`, `unban`, `mute`, `unmute`, `kick`, `unkick`, `promote`, `promote_admin`, `demote`

**Risposta:**
```json
{"ok": true, "message": "AtomoZero promosso a moderatore"}
```

### GET `/api/partial/dashboard`

Frammento HTML della dashboard (usato dall'auto-refresh).

### GET `/api/partial/messages`

Frammento HTML della tabella messaggi.

### GET `/api/partial/users`

Frammento HTML della tabella utenti.

### GET `/api/partial/network`

Frammento HTML della tabella rete.

### GET `/api/partial/logs`

Frammento HTML della tabella log.

---

## Indicatore Connessione

Tutte le pagine mostrano un pallino nella navbar:
- **Verde** = radio connessa
- **Rosso** = radio disconnessa

Si aggiorna automaticamente ogni 10 secondi tramite `/api/health`.

---

## Note Tecniche

- Il web server usa **bottle.py** (singolo file, zero dipendenze compilate)
- Gira in un **thread daemon** separato dal BBS
- Comunicazione con il BBS tramite **bbs.runtime** (variabili condivise)
- Operazioni async (advert, refresh contatti) usano **run_coroutine_threadsafe**
- La mappa usa **Leaflet.js** caricato da CDN
- Auto-refresh tramite `fetch()` + `setInterval()` (nessun WebSocket)
