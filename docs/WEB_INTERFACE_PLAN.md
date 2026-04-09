# MeshCore BBS - Piano Sviluppo Interfaccia Web di Gestione

**Versione**: 1.0
**Data**: 2026-01-17
**Target Release**: v2.0.0

---

## Executive Summary

Questo documento definisce il piano di sviluppo per l'interfaccia web di amministrazione di MeshCore BBS. L'obiettivo è creare un pannello di controllo professionale, responsive e sicuro che permetta la gestione completa del sistema BBS da qualsiasi dispositivo.

### Obiettivi Principali

1. **Gestione centralizzata** - Dashboard unificata per tutte le operazioni amministrative
2. **Responsive design** - Esperienza ottimale su desktop, tablet e smartphone
3. **Real-time monitoring** - Visualizzazione live di statistiche e log
4. **Sicurezza enterprise** - Autenticazione robusta e audit trail

### Stack Tecnologico

| Componente | Tecnologia | Motivazione |
|------------|------------|-------------|
| Backend API | FastAPI (Python) | Async, OpenAPI docs, validazione Pydantic |
| Frontend | React 18 + TypeScript | Type safety, ecosystem maturo, componentizzazione |
| UI Framework | TailwindCSS + Headless UI | Design system flessibile, accessibilità |
| State Management | TanStack Query | Caching, sync server state, real-time |
| Charts | Recharts | Leggero, React-native, responsive |
| Build Tool | Vite | Fast HMR, ottimizzato per produzione |
| Auth | JWT + httpOnly cookies | Sicuro, stateless, refresh token |

---

## Architettura Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                        Raspberry Pi                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐     ┌─────────────────────────────────────┐   │
│  │  MeshCore   │     │           Web Interface              │   │
│  │    BBS      │     │                                      │   │
│  │             │     │  ┌─────────────┐  ┌──────────────┐  │   │
│  │  - Core     │◄────┼──│  FastAPI    │  │   React SPA  │  │   │
│  │  - Commands │     │  │  Backend    │  │   Frontend   │  │   │
│  │  - Models   │     │  │  :8080/api  │  │   :8080/     │  │   │
│  │             │     │  └──────┬──────┘  └──────────────┘  │   │
│  └──────┬──────┘     │         │                            │   │
│         │            │         │ WebSocket                   │   │
│         │            │         ▼                            │   │
│  ┌──────▼──────┐     │  ┌─────────────┐                    │   │
│  │   SQLite    │◄────┼──│  Shared DB  │                    │   │
│  │   Database  │     │  │  Access     │                    │   │
│  └─────────────┘     │  └─────────────┘                    │   │
│                      └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Principi Architetturali

1. **Separation of Concerns** - API REST per operazioni CRUD, WebSocket per real-time
2. **Shared Database** - Accesso diretto al DB SQLite esistente
3. **Single Port** - Frontend e API serviti dalla stessa porta (reverse proxy interno)
4. **Stateless API** - JWT per autenticazione, nessuna sessione server-side
5. **Progressive Enhancement** - Funziona senza JS per operazioni critiche

---

## Fasi di Sviluppo

### Fase 1: Infrastruttura Backend (Sprint 1-2)

#### 1.1 Setup FastAPI Server

**File da creare:**
```
src/
└── web/
    ├── __init__.py
    ├── main.py              # FastAPI app entry point
    ├── config.py            # Web server configuration
    ├── dependencies.py      # Dependency injection
    ├── auth/
    │   ├── __init__.py
    │   ├── models.py        # Admin user model
    │   ├── jwt.py           # JWT utilities
    │   ├── middleware.py    # Auth middleware
    │   └── routes.py        # Login/logout endpoints
    ├── api/
    │   ├── __init__.py
    │   ├── v1/
    │   │   ├── __init__.py
    │   │   ├── router.py    # API v1 router
    │   │   ├── dashboard.py # Dashboard endpoints
    │   │   ├── users.py     # User management
    │   │   ├── areas.py     # Area management
    │   │   ├── messages.py  # Message management
    │   │   ├── moderation.py# Ban/mute/kick
    │   │   ├── settings.py  # System settings
    │   │   └── logs.py      # Activity logs
    │   └── websocket.py     # Real-time updates
    └── schemas/
        ├── __init__.py
        ├── auth.py          # Auth request/response
        ├── user.py          # User schemas
        ├── area.py          # Area schemas
        ├── message.py       # Message schemas
        ├── stats.py         # Statistics schemas
        └── common.py        # Pagination, errors
```

**Endpoints API v1:**

