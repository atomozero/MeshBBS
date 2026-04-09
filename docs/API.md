# MeshBBS REST API Documentation

API REST per l'amministrazione di MeshBBS.

## Base URL

```
http://localhost:8080/api/v1
```

## Autenticazione

L'API usa JWT (JSON Web Tokens) per l'autenticazione.

### Login

```http
POST /auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}
```

**Risposta:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Usare il Token

Includi il token in tutte le richieste:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Refresh Token

```http
POST /auth/refresh
Cookie: refresh_token=...
```

### Logout

```http
POST /auth/logout
```

### Two-Factor Authentication (2FA)

#### Login con 2FA

Se l'utente ha 2FA abilitato, il login restituisce un token temporaneo:

```http
POST /auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}
```

**Risposta (2FA richiesto):**
```json
{
  "requires_2fa": true,
  "pending_token": "eyJhbGciOiJIUzI1NiIs...",
  "message": "Autenticazione a due fattori richiesta"
}
```

Completa il login con il codice TOTP o un backup code:

```http
POST /auth/2fa/verify
Content-Type: application/json

{
  "pending_token": "eyJhbGciOiJIUzI1NiIs...",
  "totp_code": "123456"
}
```

#### Setup 2FA

```http
POST /auth/2fa/setup
Authorization: Bearer <token>
```

**Risposta:**
```json
{
  "secret": "JBSWY3DPEHPK3PXP...",
  "provisioning_uri": "otpauth://totp/MeshBBS:admin?secret=...",
  "backup_codes": [
    "ABCD-1234",
    "EFGH-5678",
    ...
  ],
  "qr_data": "otpauth://totp/..."
}
```

#### Abilita 2FA

Dopo setup, conferma con un codice TOTP:

```http
POST /auth/2fa/enable
Authorization: Bearer <token>
Content-Type: application/json

{
  "totp_code": "123456"
}
```

#### Stato 2FA

```http
GET /auth/2fa/status
Authorization: Bearer <token>
```

**Risposta:**
```json
{
  "enabled": true,
  "backup_codes_remaining": 8
}
```

#### Disabilita 2FA

```http
POST /auth/2fa/disable
Authorization: Bearer <token>
Content-Type: application/json

{
  "password": "current_password",
  "totp_code": "123456"
}
```

#### Rigenera Backup Codes

```http
POST /auth/2fa/backup-codes
Authorization: Bearer <token>
Content-Type: application/json

{
  "totp_code": "123456"
}
```

**Risposta:**
```json
{
  "backup_codes": [
    "WXYZ-9012",
    ...
  ],
  "remaining": 10
}
```

---

## Endpoints

### Dashboard

#### GET /dashboard/stats

Statistiche generali del BBS.

**Risposta:**
```json
{
  "users": {
    "total": 150,
    "active_24h": 23,
    "active_7d": 89,
    "banned": 5,
    "muted": 2
  },
  "messages": {
    "total": 5420,
    "today": 45,
    "week": 320
  },
  "areas": {
    "total": 8,
    "public": 6,
    "readonly": 1
  },
  "system": {
    "uptime_seconds": 86400,
    "db_size_bytes": 2621440,
    "radio_connected": true
  }
}
```

#### GET /dashboard/activity

Feed attività recenti.

**Query params:**
- `limit` (default: 10, max: 50)

**Risposta:**
```json
{
  "items": [
    {
      "id": 1,
      "timestamp": "2026-01-18T10:30:00Z",
      "event_type": "MESSAGE_POSTED",
      "user_key": "ABC123...",
      "description": "Nuovo messaggio in #generale"
    }
  ],
  "total": 100
}
```

#### GET /dashboard/chart

Dati per grafici attività.

**Query params:**
- `period`: `7d`, `30d`, `90d` (default: `7d`)

**Risposta:**
```json
{
  "labels": ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"],
  "messages": [45, 52, 38, 61, 49, 33, 28],
  "users": [12, 15, 11, 18, 14, 9, 7]
}
```

---

### Users

#### GET /users

Lista utenti con paginazione.

**Query params:**
- `page` (default: 1)
- `limit` (default: 20, max: 100)
- `search` - Cerca per nickname o chiave
- `role` - Filtra per ruolo: `admin`, `moderator`, `user`
- `status` - Filtra per stato: `active`, `banned`, `muted`

**Risposta:**
```json
{
  "items": [
    {
      "id": 1,
      "public_key": "ABC123DEF456...",
      "nickname": "Mario",
      "role": "user",
      "is_banned": false,
      "is_muted": false,
      "last_seen": "2026-01-18T10:30:00Z",
      "created_at": "2026-01-01T00:00:00Z",
      "message_count": 42
    }
  ],
  "total": 150,
  "page": 1,
  "limit": 20,
  "pages": 8
}
```

