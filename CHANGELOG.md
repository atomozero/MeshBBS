# Changelog

Tutte le modifiche notevoli al progetto MeshCore BBS saranno documentate in questo file.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.4.0] - 2026-01-18

### Aggiunto

#### Web Administration Interface
- **Pannello Admin React completo**
  - Dashboard con statistiche real-time e feed attività
  - Gestione utenti (visualizza, ban, unban, mute, kick, promozioni)
  - Gestione aree messaggi (crea, modifica, elimina)
  - Moderazione messaggi e ricerca
  - Visualizzatore log di sistema con filtri
  - Gestione impostazioni
  - Supporto tema Dark/Light/System
  - Design responsive per dispositivi mobili

#### REST API Backend
- **API FastAPI completa**
  - Autenticazione JWT con refresh token
  - Operazioni CRUD complete per tutte le risorse
  - Supporto paginazione e filtri
  - Documentazione OpenAPI/Swagger
  - 45 test API passati

#### WebSocket per Real-time
- Aggiornamenti statistiche live
- Notifiche nuovi messaggi
- Notifiche attività utenti

#### Integrazione MeshCore Hardware
- **Implementazione completa con meshcore_py**
  - Connessione seriale, BLE e TCP
  - Gestione messaggi privati e canale
  - Fallback automatico a mock se hardware non disponibile
  - 17 test connessione passati

#### Sistema Backup Automatico
- Backup schedulati con intervallo configurabile
- Backup compressi (gzip)
- Rotazione automatica backup
- Backup/restore manuale via API
- Endpoint: `/api/v1/backups`

#### Integrazione MQTT
- Pubblicazione eventi BBS (messaggi, utenti, sistema)
- Sottoscrizione a comandi
- Supporto TLS
- Topic prefix configurabile

#### Deploy Raspberry Pi
- Script installazione automatica (`deploy/install.sh`)
- Configurazione servizi systemd
- Script aggiornamento e disinstallazione
- Guida installazione completa (`docs/INSTALLATION.md`)

### Modificato
- Architettura modulo connessione migliorata
- Gestione errori potenziata
- Logging strutturato

### Corretto
- Formato feed attività dashboard
- Gestione riconnessione WebSocket
- Meccanismo refresh token

---

## [1.3.0] - 2026-01-17

### Aggiunto

#### Sistema Schedulazione Automatica
- **Scheduler per task in background**
  - Esecuzione task a intervalli configurabili
  - Supporto run_on_start per esecuzione immediata
  - Gestione errori con retry automatico
  - Status e statistiche task

- **RetentionScheduler**
  - Esegue pulizia automatica PM e log ogni 24 ore
  - Configurabile: intervallo, giorni retention
  - Integrato con RetentionManager esistente

#### Rate Limiting Anti-Spam
- **Protezione da flood e spam**
  - Intervallo minimo tra comandi (default: 1 secondo)
  - Limite comandi al minuto (default: 30)
  - Blocco temporaneo per abusi (default: 60 secondi)
  - Whitelist automatica per admin

- **Integrazione nel Dispatcher**
  - Controllo rate limit prima dell'esecuzione
  - Messaggi di errore in italiano
  - Logging di violazioni

#### Sistema Notifiche Menzioni
- **Rilevamento @nickname nei messaggi**
  - Pattern: @nickname con 2-20 caratteri
  - Case insensitive
  - Supporto underscore e numeri

- **Notifiche in /inbox**
  - Menzioni visualizzate nell'inbox
  - Link diretto al messaggio (/read <id>)
  - Scompaiono dopo la lettura
  - Limite 50 menzioni per utente

- **Integrazione comandi**
  - `/post` processa menzioni e notifica utenti
  - `/reply` processa menzioni nelle risposte
  - Conferma utenti notificati nella risposta

#### Nuovi Moduli
- `src/bbs/scheduler.py` - Sistema schedulazione
- `src/bbs/rate_limiter.py` - Rate limiting
- `src/bbs/mentions.py` - Sistema menzioni