| Method | Endpoint | Descrizione |
|--------|----------|-------------|
| POST | `/api/v1/auth/login` | Login admin |
| POST | `/api/v1/auth/logout` | Logout |
| POST | `/api/v1/auth/refresh` | Refresh token |
| GET | `/api/v1/auth/me` | Current admin info |
| GET | `/api/v1/dashboard/stats` | Statistiche generali |
| GET | `/api/v1/dashboard/activity` | Attività recente |
| GET | `/api/v1/users` | Lista utenti (paginata) |
| GET | `/api/v1/users/{key}` | Dettaglio utente |
| PATCH | `/api/v1/users/{key}` | Modifica utente |
| POST | `/api/v1/users/{key}/ban` | Ban utente |
| POST | `/api/v1/users/{key}/unban` | Unban utente |
| POST | `/api/v1/users/{key}/mute` | Mute utente |
| POST | `/api/v1/users/{key}/unmute` | Unmute utente |
| POST | `/api/v1/users/{key}/kick` | Kick utente |
| POST | `/api/v1/users/{key}/promote` | Promuovi utente |
| POST | `/api/v1/users/{key}/demote` | Degrada utente |
| GET | `/api/v1/areas` | Lista aree |
| POST | `/api/v1/areas` | Crea area |
| PATCH | `/api/v1/areas/{name}` | Modifica area |
| DELETE | `/api/v1/areas/{name}` | Elimina area |
| GET | `/api/v1/messages` | Lista messaggi |
| DELETE | `/api/v1/messages/{id}` | Elimina messaggio |
| GET | `/api/v1/logs` | Activity logs |
| GET | `/api/v1/settings` | Impostazioni sistema |
| PATCH | `/api/v1/settings` | Aggiorna impostazioni |
| POST | `/api/v1/maintenance/cleanup` | Esegui cleanup |
| GET | `/api/v1/system/status` | Stato sistema |
| WS | `/api/v1/ws` | WebSocket real-time |

#### 1.2 Sistema Autenticazione

**Modello Admin:**
```python
class AdminUser(Base):
    __tablename__ = "admin_users"

    id: int                    # Primary key
    username: str              # Unique username
    password_hash: str         # Argon2 hash
    display_name: str          # Nome visualizzato
    email: Optional[str]       # Email opzionale
    is_active: bool            # Account attivo
    is_superadmin: bool        # Può gestire altri admin
    created_at: datetime       # Data creazione
    last_login: datetime       # Ultimo login
    failed_attempts: int       # Tentativi falliti
    locked_until: datetime     # Blocco temporaneo
```

**Sicurezza:**
- Password hash con Argon2id
- JWT con scadenza 15 minuti
- Refresh token in httpOnly cookie (7 giorni)
- Rate limiting su login (5 tentativi, blocco 15 min)
- Audit log per tutte le azioni admin

#### 1.3 Database Migration

Aggiungere tabella `admin_users` al database esistente tramite Alembic migration.

**Deliverables Fase 1:**
- [x] FastAPI server funzionante
- [x] Sistema autenticazione JWT completo
- [x] API CRUD per tutte le entità
- [x] WebSocket per eventi real-time
- [x] OpenAPI documentation (`/api/docs`)
- [x] Test API (pytest + httpx) - 45 test passati

**Status Fase 1: COMPLETATA (17 Gennaio 2026)**

File implementati:
```
src/web/
├── __init__.py              # Module init, version
├── main.py                  # FastAPI app, CORS, error handlers
├── config.py                # WebConfig dataclass
├── dependencies.py          # get_db, get_current_admin
├── auth/
│   ├── __init__.py
│   ├── models.py            # AdminUser model, AdminUserRepository
│   ├── password.py          # Argon2id/PBKDF2 hashing
│   ├── jwt.py               # JWT token utilities
│   └── routes.py            # Auth endpoints (login, logout, refresh, CRUD)
├── api/
│   ├── __init__.py
│   └── v1/
│       ├── __init__.py
│       ├── router.py        # Combined v1 router
│       ├── dashboard.py     # Stats, activity, charts
│       ├── users.py         # User management, moderation
│       ├── areas.py         # Area CRUD, stats
│       ├── messages.py      # Public/private messages
│       ├── logs.py          # Activity logs, export
│       └── settings.py      # Settings, system, maintenance
├── schemas/
│   ├── __init__.py
│   ├── common.py            # Pagination, errors, bulk actions
│   ├── user.py              # User schemas
│   ├── area.py              # Area schemas
│   ├── message.py           # Message schemas
│   └── stats.py             # Dashboard stats schemas
└── websocket/
    ├── __init__.py
    ├── manager.py           # ConnectionManager, broadcasting
    └── routes.py            # WebSocket endpoint
```