#### GET /users/{user_id}

Dettaglio singolo utente.

#### POST /users/{user_id}/ban

Banna un utente.

**Body:**
```json
{
  "reason": "Spam ripetuto"
}
```

#### POST /users/{user_id}/unban

Rimuove il ban.

#### POST /users/{user_id}/mute

Silenzia un utente.

#### POST /users/{user_id}/unmute

Rimuove il silenziamento.

#### POST /users/{user_id}/kick

Espelle temporaneamente.

**Body:**
```json
{
  "duration_minutes": 60,
  "reason": "Comportamento inadeguato"
}
```

#### POST /users/{user_id}/promote

Promuove l'utente.

**Body:**
```json
{
  "role": "moderator"
}
```

---

### Areas

#### GET /areas

Lista aree messaggi.

**Query params:**
- `page`, `limit`
- `include_hidden` (default: false, solo admin)

**Risposta:**
```json
{
  "items": [
    {
      "id": 1,
      "name": "generale",
      "description": "Discussioni generali",
      "is_public": true,
      "is_readonly": false,
      "message_count": 1234,
      "created_at": "2026-01-01T00:00:00Z"
    }
  ],
  "total": 8
}
```

#### GET /areas/{area_id}

Dettaglio area con statistiche.

#### POST /areas

Crea nuova area (admin).

**Body:**
```json
{
  "name": "tech",
  "description": "Discussioni tecniche",
  "is_public": true,
  "is_readonly": false
}
```

#### PATCH /areas/{area_id}

Modifica area (admin).

#### DELETE /areas/{area_id}

Elimina area (admin). Non eliminabile se protetta.

---

### Messages

#### GET /messages

Lista messaggi con filtri.

**Query params:**
- `page`, `limit`
- `area_id` - Filtra per area
- `user_id` - Filtra per autore
- `search` - Cerca nel contenuto

**Risposta:**
```json
{
  "items": [
    {
      "id": 1,
      "area_id": 1,
      "area_name": "generale",
      "sender_key": "ABC123...",
      "sender_nickname": "Mario",
      "content": "Ciao a tutti!",
      "created_at": "2026-01-18T10:30:00Z",
      "reply_count": 3
    }
  ],
  "total": 5420
}
```

#### GET /messages/{message_id}

Dettaglio messaggio con thread.

#### DELETE /messages/{message_id}

Elimina messaggio (admin/moderator).

---

### Logs

#### GET /logs

Lista log di sistema.

**Query params:**
- `page`, `limit`
- `event_type` - Filtra per tipo evento
- `user_key` - Filtra per utente
- `from_date`, `to_date` - Range temporale

**Risposta:**
```json
{
  "items": [
    {
      "id": 1,
      "timestamp": "2026-01-18T10:30:00Z",
      "event_type": "USER_LOGIN",
      "user_key": "ABC123...",
      "details": "Login da 192.168.1.100"
    }
  ],
  "total": 10000
}
```

#### GET /logs/types

Lista tipi di evento disponibili.

#### GET /logs/stats

Statistiche log.

---

### Radio

#### GET /radio/status

Stato connessione radio MeshCore.

**Risposta:**
```json
{
  "status": "connected",
  "is_connected": true,
  "radio": {
    "public_key": "ABC123DEF456...",
    "name": "MeshBBS Node",
    "port": "/dev/ttyUSB0",
    "baud_rate": 115200,
    "is_mock": false,
    "battery_level": 85,
    "battery_charging": false
  },
  "connected_at": "2026-01-18T08:00:00Z",
  "last_activity": "2026-01-18T10:30:00Z",
  "error": null,
  "message_count": 1234,
  "reconnect_attempts": 0
}
```

**Stati possibili:**
- `disconnected` - Non connesso
- `connecting` - Connessione in corso
- `connected` - Connesso
- `reconnecting` - Riconnessione in corso
- `error` - Errore

#### GET /radio/health

Health check rapido (senza autenticazione).

**Risposta:**
```json
{
  "connected": true,
  "status": "connected",
  "timestamp": "2026-01-18T10:30:00Z"
}
```

---

### BBS Control

#### GET /bbs/status

Stato del servizio BBS radio (richiede autenticazione admin).

**Risposta:**
```json
{
  "bbs_running": true,
  "radio": {
    "status": "connected",
    "is_connected": true,
    "radio": {
      "public_key": "ABC123...",
      "name": "MeshBBS Node",
      "port": "/dev/ttyUSB0",
      "battery_level": 85,
      "battery_charging": false
    },
    "message_count": 1234,
    "reconnect_attempts": 0
  },
  "radio_uptime_seconds": 86400,
  "timestamp": "2026-01-18T10:30:00Z"
}
```

#### POST /bbs/restart

Riavvia il servizio BBS radio (solo superadmin). Disponibile solo con il launcher unificato.