#### Test
- `test_scheduler.py`: 23 test per schedulazione
- `test_rate_limiter.py`: 24 test per rate limiting
- `test_mentions.py`: 32 test per menzioni

**Totale: 437 test passati**

---

## [1.2.0] - 2026-01-17

### Aggiunto

#### Privacy e GDPR Compliance
- **Retention Policy automatica**
  - Configurabile via environment: `BBS_PM_RETENTION_DAYS` (default 30)
  - Configurabile via environment: `BBS_LOG_RETENTION_DAYS` (default 90)
  - Pulizia automatica di PM e log vecchi

- **Messaggi Privati Effimeri** (`/msg!`)
  - Nuovo comando `/msg! <utente> <messaggio>` per PM non salvati
  - I messaggi esistono solo in memoria fino alla lettura
  - Scompaiono dopo che il destinatario li legge
  - Alias: `/pm!`, `/dm!`

- **Supporto SQLCipher** (opzionale)
  - Crittografia database a riposo
  - Configurabile via `BBS_DATABASE_KEY`
  - Protegge i dati se la SD card viene rubata

- **Nuovi Comandi Privacy**
  - `/gdpr` - Mostra informazioni privacy e retention policy
  - `/mydata` - Mostra i propri dati salvati nel BBS
  - `/cleanup` (admin) - Esegue pulizia manuale dei dati vecchi
  - `/cleanup --dry-run` - Preview senza eliminare

#### Modifiche
- Inbox ora mostra PM effimeri separatamente
- Parser comandi supporta `!` per comandi effimeri

#### Configurazione
Nuove variabili environment:
```
BBS_PM_RETENTION_DAYS=30      # Giorni di retention PM (0=infinito)
BBS_LOG_RETENTION_DAYS=90     # Giorni di retention log (0=infinito)
BBS_DATABASE_KEY=             # Chiave SQLCipher (vuoto=no crittografia)
BBS_ALLOW_EPHEMERAL_PM=true   # Abilita /msg!
```

#### Test
- `test_privacy.py`: 24 nuovi test per funzionalità privacy

**Totale: 358 test passati**

---

## [1.1.0] - 2026-01-17

### Aggiunto

#### Comandi Utility
- Nuovo comando `/delpm <id>` per eliminare messaggi privati
  - Permette di eliminare PM ricevuti o inviati
  - Alias: `/deletepm`, `/rmpm`
- Nuovo comando `/clear` per marcare tutti i PM come letti
  - Pulisce l'inbox senza eliminare i messaggi
  - Alias: `/readall`, `/markread`
- Nuovo comando `/stats` per visualizzare statistiche BBS
  - Mostra: utenti totali/attivi, messaggi, aree, PM
  - Utenti attivi = ultimi 24h
  - Alias: `/statistics`, `/stat`
- Nuovo comando `/info` per informazioni sul BBS
  - Mostra: versione, utenti, aree, protocollo, licenza
  - Alias: `/about`, `/version`
- Nuovo comando `/whois <utente>` per info su un utente
  - Mostra: profilo, ruolo, data registrazione, ultimo accesso
  - Mostra: conteggio messaggi, stato (banned/muted/kicked)
  - Cerca per nickname o chiave pubblica
  - Alias: `/user`, `/profile`

#### Test
- `test_utility_commands.py`: 47 nuovi test per comandi utility

**Totale: 334 test passati**

---

## [0.1.0] - 2026-01-17

### Aggiunto

#### Struttura Progetto
- Creata struttura directory completa del progetto
- Configurato virtual environment Python
- Creato `requirements.txt` con dipendenze
- Creato `pytest.ini` per configurazione test
- Aggiunti file `LICENSE` (MIT) e `README.md`