---

### Fase 2: Frontend Foundation (Sprint 3-4)

#### 2.1 Setup Progetto React

**Struttura directory:**
```
web/
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
├── index.html
├── public/
│   ├── favicon.ico
│   └── logo.svg
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── index.css              # Tailwind imports
    ├── api/
    │   ├── client.ts          # Axios/fetch wrapper
    │   ├── auth.ts            # Auth API calls
    │   ├── users.ts           # Users API
    │   ├── areas.ts           # Areas API
    │   ├── messages.ts        # Messages API
    │   └── websocket.ts       # WebSocket client
    ├── components/
    │   ├── ui/                # Componenti base
    │   │   ├── Button.tsx
    │   │   ├── Input.tsx
    │   │   ├── Select.tsx
    │   │   ├── Modal.tsx
    │   │   ├── Table.tsx
    │   │   ├── Card.tsx
    │   │   ├── Badge.tsx
    │   │   ├── Alert.tsx
    │   │   ├── Spinner.tsx
    │   │   └── Toast.tsx
    │   ├── layout/
    │   │   ├── Sidebar.tsx
    │   │   ├── Header.tsx
    │   │   ├── Footer.tsx
    │   │   └── MobileNav.tsx
    │   ├── charts/
    │   │   ├── ActivityChart.tsx
    │   │   ├── UsersChart.tsx
    │   │   └── MessagesChart.tsx
    │   └── features/
    │       ├── auth/
    │       ├── dashboard/
    │       ├── users/
    │       ├── areas/
    │       ├── messages/
    │       └── settings/
    ├── hooks/
    │   ├── useAuth.ts
    │   ├── useWebSocket.ts
    │   ├── useToast.ts
    │   └── useMediaQuery.ts
    ├── contexts/
    │   ├── AuthContext.tsx
    │   └── ThemeContext.tsx
    ├── pages/
    │   ├── Login.tsx
    │   ├── Dashboard.tsx
    │   ├── Users.tsx
    │   ├── UserDetail.tsx
    │   ├── Areas.tsx
    │   ├── Messages.tsx
    │   ├── Logs.tsx
    │   ├── Settings.tsx
    │   └── NotFound.tsx
    ├── routes/
    │   └── index.tsx
    ├── utils/
    │   ├── formatters.ts
    │   ├── validators.ts
    │   └── constants.ts
    └── types/
        ├── api.ts
        ├── user.ts
        ├── area.ts
        └── message.ts
```

#### 2.2 Design System

**Palette Colori Corporate:**
```css
:root {
  /* Primary - Blue professionale */
  --primary-50: #eff6ff;
  --primary-100: #dbeafe;
  --primary-500: #3b82f6;
  --primary-600: #2563eb;
  --primary-700: #1d4ed8;

  /* Neutral - Grigi */
  --neutral-50: #f9fafb;
  --neutral-100: #f3f4f6;
  --neutral-200: #e5e7eb;
  --neutral-500: #6b7280;
  --neutral-700: #374151;
  --neutral-900: #111827;

  /* Semantic */
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;
  --info: #3b82f6;
}
```

**Typography:**
- Font: Inter (Google Fonts)
- Headings: Semi-bold (600)
- Body: Regular (400)
- Scale: 12/14/16/18/20/24/30/36px

**Breakpoints Responsive:**
```javascript
screens: {
  'sm': '640px',   // Mobile landscape
  'md': '768px',   // Tablet
  'lg': '1024px',  // Desktop
  'xl': '1280px',  // Large desktop
}
```

#### 2.3 Componenti UI Core

**Button Component:**
```tsx
interface ButtonProps {
  variant: 'primary' | 'secondary' | 'danger' | 'ghost';
  size: 'sm' | 'md' | 'lg';
  loading?: boolean;
  disabled?: boolean;
  fullWidth?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}
```

**Table Component:**
```tsx
interface TableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  loading?: boolean;
  pagination?: PaginationState;
  sorting?: SortingState;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
  stickyHeader?: boolean;
}
```

**Deliverables Fase 2:**
- [x] Progetto React + Vite configurato
- [x] Design system completo (colori, typography, spacing)
- [x] Componenti UI base (20+ componenti)
- [x] Layout responsive (sidebar, header, mobile nav)
- [x] Sistema routing
- [x] API client con interceptors
- [x] Gestione errori centralizzata

**Status Fase 2: COMPLETATA (17 Gennaio 2026)**