**Risposta:**
```json
{
  "message": "Riavvio BBS in corso",
  "timestamp": "2026-01-18T10:30:00Z"
}
```

#### POST /bbs/advert

Invia manualmente un advertisement sulla rete mesh.

**Risposta:**
```json
{
  "message": "Advertisement inviato",
  "timestamp": "2026-01-18T10:30:00Z"
}
```

---

### Settings

#### GET /settings

Configurazione corrente (admin).

**Risposta:**
```json
{
  "bbs_name": "MeshBBS",
  "default_area": "generale",
  "max_message_length": 200,
  "pm_retention_days": 30,
  "log_retention_days": 90,
  "allow_ephemeral_pm": true,
  "serial_port": "/dev/ttyUSB0",
  "baud_rate": 115200,
  "database_path": "/var/lib/meshbbs/meshbbs.db",
  "log_path": "/var/log/meshbbs/meshbbs.log"
}
```

#### PATCH /settings

Aggiorna configurazione (superadmin).

Le modifiche vengono persistite nel file `data/settings.json`.

**Body:**
```json
{
  "bbs_name": "My MeshBBS",
  "pm_retention_days": 60,
  "allow_ephemeral_pm": false
}
```

**Campi modificabili:**
- `bbs_name` (string, 1-50 char)
- `default_area` (string, 2-32 char)
- `max_message_length` (int, 50-1000)
- `latitude` (float, -90/+90) - Latitudine BBS
- `longitude` (float, -180/+180) - Longitudine BBS
- `pm_retention_days` (int, 0-365, 0=infinito)
- `log_retention_days` (int, 0-365, 0=infinito)
- `allow_ephemeral_pm` (bool)
- `send_delay` (float) - Secondi tra chunk di risposta
- `max_send_attempts` (int) - Tentativi massimi invio
- `send_retry_delay` (float) - Secondi base tra retry
- `stats_publish_interval` (int) - Secondi tra pubblicazioni stats MQTT

**Nota:** Alcune impostazioni richiedono un riavvio per avere effetto.

#### GET /settings/system

Info sistema.

**Risposta:**
```json
{
  "version": "1.4.0",
  "python_version": "3.11.2",
  "uptime": "2 days, 5 hours",
  "database_size": "2.5 MB",
  "radio_connected": true,
  "radio_port": "/dev/ttyUSB0"
}
```

---

### Backups

#### GET /backups

Lista backup disponibili (superadmin).

**Risposta:**
```json
{
  "items": [
    {
      "name": "meshbbs-backup-auto-20260118-100000.db.gz",
      "path": "/var/lib/meshbbs/backups/...",
      "size": 1048576,
      "size_human": "1.0 MB",
      "created_at": "2026-01-18T10:00:00Z",
      "compressed": true
    }
  ],
  "total": 7
}
```

#### POST /backups

Crea nuovo backup.

**Body:**
```json
{
  "label": "pre-update"
}
```

#### POST /backups/restore

Ripristina da backup.

**Body:**
```json
{
  "backup_name": "meshbbs-backup-auto-20260118-100000.db.gz"
}
```

#### DELETE /backups/{backup_name}

Elimina backup.

#### GET /backups/config

Configurazione backup.

---

## WebSocket

### Connessione

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  // Autenticazione
  ws.send(JSON.stringify({
    type: 'auth',
    token: 'eyJhbGciOiJIUzI1NiIs...'
  }));
};
```

### Eventi

Il server BBS invia automaticamente eventi ai client WebSocket connessi:

**stats_update** - Statistiche aggiornate (ogni 30 secondi)
```json
{
  "type": "stats_update",
  "data": {
    "users": {"total": 151, "active_24h": 24},
    "messages": {"public": {"total": 5420, "today": 46, "last_hour": 8}},
    "radio": {"connected": true, "messages_processed": 1234}
  },
  "timestamp": "2026-01-18T10:30:00Z"
}
```

**system_status** - Stato radio aggiornato (ogni 30 secondi, topic: system)
```json
{
  "type": "system_status",
  "data": {
    "status": "connected",
    "is_connected": true,
    "radio": {"name": "MeshBBS Node", "battery_level": 85},
    "message_count": 1234
  },
  "timestamp": "2026-01-18T10:30:00Z"
}
```

**new_message** - Nuovo messaggio ricevuto dal mesh (topic: messages)
```json
{
  "type": "new_message",
  "data": {
    "id": 5421,
    "area": "generale",
    "sender": "Mario",
    "preview": "Ciao a tutti..."
  }
}
```

**user_activity** - Attività utente
```json
{
  "type": "user_activity",
  "data": {
    "event": "login",
    "user_key": "ABC123...",
    "nickname": "Luigi"
  }
}
```

---

## Codici Errore

| Codice | Descrizione |
|--------|-------------|
| 400 | Richiesta non valida |
| 401 | Non autenticato |
| 403 | Accesso negato |
| 404 | Risorsa non trovata |
| 409 | Conflitto (es. duplicato) |
| 422 | Errore validazione |
| 423 | Account bloccato |
| 429 | Troppe richieste |
| 500 | Errore interno |
| 501 | Non implementato |

### Formato Errore

```json
{
  "error": "Messaggio errore",
  "detail": "Dettagli aggiuntivi",
  "field": "nome_campo"
}
```

---

## Rate Limiting

L'API implementa rate limiting:
- **100 richieste/minuto** per utente autenticato
- **20 richieste/minuto** per IP non autenticato

Headers risposta:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1705574400
```