#### Modulo Database (`src/bbs/models/`)
- `base.py`: Configurazione SQLAlchemy, session management, init_database()
- `user.py`: Modello User con public_key come identificatore
- `area.py`: Modello Area per aree di discussione
- `message.py`: Modello Message con supporto threading
- `private_message.py`: Modello PrivateMessage per messaggi diretti
- `activity_log.py`: Modello ActivityLog per audit trail

#### Repository Pattern (`src/bbs/repositories/`)
- `base_repository.py`: Repository generico con operazioni CRUD
- `user_repository.py`: Repository per gestione utenti
- `area_repository.py`: Repository per gestione aree
- `message_repository.py`: Repository per gestione messaggi

#### Sistema Comandi (`src/bbs/commands/`)
- `parser.py`: Parser comandi con supporto argomenti quotati
- `dispatcher.py`: Dispatcher per routing comandi
- `base.py`: Classi base Command, CommandContext, CommandResult, CommandRegistry
- Comandi implementati:
  - `/help` - Mostra aiuto comandi
  - `/areas` - Lista aree disponibili
  - `/list [n]` - Lista ultimi messaggi
  - `/read <id>` - Legge un messaggio
  - `/post <messaggio>` - Pubblica un messaggio
  - `/nick <nome>` - Imposta nickname

#### Modulo MeshCore (`src/meshcore/`)
- `protocol.py`: Definizioni protocollo (PacketType, NodeType)
- `messages.py`: Dataclass per Message, Advert, Ack
- `connection.py`:
  - `BaseMeshCoreConnection`: Interfaccia astratta
  - `MeshCoreConnection`: Implementazione (placeholder per hardware)
  - `MockMeshCoreConnection`: Mock per sviluppo/test senza hardware

#### Core BBS (`src/bbs/`)
- `core.py`: Classe BBSCore con:
  - Gestione ciclo di vita (start/stop)
  - Main loop per ricezione messaggi
  - Dispatch comandi
  - Advertisement periodico

#### Utilities (`src/utils/`)
- `config.py`: Configurazione con dataclass Config
- `logger.py`: Setup logging con RotatingFileHandler

#### Entry Point
- `src/main.py`: CLI con argparse per avvio BBS

#### Test Suite (`tests/`)
- `conftest.py`: Fixtures pytest (db_session, mock_connection, etc.)
- `test_parser.py`: 11 test per command parser
- `test_commands.py`: 15 test per comandi BBS
- `test_models.py`: 14 test per modelli database
- `test_connection.py`: 15 test per connessione mock
- `test_core.py`: 8 test per BBSCore

**Totale: 66 test passati**

### Note Tecniche
- Database: SQLite con WAL mode per performance
- Architettura: Async con asyncio
- Pattern: Repository, Command, Dependency Injection
- Mock connection permette sviluppo senza hardware

### Task Documents Aggiornati
- I documenti in `/tasks/` contengono analisi e task dettagliati per ogni componente MVP

---

## [1.0.0] - 2026-01-17

### Aggiunto

#### Comandi Gestione Aree (Admin)
- Nuovo comando `/newarea <nome> [descrizione]` per creare aree
  - Validazione nome: 2-32 caratteri, lettere/numeri/underscore/trattino
  - Deve iniziare con una lettera
  - Case insensitive (convertito in minuscolo)
  - Alias: `/createarea`, `/addarea`
- Nuovo comando `/delarea <nome>` per eliminare aree
  - Elimina anche tutti i messaggi dell'area
  - Aree protette: "generale" e "general" non eliminabili
  - Mostra conteggio messaggi eliminati
  - Alias: `/deletearea`, `/rmarea`
- Nuovo comando `/editarea <nome> <proprietà> [valore]` per modificare aree
  - Proprietà `desc`: cambia descrizione
  - Proprietà `readonly`: abilita/disabilita sola lettura (on/off)
  - Proprietà `public`: mostra/nascondi area (on/off)
  - Alias: `/modarea`
- Nuovo comando `/listareas` per vista admin di tutte le aree
  - Mostra flags: RO (read-only), HIDDEN (nascosta)
  - Mostra conteggio messaggi per area
  - Mostra totale aree