File implementati:
```
web/
├── package.json              # Dipendenze e scripts
├── vite.config.ts            # Config Vite con proxy e test
├── tailwind.config.js        # Design system TailwindCSS
├── tsconfig.json             # TypeScript config
├── index.html                # Entry HTML
├── public/
│   └── logo.svg              # Logo MeshBBS
└── src/
    ├── main.tsx              # Entry point React
    ├── App.tsx               # Router e providers
    ├── index.css             # Styles Tailwind + custom
    ├── vite-env.d.ts         # Vite types
    ├── api/
    │   ├── index.ts          # API exports
    │   ├── client.ts         # Axios client, interceptors
    │   ├── auth.ts           # Auth API
    │   ├── dashboard.ts      # Dashboard API
    │   ├── users.ts          # Users API
    │   ├── areas.ts          # Areas API
    │   ├── messages.ts       # Messages API
    │   ├── logs.ts           # Logs API
    │   ├── settings.ts       # Settings API
    │   └── websocket.ts      # WebSocket client
    ├── components/
    │   ├── ui/
    │   │   ├── index.ts      # UI exports
    │   │   ├── Button.tsx    # Button component
    │   │   ├── Input.tsx     # Input component
    │   │   ├── Textarea.tsx  # Textarea component
    │   │   ├── Select.tsx    # Select component
    │   │   ├── Checkbox.tsx  # Checkbox component
    │   │   ├── Switch.tsx    # Toggle switch
    │   │   ├── Card.tsx      # Card components
    │   │   ├── Badge.tsx     # Badge + StatusBadge + RoleBadge
    │   │   ├── Modal.tsx     # Modal + ConfirmModal
    │   │   ├── Table.tsx     # Table components
    │   │   ├── Pagination.tsx# Pagination
    │   │   ├── Spinner.tsx   # Loading spinners
    │   │   ├── Alert.tsx     # Alert component
    │   │   ├── Toast.tsx     # Toast system
    │   │   ├── Dropdown.tsx  # Dropdown menu
    │   │   └── EmptyState.tsx# Empty state
    │   └── layout/
    │       ├── index.ts      # Layout exports
    │       ├── Sidebar.tsx   # Desktop sidebar
    │       ├── Header.tsx    # Header with status
    │       ├── MobileNav.tsx # Mobile drawer nav
    │       └── MainLayout.tsx# Main layout wrapper
    ├── contexts/
    │   ├── index.ts          # Context exports
    │   ├── AuthContext.tsx   # Auth state management
    │   └── WebSocketContext.tsx # WebSocket state
    ├── pages/
    │   ├── index.ts          # Pages exports
    │   ├── LoginPage.tsx     # Login page
    │   ├── DashboardPage.tsx # Dashboard with charts
    │   ├── UsersPage.tsx     # User management
    │   ├── AreasPage.tsx     # Areas CRUD
    │   ├── MessagesPage.tsx  # Messages management
    │   ├── LogsPage.tsx      # Activity logs
    │   └── SettingsPage.tsx  # System settings
    ├── types/
    │   └── index.ts          # TypeScript types
    └── __tests__/
        ├── setup.ts          # Test setup
        ├── components/       # Component tests (4 files)
        ├── api/              # API tests (1 file)
        └── hooks/            # Hook tests (1 file)
```

**Test Results:**
- 39 test passati (6 file di test)
- Componenti UI testati: Button, Input, Badge, Modal
- API client testato: token management
- Hook testato: useAuth

**Build Output:**
- dist/index.html (1.20 KB)
- dist/assets/index.css (35.93 KB gzipped: 5.94 KB)
- dist/assets/index.js (137.82 KB gzipped: 36.79 KB)
- dist/assets/vendor.js (164.76 KB gzipped: 53.80 KB)
- dist/assets/charts.js (383.32 KB gzipped: 105.44 KB)
- dist/assets/query.js (28.74 KB gzipped: 9.01 KB)

---

### Fase 3: Dashboard & Monitoring (Sprint 5-6)

#### 3.1 Dashboard Page

