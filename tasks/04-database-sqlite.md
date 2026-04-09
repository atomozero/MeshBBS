# Task 04: Database SQLite

## Stato: ✅ COMPLETATO

## Analisi

### Contesto
Il database SQLite è il cuore della persistenza del BBS. A differenza del Room Server nativo di MeshCore (limitato a 32 messaggi), il BBS deve supportare:
- Storage illimitato di messaggi
- Multiple aree tematiche
- Gestione utenti con ruoli
- Messaggi privati
- Log delle attività

### Architettura Database

```
┌─────────────────────────────────────────────────────────────┐
│                      DATABASE BBS                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  users  │  │  areas  │  │ messages │  │private_msgs  │  │
│  └────┬────┘  └────┬────┘  └────┬─────┘  └──────┬───────┘  │
│       │            │            │               │           │
│       └────────────┴─────┬──────┴───────────────┘           │
│                          │                                   │
│                   ┌──────▼──────┐                           │
│                   │activity_log │                           │
│                   └─────────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementazione Completata

### File Creati

| File | Descrizione |
|------|-------------|
| `src/bbs/models/base.py` | Configurazione SQLAlchemy, session management |
| `src/bbs/models/user.py` | Modello User |
| `src/bbs/models/area.py` | Modello Area |
| `src/bbs/models/message.py` | Modello Message |
| `src/bbs/models/private_message.py` | Modello PrivateMessage |
| `src/bbs/models/activity_log.py` | Modello ActivityLog + EventType |
| `src/bbs/repositories/base_repository.py` | Repository generico CRUD |
| `src/bbs/repositories/user_repository.py` | Repository User |
| `src/bbs/repositories/area_repository.py` | Repository Area |
| `src/bbs/repositories/message_repository.py` | Repository Message |

---

## Modelli Implementati

### User (`src/bbs/models/user.py`)

```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    public_key = Column(String(64), unique=True, nullable=False)
    nickname = Column(String(32), nullable=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    is_admin = Column(Boolean, default=False)
    is_moderator = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    ban_reason = Column(String(255), nullable=True)

    # Properties
    @property
    def display_name(self) -> str: ...
    @property
    def short_key(self) -> str: ...

    # Methods
    def can_post(self) -> bool: ...
    def can_moderate(self) -> bool: ...
    def ban(self, reason=None): ...
    def unban(self): ...
```

### Area (`src/bbs/models/area.py`)

```python
class Area(Base):
    __tablename__ = "areas"

    id = Column(Integer, primary_key=True)
    name = Column(String(32), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=True)
    is_readonly = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    message_count = Column(Integer, default=0)
    last_post_at = Column(DateTime, nullable=True)

    # Relationships
    messages = relationship("Message", back_populates="area")
```

### Message (`src/bbs/models/message.py`)

```python
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    area_id = Column(Integer, ForeignKey("areas.id"))
    sender_key = Column(String(64), ForeignKey("users.public_key"))
    subject = Column(String(64), nullable=True)
    body = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    parent_id = Column(Integer, ForeignKey("messages.id"))  # Threading
    hops = Column(Integer, default=0)
    rssi = Column(Integer, nullable=True)

    # Properties
    @property
    def preview(self) -> str: ...
    @property
    def age_string(self) -> str: ...
    @property
    def is_reply(self) -> bool: ...
```

### PrivateMessage (`src/bbs/models/private_message.py`)

```python
class PrivateMessage(Base):
    __tablename__ = "private_messages"

    id = Column(Integer, primary_key=True)
    sender_key = Column(String(64), ForeignKey("users.public_key"))
    recipient_key = Column(String(64), ForeignKey("users.public_key"))
    body = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)

    def mark_as_read(self): ...
```

### ActivityLog (`src/bbs/models/activity_log.py`)

```python
class EventType(str, Enum):
    USER_FIRST_SEEN = "user_first_seen"
    USER_NICKNAME_SET = "user_nickname_set"
    USER_BANNED = "user_banned"
    MESSAGE_POSTED = "message_posted"
    PRIVATE_MSG_SENT = "private_msg_sent"
    BBS_STARTED = "bbs_started"
    BBS_STOPPED = "bbs_stopped"
    ADVERT_SENT = "advert_sent"
    ERROR = "error"

class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String(32), nullable=False)
    user_key = Column(String(64), nullable=True)
    details = Column(Text, nullable=True)
```

---

## Repository Pattern

### BaseRepository

```python
class BaseRepository(Generic[T]):
    model: Type[T]

    def __init__(self, session: Session): ...
    def get_by_id(self, id: int) -> Optional[T]: ...
    def get_all(self, limit=100, offset=0) -> List[T]: ...
    def add(self, entity: T) -> T: ...
    def update(self, entity: T) -> T: ...
    def delete(self, entity: T) -> bool: ...
    def count(self) -> int: ...
```

### UserRepository

```python
class UserRepository(BaseRepository[User]):
    def get_by_public_key(self, key: str) -> Optional[User]: ...
    def get_or_create(self, public_key: str) -> Tuple[User, bool]: ...
    def set_nickname(self, public_key: str, nickname: str) -> Optional[User]: ...
    def get_active_users(self, hours=24) -> List[User]: ...
```

### MessageRepository

```python
class MessageRepository(BaseRepository[Message]):
    def create_message(self, area_name, sender_key, body, ...) -> Optional[Message]: ...
    def get_by_area(self, area_name, limit=10) -> List[Message]: ...
    def get_thread(self, message_id) -> List[Message]: ...
```

---

## Configurazione Database

### Session Management (`src/bbs/models/base.py`)

```python
def init_database(db_path: str = "data/bbs.db") -> None:
    """Initialize database with WAL mode for performance."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    _create_default_data()

@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager with auto-commit/rollback."""
    session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### SQLite Pragmas (Performance)

```python
@event.listens_for(_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
    cursor.close()
```

---

## Test Completati

**File**: `tests/test_models.py` (14 test)

- ✅ test_create_user
- ✅ test_user_short_key
- ✅ test_user_display_name_with_nick
- ✅ test_user_display_name_without_nick
- ✅ test_user_unique_key
- ✅ test_create_area
- ✅ test_area_unique_name
- ✅ test_default_areas_exist
- ✅ test_create_message
- ✅ test_message_preview
- ✅ test_message_threading
- ✅ test_create_private_message
- ✅ test_mark_as_read
- ✅ test_log_activity

---

## Aree di Default

Il database viene inizializzato con 3 aree di default:

| Nome | Descrizione |
|------|-------------|
| generale | Area di discussione generale |
| tech | Discussioni tecniche e progetti |
| emergenze | Comunicazioni urgenti e emergenze |

---

## Checklist Finale

- [x] Schema database progettato
- [x] Modelli SQLAlchemy creati (User, Area, Message, PrivateMessage, ActivityLog)
- [x] Repository pattern implementato
- [x] Session management con context manager
- [x] WAL mode per performance
- [x] Foreign keys abilitati
- [x] Indici ottimizzati
- [x] Aree di default create
- [x] Test passati (14 test)