#### Activity Log
- Aggiunto evento `AREA_MODIFIED` per tracciare modifiche aree

#### Test
- `test_area_admin_commands.py`: 38 nuovi test per gestione aree

**Totale: 287 test passati**

---

## [0.9.0] - 2026-01-17

### Aggiunto

#### Comando /kick per Espulsione Temporanea
- Nuovo comando `/kick <utente> [minuti] [motivo]` per espellere temporaneamente
  - Durata default: 30 minuti
  - Durata massima: 1440 minuti (24 ore)
  - Solo admin possono usare questo comando
  - Protezioni: non può espellere se stessi, admin o utenti già bannati
- Nuovo comando `/unkick <utente>` per rimuovere espulsione
- Differenza rispetto ad altre sanzioni:
  - **Ban**: Permanente, blocca completamente l'accesso
  - **Kick**: Temporaneo, blocca l'accesso per durata specificata
  - **Mute**: Permanente (fino a unmute), blocca solo la scrittura

#### Sistema Kick Temporaneo
- Aggiunto campo `kicked_until` (DateTime) al modello User
- Aggiunto campo `kick_reason` al modello User
- Proprietà `is_kicked` verifica se il kick è ancora attivo
- Proprietà `kick_remaining_minutes` mostra minuti rimanenti
- Il kick scade automaticamente dopo il tempo specificato
- Aggiornato dispatcher per bloccare utenti kicked

#### Nuovi Eventi ActivityLog
- `USER_KICKED` - Registra espulsione con durata
- `USER_UNKICKED` - Registra rimozione espulsione

#### Test
- `test_kick_command.py`: 30 nuovi test per comando /kick

**Totale: 249 test passati**

---

## [0.8.0] - 2026-01-17

### Aggiunto

#### Comandi Gestione Staff
- Nuovo comando `/promote <utente> [admin]` per promuovere utenti
  - `/promote Mario` - promuove a moderatore
  - `/promote Mario admin` - promuove ad admin
  - Solo admin possono usare questo comando
  - Protezioni: non può promuovere se stessi o utenti bannati
- Nuovo comando `/demote <utente>` per degradare utenti
  - Admin diventa moderatore
  - Moderatore diventa utente normale
  - Non può degradare se stessi
- Nuovo comando `/staff` per visualizzare lo staff
  - Mostra admin con indicatore `[A]`
  - Mostra moderatori con indicatore `[M]`
  - Disponibile a tutti gli utenti
  - Alias: `/mods`, `/admins`

#### Gerarchia Ruoli
- Aggiunta proprietà `role_display` al modello User
- Gerarchia: Admin > Moderatore > Utente
- Gli admin sono automaticamente anche moderatori
- Degradare un admin lo rende moderatore (mantiene privilegi mod)

#### Nuovi Eventi ActivityLog
- `USER_PROMOTED` - Registra promozioni
- `USER_DEMOTED` - Registra degradazioni

#### Test
- `test_promote_commands.py`: 31 nuovi test per gestione staff

**Totale: 219 test passati**

---

## [0.7.0] - 2026-01-17

### Aggiunto

#### Comandi Admin per Moderazione
- Nuovo comando `/ban <utente> [motivo]` per bannare utenti
  - Solo admin possono usare questo comando
  - Cerca utente per nickname o chiave pubblica (8+ char)
  - Supporta motivo opzionale
  - Protezioni: non può bannare se stessi o altri admin
- Nuovo comando `/unban <utente>` per rimuovere ban
- Nuovo comando `/mute <utente> [motivo]` per silenziare utenti
  - Utente silenziato può leggere ma non scrivere
  - Alias: `/silence`
- Nuovo comando `/unmute <utente>` per rimuovere silenziamento
  - Alias: `/unsilence`