**Layout Desktop:**
```
┌─────────────────────────────────────────────────────────────────┐
│  Header: Logo | Search | Notifications | Profile               │
├─────────┬───────────────────────────────────────────────────────┤
│         │                                                        │
│         │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │
│  Side   │  │ Users   │ │Messages │ │ Areas   │ │ Active  │     │
│  bar    │  │  142    │ │  1,234  │ │   8     │ │   23    │     │
│         │  └─────────┘ └─────────┘ └─────────┘ └─────────┘     │
│  - Dash │                                                        │
│  - Users│  ┌────────────────────────────────────────────────┐   │
│  - Areas│  │                                                 │   │
│  - Msgs │  │          Activity Chart (7 days)               │   │
│  - Logs │  │                                                 │   │
│  - Sett │  └────────────────────────────────────────────────┘   │
│         │                                                        │
│         │  ┌──────────────────┐  ┌──────────────────────────┐   │
│         │  │  Recent Activity │  │     System Status        │   │
│         │  │  - User joined   │  │  Radio: Connected ●      │   │
│         │  │  - Message posted│  │  DB: 45MB / 1GB          │   │
│         │  │  - Area created  │  │  Uptime: 3d 14h          │   │
│         │  └──────────────────┘  └──────────────────────────┘   │
│         │                                                        │
└─────────┴───────────────────────────────────────────────────────┘
```

**Layout Mobile:**
```
┌─────────────────────┐
│ ☰  MeshBBS    👤    │
├─────────────────────┤
│ ┌─────┐ ┌─────┐    │
│ │Users│ │Msgs │    │
│ │ 142 │ │1234 │    │
│ └─────┘ └─────┘    │
│ ┌─────┐ ┌─────┐    │
│ │Areas│ │Activ│    │
│ │  8  │ │ 23  │    │
│ └─────┘ └─────┘    │
├─────────────────────┤
│                     │
│  Activity Chart     │
│  (scrollable)       │
│                     │
├─────────────────────┤
│  Recent Activity    │
│  - User joined...   │
│  - Message posted...│
├─────────────────────┤
│  System Status      │
│  Radio: ● Connected │
│  DB: 45MB           │
└─────────────────────┘
```

#### 3.2 Real-time Updates

**WebSocket Events:**
```typescript
interface WSEvent {
  type: 'user_joined' | 'user_left' | 'message_posted' |
        'user_banned' | 'area_created' | 'system_alert';
  timestamp: string;
  data: Record<string, unknown>;
}
```

**Features:**
- Contatori che si aggiornano in tempo reale
- Toast notifications per eventi importanti
- Activity feed live
- Indicatore stato connessione radio

#### 3.3 System Status Widget

**Metriche monitorate:**
- Stato connessione radio (connected/disconnected/error)
- Dimensione database e spazio disponibile
- Uptime sistema
- CPU/RAM usage (se disponibile)
- Rate limiter status (utenti bloccati)
- Scheduler status (prossimo cleanup)

**Deliverables Fase 3:**
- [x] Dashboard completa responsive
- [x] 4 KPI cards con animazioni
- [x] Activity chart interattivo (Recharts)
- [x] Real-time activity feed
- [x] System status widget
- [x] WebSocket connection con auto-reconnect
- [x] Toast notification system

**Status Fase 3: COMPLETATA (17 Gennaio 2026)** - Integrata nella Fase 2

---

### Fase 4: User Management (Sprint 7-8)

#### 4.1 Users List Page

**Features:**
- Tabella paginata e ordinabile
- Filtri: ruolo, stato (banned/muted/kicked), attività
- Ricerca per nickname o public key
- Azioni bulk (ban multipli, export)
- Quick actions inline (ban, mute, view)

**Colonne tabella:**
| Colonna | Descrizione | Ordinabile |
|---------|-------------|------------|
| User | Avatar + nickname + key | Sì |
| Role | Badge (Admin/Mod/User) | Sì |
| Status | Active/Banned/Muted/Kicked | Sì |
| Messages | Conteggio messaggi | Sì |
| Last Seen | Data ultimo accesso | Sì |
| Joined | Data registrazione | Sì |
| Actions | Dropdown menu | No |

#### 4.2 User Detail Page

**Sezioni:**
1. **Header**: Avatar, nickname, role badge, quick actions
2. **Info Card**: Public key, email, registration date, last seen
3. **Statistics**: Messages sent, PMs sent/received, areas active in
4. **Activity Timeline**: Ultimi 50 eventi dell'utente
5. **Moderation History**: Ban/mute/kick precedenti
6. **Messages**: Lista messaggi dell'utente (con delete)
7. **Actions Panel**: Promote/demote, ban/mute/kick con form

#### 4.3 Moderation Actions

**Ban Dialog:**
```
┌─────────────────────────────────────┐
│  🚫 Ban User                    ✕   │
├─────────────────────────────────────┤
│                                     │
│  Are you sure you want to ban       │
│  @JohnDoe?                          │
│                                     │
│  Reason (optional):                 │
│  ┌─────────────────────────────┐   │
│  │ Spam e messaggi inappropriati│   │
│  └─────────────────────────────┘   │
│                                     │
│  ☐ Notify user via BBS message     │
│  ☐ Delete all user's messages      │
│                                     │
│  ┌─────────┐  ┌─────────────────┐  │
│  │ Cancel  │  │   Ban User 🚫   │  │
│  └─────────┘  └─────────────────┘  │
└─────────────────────────────────────┘
```