---

### Delivery Tracking

Il sistema traccia lo stato di consegna dei messaggi inviati attraverso la rete MeshCore.

#### Stati di Consegna

| Stato | Descrizione |
|-------|-------------|
| `pending` | Messaggio in coda per l'invio |
| `sending` | Messaggio in fase di trasmissione |
| `sent` | Messaggio inviato, in attesa di ACK |
| `delivered` | ACK ricevuto dal destinatario |
| `read` | Messaggio letto dal destinatario |
| `failed` | Consegna fallita dopo i tentativi |

#### GET /messages/{message_id}/delivery

Stato di consegna per un messaggio specifico.

**Risposta:**
```json
{
  "id": 1,
  "message_type": "private",
  "message_id": 123,
  "external_id": "mesh_abc123",
  "sender_key": "ABC123...",
  "recipient_key": "DEF456...",
  "state": "delivered",
  "created_at": "2026-01-18T10:30:00Z",
  "sent_at": "2026-01-18T10:30:01Z",
  "delivered_at": "2026-01-18T10:30:05Z",
  "read_at": null,
  "failed_at": null,
  "retry_count": 0,
  "max_retries": 3,
  "error_message": null,
  "ack_hops": 2,
  "ack_rssi": -75,
  "delivery_time_ms": 4000
}
```

#### GET /delivery/pending

Lista messaggi in attesa di consegna.

**Risposta:**
```json
{
  "items": [
    {
      "id": 1,
      "message_type": "private",
      "message_id": 123,
      "state": "pending",
      "created_at": "2026-01-18T10:30:00Z",
      "retry_count": 0
    }
  ],
  "total": 5
}
```

#### GET /delivery/stats

Statistiche di consegna.

**Risposta:**
```json
{
  "pending": 5,
  "sending": 2,
  "sent": 10,
  "delivered": 1234,
  "read": 890,
  "failed": 23
}
```

#### POST /delivery/{delivery_id}/retry

Ritenta la consegna di un messaggio fallito (admin).

**Risposta:**
```json
{
  "id": 1,
  "state": "pending",
  "retry_count": 2,
  "message": "Delivery queued for retry"
}
```

---

### Statistics

#### GET /stats

Statistiche unificate di utilizzo del BBS. Stesso payload pubblicato via MQTT su `meshbbs/stats`.

**Risposta:**
```json
{
  "users": {
    "total": 150,
    "active_24h": 23,
    "active_7d": 89,
    "new_today": 3,
    "banned": 5,
    "muted": 2
  },
  "messages": {
    "public": {
      "total": 5420,
      "today": 45,
      "last_hour": 8,
      "week": 320
    },
    "private": {
      "total": 890,
      "today": 12,
      "unread": 34
    },
    "areas": 8
  },
  "radio": {
    "status": "connected",
    "connected": true,
    "messages_processed": 1234,
    "reconnect_attempts": 0,
    "name": "MeshBBS Node",
    "port": "/dev/ttyUSB0",
    "battery_level": 85,
    "battery_charging": false,
    "uptime_seconds": 86400,
    "last_activity": "2026-01-18T10:30:00Z"
  },
  "delivery": {
    "by_state": {
      "pending": 5,
      "sending": 2,
      "sent": 10,
      "delivered": 1234,
      "read": 890,
      "failed": 23
    },
    "total": 2164,
    "success_rate": 98.2,
    "failed": 23
  },
  "system": {
    "bbs_name": "MeshBBS Italia",
    "uptime_seconds": 86400,
    "db_size_bytes": 2621440,
    "memory": {
      "available": 1073741824,
      "total": 4294967296
    }
  },
  "collected_at": "2026-01-18T10:30:00Z"
}
```

#### GET /stats/health

Health check leggero (senza autenticazione, senza query al database).

**Risposta:**
```json
{
  "status": "ok",
  "radio_connected": true,
  "messages_processed": 1234
}
```

---

## Versioning

L'API è versionata nel path: `/api/v1/...`

Versioni future useranno `/api/v2/...` etc.