#### Sistema Mute
- Aggiunto campo `is_muted` al modello User
- Utenti silenziati non possono:
  - Pubblicare messaggi (`/post`)
  - Rispondere a messaggi (`/reply`)
  - Inviare messaggi privati (`/msg`)
- Utenti silenziati possono comunque:
  - Leggere messaggi e aree
  - Visualizzare la propria inbox

#### Nuovi Eventi ActivityLog
- `USER_MUTED` - Registra quando un utente viene silenziato
- `USER_UNMUTED` - Registra quando un utente viene riabilitato

#### Test
- `test_admin_commands.py`: 33 nuovi test per comandi admin

**Totale: 188 test passati**

---

## [0.6.0] - 2026-01-17

### Aggiunto

#### Comando /search per Ricerca Messaggi
- Nuovo comando `/search [#area] <termine>` per ricerca nei messaggi
- Ricerca case-insensitive nel contenuto dei messaggi
- Supporta ricerca globale o in area specifica
- Alias: `/find`, `/s`
- Funzionalità:
  - Mostra anteprima del messaggio con termine evidenziato
  - Mostra autore, area e ID messaggio
  - Suggerimento per usare /read per leggere messaggio completo
  - Limite risultati configurabile (default 5, max 10)
  - Validazione lunghezza minima termine (2 caratteri)

#### Test
- `test_search_command.py`: 17 nuovi test per comando /search

**Totale: 155 test passati**

---

## [0.5.0] - 2026-01-17

### Aggiunto

#### Supporto Multi-Area per /post
- Comando `/post` ora supporta specificare l'area di destinazione
- Sintassi: `/post [#area] <messaggio>`
- Formati supportati:
  - `/post Ciao!` - pubblica nell'area default (generale)
  - `/post #tech Domanda` - pubblica nell'area tech
  - `/post tech Domanda` - pubblica nell'area tech (se esiste)
- Validazione area: verifica esistenza e permessi di scrittura
- Mostra aree disponibili se area non trovata
- Risposta include nome area se diversa da default

#### Test
- `test_post_multiarea.py`: 15 nuovi test per multi-area

**Totale: 138 test passati**

---

## [0.4.0] - 2026-01-17

### Aggiunto

#### Sistema Threading Messaggi
- Comando `/reply <id> <messaggio>` per risposte a messaggi
  - Crea conversazioni thread nei messaggi pubblici
  - Risposta pubblicata nella stessa area del messaggio originale
  - Alias: `/re`
  - Limite 200 caratteri
- Comando `/read` migliorato:
  - Mostra info parent per messaggi che sono risposte (es. "re: #42 Mario")
  - Mostra conteggio risposte se presenti
  - Aggiunto suggerimento per risposta rapida

#### Test
- `test_reply_command.py`: 17 nuovi test per threading
  - Test comando /reply
  - Test visualizzazione thread in /read
  - Test proprietà Message (is_reply, reply_count, get_thread)

**Totale: 123 test passati**

---

## [0.3.0] - 2026-01-17

### Aggiunto

#### Sistema Messaggi Privati
- Nuovo repository `private_message_repository.py` per gestione messaggi privati
- Comando `/msg <utente> <messaggio>` per inviare messaggi privati
  - Ricerca utente per nickname o chiave pubblica (min 8 char)
  - Alias: `/pm`, `/dm`, `/tell`
  - Limite 200 caratteri per messaggio
  - Protezione: no messaggi a se stessi o utenti bannati
- Comando `/inbox [n]` per visualizzare messaggi ricevuti
  - Mostra conteggio non letti
  - Marcatore `*` per messaggi non letti
  - Alias: `/mail`, `/pms`
- Comando `/readpm <id>` per leggere un messaggio privato
  - Segna automaticamente come letto
  - Mostra suggerimento per risposta
  - Alias: `/rpm`, `/viewpm`