**Kick Dialog (con durata):**
```
┌─────────────────────────────────────┐
│  ⏱️ Kick User                   ✕   │
├─────────────────────────────────────┤
│                                     │
│  Duration:                          │
│  ┌─────────────────────────────┐   │
│  │ 30 minutes              ▼   │   │
│  └─────────────────────────────┘   │
│  Options: 15m, 30m, 1h, 2h, 6h, 24h│
│                                     │
│  Reason (optional):                 │
│  ┌─────────────────────────────┐   │
│  │                             │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────┐  ┌─────────────────┐  │
│  │ Cancel  │  │   Kick User ⏱️  │  │
│  └─────────┘  └─────────────────┘  │
└─────────────────────────────────────┘
```

**Deliverables Fase 4:**
- [x] Users list con filtri e ricerca
- [x] User detail modal
- [x] Moderation dialogs (ban/mute/kick)
- [x] Promote/demote functionality
- [ ] Bulk actions (parziale)
- [ ] Activity timeline component
- [ ] Export utenti (CSV/JSON)

**Status Fase 4: PARZIALMENTE COMPLETATA (17 Gennaio 2026)** - Funzionalità base integrate nella Fase 2

---

### Fase 5: Content Management (Sprint 9-10)

#### 5.1 Areas Management

**Features:**
- Lista aree con statistiche
- Crea nuova area (form validato)
- Modifica area (nome, descrizione, readonly, public)
- Elimina area (con conferma e conteggio messaggi)
- Riordina aree (drag & drop)

**Area Form:**
```
┌─────────────────────────────────────┐
│  Create New Area                ✕   │
├─────────────────────────────────────┤
│                                     │
│  Name *                             │
│  ┌─────────────────────────────┐   │
│  │ technology                   │   │
│  └─────────────────────────────┘   │
│  2-32 chars, letters/numbers/-/_   │
│                                     │
│  Description                        │
│  ┌─────────────────────────────┐   │
│  │ Discussioni su tecnologia   │   │
│  │ e programmazione            │   │
│  └─────────────────────────────┘   │
│                                     │
│  ☐ Read-only (no posting)          │
│  ☑ Public (visible in /areas)      │
│                                     │
│  ┌─────────┐  ┌─────────────────┐  │
│  │ Cancel  │  │  Create Area    │  │
│  └─────────┘  └─────────────────┘  │
└─────────────────────────────────────┘
```

#### 5.2 Messages Management

**Features:**
- Lista messaggi con filtri (area, autore, data)
- Preview messaggio con thread
- Delete messaggio (con conferma)
- Bulk delete per area
- Export messaggi

**Message Row:**
```
┌────────────────────────────────────────────────────────────────┐
│ #123 │ @Mario │ #tech │ "Ciao a tutti, ho una domand..." │ 2h │ 🗑️ │
└────────────────────────────────────────────────────────────────┘
```

#### 5.3 Activity Logs

**Features:**
- Timeline filtrable per tipo evento
- Filtri: tipo, utente, data range
- Export logs
- Clear logs (con retention)

**Log Entry:**
```
┌────────────────────────────────────────────────────────────────┐
│ 🔵 USER_BANNED                                      14:23:45   │
│    Admin @SuperAdmin banned user @Spammer                      │
│    Reason: "Spam ripetuto"                                     │
│    IP: 192.168.1.100                                           │
└────────────────────────────────────────────────────────────────┘
```

**Deliverables Fase 5:**
- [x] Areas CRUD completo
- [x] Messages list con filtri
- [x] Message preview modal
- [x] Delete messages (singolo e bulk)
- [x] Activity logs viewer
- [x] Export funzionalità (JSON/CSV)
- [ ] Filtri data range con date picker

**Status Fase 5: COMPLETATA (17 Gennaio 2026)** - Integrata nella Fase 2

---

### Fase 6: Settings & Configuration (Sprint 11-12)

#### 6.1 Settings Page

**Sezioni:**

**General Settings:**
- BBS Name
- Default Area
- Message max length
- Welcome message

**Privacy & Retention:**
- PM retention days (slider 0-365)
- Log retention days (slider 0-365)
- Enable ephemeral messages (toggle)
- Auto cleanup schedule (cron picker)

**Rate Limiting:**
- Min interval between commands (slider)
- Max commands per minute (slider)
- Block duration (slider)
- Enable rate limiting (toggle)

**Radio Connection:**
- Serial port (select)
- Baud rate (select)
- Connection status (indicator)
- Test connection (button)

**Admin Accounts:**
- Lista admin
- Aggiungi admin
- Rimuovi admin
- Reset password

#### 6.2 Settings Persistence

Le impostazioni sono salvate in:
1. Environment variables (priorità)
2. `config.yaml` file
3. Database `settings` table (per override runtime)

**Deliverables Fase 6:**
- [x] Settings form completo
- [x] Validazione client-side
- [x] Save con feedback (toast)
- [ ] Reset to defaults
- [ ] Admin management page
- [ ] Connection test tool
- [ ] Config file editor (advanced)

**Status Fase 6: PARZIALMENTE COMPLETATA (17 Gennaio 2026)** - Form settings base integrato nella Fase 2

---

### Fase 7: Polish & Optimization (Sprint 13-14)

#### 7.1 Performance Optimization

**Frontend:**
- Code splitting per route
- Lazy loading componenti pesanti
- Image optimization
- Bundle size < 200KB gzipped
- First Contentful Paint < 1.5s

**Backend:**
- Response caching (Redis opzionale)
- Query optimization
- Connection pooling
- Gzip compression

#### 7.2 Accessibility (WCAG 2.1 AA)

- Keyboard navigation completa
- Screen reader support
- Focus indicators visibili
- Color contrast ratio >= 4.5:1
- Skip links
- ARIA labels

#### 7.3 Testing

**Frontend:**
- Unit tests (Vitest)
- Component tests (Testing Library)
- E2E tests (Playwright)
- Coverage > 80%

**Backend:**
- Unit tests (pytest)
- API integration tests
- Coverage > 85%

#### 7.4 Documentation

- README per web module
- API documentation (Swagger)
- Component storybook
- Deployment guide
- Admin user guide

**Deliverables Fase 7:**
- [x] E2E Tests con Playwright (54 test passati)
- [ ] Performance audit passato
- [ ] Lighthouse score > 90
- [ ] WCAG 2.1 AA compliance
- [ ] Test coverage targets raggiunti
- [ ] Documentation completa
- [ ] Security audit

**Status Fase 7: IN CORSO (17 Gennaio 2026)**

**E2E Test Results:**
- 54 test E2E passati con Playwright
- Test coverage:
  - Authentication: 5 test (login, validation, redirect)
  - Dashboard: 13 test (stats, charts, navigation)
  - Users: 7 test (list, filter, moderation)
  - Areas: 9 test (CRUD, table, dialogs)
  - Messages: 9 test (list, filter, delete)
  - Responsive: 11 test (mobile, tablet, desktop)

**Test Files:**
```
web/e2e/
├── auth.spec.ts       # 5 tests - Authentication flow
├── dashboard.spec.ts  # 13 tests - Dashboard & navigation
├── users.spec.ts      # 7 tests - User management
├── areas.spec.ts      # 9 tests - Areas CRUD
├── messages.spec.ts   # 9 tests - Messages management
└── responsive.spec.ts # 11 tests - Responsive design
```

**Playwright Configuration:**
- Browser: Chromium
- Base URL: http://localhost:3000
- API mocking via page.route()
- Screenshot on failure
- Trace on first retry

**Skeleton Loaders:**
- Componente `Skeleton` base con varianti (text, circular, rectangular)
- `SkeletonText` per blocchi di testo
- `SkeletonCard` per card generiche
- `SkeletonTable` per tabelle
- `SkeletonStatCard` per stat cards
- `SkeletonChart` per grafici
- `DashboardSkeleton` per la dashboard completa
- `TablePageSkeleton` per pagine con tabelle

**Custom Hooks:**
```
web/src/hooks/
├── index.ts           # Export aggregato
├── useDebounce.ts     # Debounce valori
├── useLocalStorage.ts # Persistenza localStorage
├── useMediaQuery.ts   # Responsive breakpoints
├── useOnClickOutside.ts # Click outside detection
├── useAsync.ts        # Gestione async operations
├── usePagination.ts   # Paginazione con URL sync
└── useInterval.ts     # Intervalli e timeout
```