#### Repository
- `private_message_repository.py`: Gestione completa messaggi privati
  - `send_message()`: Invio con validazione destinatario
  - `get_inbox()`: Lista messaggi ricevuti con filtro unread
  - `get_sent()`: Lista messaggi inviati
  - `get_conversation()`: Conversazione tra due utenti
  - `get_unread_count()`: Conteggio non letti
  - `mark_as_read()`: Marca singolo messaggio come letto
  - `mark_conversation_as_read()`: Marca intera conversazione

#### Test
- `test_private_messages.py`: 26 nuovi test per sistema messaggi privati

**Totale: 106 test passati**

---

## [0.2.0] - 2026-01-17

### Aggiunto

#### Comando `/who`
- Nuovo comando per visualizzare utenti attivi
- Supporta argomento opzionale ore (es. `/who 12`)
- Mostra indicatori ruolo: `[A]` admin, `[M]` moderatore
- Alias: `/users`, `/online`
- Esclude utenti bannati dalla lista
- Limite massimo 168 ore (1 settimana)

#### Test
- `test_who_command.py`: 14 nuovi test per comando /who

**Totale: 80 test passati**

---

## [Unreleased]

### Da Fare
- Implementare connessione reale via meshcore_py
- Sistema notifiche per menzioni e risposte

---

## [1.4.0-web] - 2026-01-18

### Aggiunto (Web Interface)

#### Dark Mode Completo
- **ThemeContext** - Context React per gestione tema
  - Supporto tre modalità: light, dark, system
  - Rilevamento automatico preferenze sistema (`prefers-color-scheme`)
  - Persistenza localStorage (`meshbbs-theme`)
  - Sincronizzazione cross-tab via StorageEvent
  - Hook `useTheme()` per accesso a tema e funzioni

- **Componenti UI Theme**
  - `ThemeToggle` - Pulsante toggle rapido light/dark
  - `ThemeSelector` - Selettore segmentato con opzioni Light/Dark/System
  - Icone Lucide: Sun, Moon, Monitor

- **Integrazione Header**
  - ThemeToggle aggiunto alla barra superiore
  - Cambio tema accessibile da qualsiasi pagina

#### Error Handling
- **ErrorBoundary** - Class component per catturare errori React
  - Mostra UI di fallback user-friendly in caso di crash
  - Pulsanti: Try Again, Reload Page, Go Home
  - Dettagli errore visibili solo in development mode
  - Supporto callback `onError` per logging esterno
  - Supporto fallback personalizzato

- **ErrorFallback** - Componente per errori inline
  - Stile compatto per errori in componenti specifici
  - Pulsante Retry per recupero errori

#### Accessibilit\u00e0 (ARIA)
- **Button** - Miglioramenti accessibilit\u00e0
  - `aria-disabled` e `aria-busy` per stati loading
  - `aria-hidden` per icone decorative
  - Screen reader text per stato loading

- **Input** - Miglioramenti accessibilit\u00e0
  - `aria-invalid` per campi con errore
  - `aria-describedby` per collegare hint ed errori
  - ID unici generati automaticamente con `useId`
  - `role="alert"` per messaggi di errore

- **Modal** - Miglioramenti accessibilit\u00e0
  - Focus trap per navigazione con Tab
  - Gestione focus al mount/unmount
  - Chiusura con tasto Escape
  - `aria-labelledby` e `aria-describedby`
  - Prevenzione scroll body quando aperto

#### Lazy Loading
- **Code Splitting** per tutte le pagine
  - LoginPage, DashboardPage, UsersPage, AreasPage, MessagesPage, LogsPage, SettingsPage
  - Bundle iniziale ridotto da 145KB a 76KB
  - Chunk separati per ogni pagina (7-12KB ciascuno)
  - Loading fallback con Suspense
  - Migliore esperienza utente al primo caricamento

#### Test
- `useTheme.test.tsx`: 10 test per ThemeContext
- `ThemeToggle.test.tsx`: 12 test per componenti theme
- `ErrorBoundary.test.tsx`: 11 test per error handling

**Totale test frontend: 72 test passati**