Hooks disponibili:
- `useDebounce(value, delay)` - Debounce di valori (es. search)
- `useLocalStorage(key, initialValue)` - Stato persistente in localStorage
- `useMediaQuery(query)` - Detect media query match
- `useIsMobile()`, `useIsTablet()`, `useIsDesktop()` - Breakpoint hooks
- `usePrefersDarkMode()` - Detect dark mode preference
- `usePrefersReducedMotion()` - Detect reduced motion preference
- `useOnClickOutside(ref, handler)` - Click outside detection
- `useAsync(asyncFn, immediate)` - Async state management
- `useAsyncFn(asyncFn)` - Async function wrapper
- `usePagination(options)` - Pagination with URL sync
- `useInterval(callback, delay)` - Interval management
- `useTimeout(callback, delay)` - Timeout management

---

## Deployment

### Struttura Finale

```
src/
├── bbs/                    # BBS core (esistente)
├── web/                    # Web interface
│   ├── backend/            # FastAPI
│   └── frontend/           # React (build output in static/)
├── meshcore/               # MeshCore protocol
└── utils/                  # Utilities
```

### Avvio Unificato

```bash
# Development
python main.py --with-web --web-port 8080 --debug

# Production
python main.py --with-web --web-port 8080
```

### Build Frontend

```bash
cd src/web/frontend
npm run build
# Output in src/web/backend/static/
```

### Risorse Raspberry Pi

**Requisiti minimi:**
- RAM: 512MB (1GB consigliato)
- Storage: 100MB per applicazione
- CPU: Single core sufficiente

**Ottimizzazioni:**
- Frontend pre-built (no build sul Pi)
- SQLite WAL mode
- Uvicorn con 2 workers

---

## Timeline

| Fase | Sprint | Durata | Milestone |
|------|--------|--------|-----------|
| 1 | 1-2 | 2 settimane | API Backend completa |
| 2 | 3-4 | 2 settimane | Frontend foundation |
| 3 | 5-6 | 2 settimane | Dashboard funzionante |
| 4 | 7-8 | 2 settimane | User management |
| 5 | 9-10 | 2 settimane | Content management |
| 6 | 11-12 | 2 settimane | Settings & config |
| 7 | 13-14 | 2 settimane | Polish & release |

**Totale: 14 settimane**

---

## Rischi e Mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|-------------|---------|-------------|
| Performance su Raspberry | Media | Alto | Pre-build frontend, ottimizzazioni SQLite |
| Conflitti DB concurrent | Bassa | Alto | WAL mode, lock espliciti |
| Sicurezza auth | Media | Critico | JWT best practices, audit |
| Complessità UI mobile | Media | Medio | Mobile-first design, test su dispositivi reali |

---

## Appendice A: Mockup Screens

### Login Page
```
┌─────────────────────────────────────┐
│                                     │
│         ┌───────────────┐          │
│         │   MeshCore    │          │
│         │     BBS       │          │
│         │    Admin      │          │
│         └───────────────┘          │
│                                     │
│  Username                           │
│  ┌─────────────────────────────┐   │
│  │ admin                        │   │
│  └─────────────────────────────┘   │
│                                     │
│  Password                           │
│  ┌─────────────────────────────┐   │
│  │ ••••••••                    │   │
│  └─────────────────────────────┘   │
│                                     │
│  ☐ Remember me                     │
│                                     │
│  ┌─────────────────────────────┐   │
│  │         Sign In             │   │
│  └─────────────────────────────┘   │
│                                     │
│  v1.3.0 • MeshCore BBS             │
└─────────────────────────────────────┘
```

### Mobile Navigation
```
┌─────────────────────┐
│ ☰  MeshBBS    🔔 👤 │  <- Header fisso
├─────────────────────┤
│                     │
│   Page Content      │
│                     │
├─────────────────────┤
│ 🏠  👥  📁  ⚙️  📊 │  <- Bottom nav
└─────────────────────┘
  Dash User Area Set Log
```

---

## Appendice B: API Response Examples

### Dashboard Stats
```json
{
  "users": {
    "total": 142,
    "active_24h": 23,
    "banned": 5,
    "muted": 2
  },
  "messages": {
    "total": 1234,
    "today": 45,
    "week": 312
  },
  "areas": {
    "total": 8,
    "active": 6
  },
  "system": {
    "uptime_seconds": 302400,
    "db_size_mb": 45.2,
    "radio_connected": true
  }
}
```

### User Detail
```json
{
  "public_key": "abc123def456...",
  "nickname": "Mario",
  "role": "moderator",
  "is_banned": false,
  "is_muted": false,
  "is_kicked": false,
  "created_at": "2026-01-15T10:30:00Z",
  "last_seen": "2026-01-17T14:22:00Z",
  "stats": {
    "messages_count": 156,
    "pms_sent": 23,
    "pms_received": 45
  }
}
```

---

**Documento approvato da:** ________________
**Data:** ________________
