# MeshBBS Federation Architecture

## Technical Analysis Document

**Version:** 1.0
**Date:** January 2026
**Status:** Proposal / RFC

---

## 1. Executive Summary

Questo documento analizza la fattibilità tecnica e propone un'architettura per un sistema di federazione nativo per MeshBBS, permettendo a più nodi BBS di comunicare e sincronizzare dati attraverso la rete mesh LoRa.

### 1.1 Obiettivi

- **Resilienza**: Funzionamento anche con connettività intermittente
- **Efficienza**: Minimizzare l'uso della banda (~300 bytes/messaggio max)
- **Decentralizzazione**: Nessun nodo "master", architettura peer-to-peer
- **Compatibilità**: Integrazione con l'architettura MeshBBS esistente

### 1.2 Vincoli Tecnici

| Vincolo | Valore | Impatto |
|---------|--------|---------|
| Payload max LoRa | ~300 bytes | Messaggi frammentati |
| Latenza tipica | 1-30 secondi | Store-and-forward obbligatorio |
| Duty cycle LoRa | 1-10% | Sincronizzazione asincrona |
| Connettività | Intermittente | Offline-first design |

---

## 2. Architettura di Alto Livello

```
┌─────────────────────────────────────────────────────────────────┐
│                     FEDERATION LAYER                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │  MeshBBS    │    │  MeshBBS    │    │  MeshBBS    │          │
│  │   Node A    │◄──►│   Node B    │◄──►│   Node C    │          │
│  │  (Roma)     │    │  (Milano)   │    │  (Torino)   │          │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘          │
│         │                   │                   │                 │
│         ▼                   ▼                   ▼                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │   Local     │    │   Local     │    │   Local     │          │
│  │   Users     │    │   Users     │    │   Users     │          │
│  └─────────────┘    └─────────────┘    └─────────────┘          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MESHCORE NETWORK                             │
│                                                                   │
│     LoRa Radio  ◄────────────────────────►  LoRa Radio          │
│     (433/868/915 MHz)                       (433/868/915 MHz)   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 Componenti Principali

#### 2.1.1 Federation Manager
Gestisce la logica di federazione ad alto livello:
- Discovery dei nodi
- Gestione delle connessioni
- Routing dei messaggi federati

#### 2.1.2 Sync Engine
Motore di sincronizzazione:
- Risoluzione conflitti
- Delta sync (solo modifiche)
- Prioritizzazione messaggi

#### 2.1.3 Message Router
Instradamento messaggi tra nodi:
- PM relay
- Broadcast propagation
- Loop prevention

#### 2.1.4 Store-and-Forward Queue
Coda persistente per messaggi in attesa:
- Retry automatico
- TTL management
- Deduplicazione

---

## 3. Modelli di Federazione

### 3.1 Modello Hub-and-Spoke

```
         ┌─────────┐
         │  Hub    │
         │  Node   │
         └────┬────┘
              │
    ┌─────────┼─────────┐
    │         │         │
┌───▼───┐ ┌───▼───┐ ┌───▼───┐
│Spoke A│ │Spoke B│ │Spoke C│
└───────┘ └───────┘ └───────┘
```

**Vantaggi:**
- Semplice da implementare
- Routing prevedibile
- Facile gestione

**Svantaggi:**
- Single point of failure
- Hub sovraccaricato
- Non adatto per mesh reale

### 3.2 Modello Mesh Completo (Proposto)

```
    ┌───────┐
    │Node A │◄─────────────┐
    └───┬───┘              │
        │                  │
        ▼                  ▼
    ┌───────┐          ┌───────┐
    │Node B │◄────────►│Node C │
    └───┬───┘          └───┬───┘
        │                  │
        └────────┬─────────┘
                 ▼
             ┌───────┐
             │Node D │
             └───────┘
```

**Vantaggi:**
- Nessun single point of failure
- Auto-healing topology
- Distribuzione carico naturale

**Svantaggi:**
- Complessità maggiore
- Potenziali loop
- Overhead di coordinamento

### 3.3 Modello Ibrido Gerarchico

```
┌─────────────────────────────────────────┐
│            TIER 1 (Regional)            │
│  ┌─────┐      ┌─────┐      ┌─────┐     │
│  │ R1  │◄────►│ R2  │◄────►│ R3  │     │
│  └──┬──┘      └──┬──┘      └──┬──┘     │
└─────┼────────────┼───────────┼─────────┘
      │            │           │
┌─────▼────┐ ┌─────▼────┐ ┌───▼──────┐
│ TIER 2   │ │ TIER 2   │ │ TIER 2   │
│ (Local)  │ │ (Local)  │ │ (Local)  │
│ L1  L2   │ │ L3  L4   │ │ L5  L6   │
└──────────┘ └──────────┘ └──────────┘
```

**Raccomandazione:** Modello Ibrido Gerarchico
- TIER 1: Nodi con buona connettività (gateway regionali)
- TIER 2: Nodi locali che si connettono al tier più vicino

---

## 4. Identità e Naming

### 4.1 Identificatori di Nodo

```
Node ID Format: [16-bit node_id]
Example: 0xA1B2

Fully Qualified Node Address (FQNA):
  meshbbs://[node_id]/[resource]
  meshbbs://a1b2/users/alice
  meshbbs://a1b2/areas/general
```

### 4.2 Identificatori Utente Federati

```python
class FederatedUserId:
    """
    Formato: username@node_id
    Esempio: alice@a1b2
    """
    username: str      # max 16 chars
    home_node: int     # 16-bit node ID

    def __str__(self):
        return f"{self.username}@{self.home_node:04x}"

    def to_bytes(self) -> bytes:
        # 16 bytes username + 2 bytes node = 18 bytes
        name_bytes = self.username.encode('utf-8')[:16].ljust(16, b'\x00')
        return name_bytes + self.home_node.to_bytes(2, 'big')
```

### 4.3 Identificatori di Area/Messaggio

```python
class FederatedAreaId:
    """
    Formato: area_name@node_id
    Per aree globali: area_name@global
    """
    name: str
    origin_node: int  # 0x0000 = global

class FederatedMessageId:
    """
    Formato: [node_id:4][timestamp:4][seq:2] = 10 bytes
    Garantisce unicità globale
    """
    node_id: int      # 2 bytes
    timestamp: int    # 4 bytes (unix epoch)
    sequence: int     # 2 bytes (per-second counter)
```

---

## 5. Sincronizzazione Dati

### 5.1 Tipi di Dati Sincronizzabili

| Tipo | Direzione | Priorità | Note |
|------|-----------|----------|------|
| PM (Private Messages) | Peer-to-peer | Alta | Crittografati E2E |
| Public Posts | Broadcast/Pull | Media | Compressione delta |
| User Profiles | On-demand | Bassa | Cache locale |
| Area Metadata | Broadcast | Bassa | Infrequente |
| Node Status | Heartbeat | Alta | Ogni 5-15 min |

### 5.2 Strategia di Sincronizzazione

#### 5.2.1 Vector Clocks per Ordinamento

```python
class VectorClock:
    """
    Traccia le versioni per ogni nodo conosciuto.
    Permette ordinamento parziale senza clock sincronizzati.
    """
    def __init__(self):
        self.clock: Dict[int, int] = {}  # node_id -> counter

    def increment(self, node_id: int):
        self.clock[node_id] = self.clock.get(node_id, 0) + 1

    def merge(self, other: 'VectorClock'):
        for node_id, counter in other.clock.items():
            self.clock[node_id] = max(
                self.clock.get(node_id, 0),
                counter
            )

    def to_bytes(self) -> bytes:
        # [1B num_entries][2B node_id + 4B counter] * n
        entries = len(self.clock)
        data = bytes([entries])
        for node_id, counter in self.clock.items():
            data += node_id.to_bytes(2, 'big')
            data += counter.to_bytes(4, 'big')
        return data
```

#### 5.2.2 Merkle Trees per Sync Efficiente

```python
class SyncMerkleTree:
    """
    Merkle tree per identificare rapidamente differenze
    tra due nodi senza trasferire tutti i dati.
    """
    def __init__(self, area_id: str):
        self.area_id = area_id
        self.root_hash: bytes = b''
        self.buckets: Dict[int, bytes] = {}  # hour_bucket -> hash

    def compute_bucket_hash(self, messages: List[Message]) -> bytes:
        # Hash di tutti i message_id nel bucket
        hasher = hashlib.sha256()
        for msg in sorted(messages, key=lambda m: m.id):
            hasher.update(msg.id.to_bytes())
        return hasher.digest()[:8]  # 8 bytes per bucket

    def compare(self, remote_root: bytes) -> bool:
        return self.root_hash == remote_root

    def find_differences(self, remote_buckets: Dict[int, bytes]) -> List[int]:
        """Ritorna i bucket che differiscono"""
        diff = []
        all_buckets = set(self.buckets.keys()) | set(remote_buckets.keys())
        for bucket in all_buckets:
            local = self.buckets.get(bucket, b'\x00' * 8)
            remote = remote_buckets.get(bucket, b'\x00' * 8)
            if local != remote:
                diff.append(bucket)
        return diff
```

### 5.3 Conflict Resolution

**Strategia: Last-Write-Wins con Vector Clocks**

```python
def resolve_conflict(local: Message, remote: Message) -> Message:
    """
    Risolve conflitti tra versioni di un messaggio.
    """
    # 1. Confronta vector clocks
    local_vc = local.vector_clock
    remote_vc = remote.vector_clock

    if local_vc.happens_before(remote_vc):
        return remote  # Remote è più recente
    elif remote_vc.happens_before(local_vc):
        return local   # Local è più recente
    else:
        # Conflitto reale: usa timestamp come tiebreaker
        if remote.timestamp > local.timestamp:
            return remote
        elif local.timestamp > remote.timestamp:
            return local
        else:
            # Stesso timestamp: usa node_id più alto
            return remote if remote.node_id > local.node_id else local
```

---

## 6. Store-and-Forward

### 6.1 Architettura della Coda

```python
class FederationQueue:
    """
    Coda persistente per messaggi federati in attesa di delivery.
    """

    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS outbound_queue (
                id INTEGER PRIMARY KEY,
                message_id BLOB UNIQUE,
                target_node INTEGER,
                message_type INTEGER,
                payload BLOB,
                priority INTEGER DEFAULT 5,
                created_at INTEGER,
                expires_at INTEGER,
                retry_count INTEGER DEFAULT 0,
                last_retry_at INTEGER,
                status TEXT DEFAULT 'pending'
            )
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_target_status
            ON outbound_queue(target_node, status, priority DESC)
        """)

    async def enqueue(
        self,
        target_node: int,
        message_type: int,
        payload: bytes,
        priority: int = 5,
        ttl_hours: int = 72
    ):
        """Aggiunge un messaggio alla coda"""
        now = int(time.time())
        message_id = self._generate_message_id()

        self.db.execute("""
            INSERT INTO outbound_queue
            (message_id, target_node, message_type, payload,
             priority, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            message_id,
            target_node,
            message_type,
            payload,
            priority,
            now,
            now + (ttl_hours * 3600)
        ))
        self.db.commit()

    async def get_pending(self, target_node: int, limit: int = 10) -> List[QueuedMessage]:
        """Recupera messaggi pendenti per un nodo"""
        cursor = self.db.execute("""
            SELECT * FROM outbound_queue
            WHERE target_node = ?
              AND status = 'pending'
              AND expires_at > ?
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        """, (target_node, int(time.time()), limit))
        return [QueuedMessage(*row) for row in cursor.fetchall()]

    async def mark_delivered(self, message_id: bytes):
        """Segna un messaggio come consegnato"""
        self.db.execute("""
            UPDATE outbound_queue
            SET status = 'delivered'
            WHERE message_id = ?
        """, (message_id,))
        self.db.commit()

    async def cleanup_expired(self):
        """Rimuove messaggi scaduti"""
        self.db.execute("""
            DELETE FROM outbound_queue
            WHERE expires_at < ? OR status = 'delivered'
        """, (int(time.time()),))
        self.db.commit()
```

### 6.2 Retry Policy

```python
class RetryPolicy:
    """
    Politica di retry con backoff esponenziale.
    """

    # Intervalli di retry: 1min, 5min, 15min, 1h, 4h, 12h
    RETRY_INTERVALS = [60, 300, 900, 3600, 14400, 43200]
    MAX_RETRIES = 6

    @classmethod
    def get_next_retry_delay(cls, retry_count: int) -> int:
        """Ritorna il delay per il prossimo retry in secondi"""
        if retry_count >= cls.MAX_RETRIES:
            return -1  # Stop retrying
        return cls.RETRY_INTERVALS[min(retry_count, len(cls.RETRY_INTERVALS) - 1)]

    @classmethod
    def should_retry(cls, msg: QueuedMessage) -> bool:
        """Determina se un messaggio deve essere ritentato"""
        if msg.retry_count >= cls.MAX_RETRIES:
            return False
        if msg.expires_at < time.time():
            return False

        next_delay = cls.get_next_retry_delay(msg.retry_count)
        return time.time() >= msg.last_retry_at + next_delay
```

---

## 7. Discovery e Routing

### 7.1 Node Discovery Protocol

```python
class NodeAnnouncement:
    """
    Annuncio periodico di un nodo alla rete.
    Inviato ogni 10-15 minuti.
    """
    VERSION = 1

    def __init__(
        self,
        node_id: int,
        node_name: str,
        capabilities: int,
        public_key: bytes,
        areas: List[str],
        user_count: int,
        timestamp: int
    ):
        self.node_id = node_id
        self.node_name = node_name[:16]
        self.capabilities = capabilities  # Bitmap
        self.public_key = public_key[:32]
        self.areas = areas[:8]  # Max 8 aree
        self.user_count = user_count
        self.timestamp = timestamp

    def to_bytes(self) -> bytes:
        """
        Serializza per trasmissione LoRa.
        Target: < 200 bytes
        """
        # Header: version(1) + node_id(2) + caps(2) + timestamp(4) = 9 bytes
        data = bytes([self.VERSION])
        data += self.node_id.to_bytes(2, 'big')
        data += self.capabilities.to_bytes(2, 'big')
        data += self.timestamp.to_bytes(4, 'big')

        # Node name: length(1) + name(max 16) = max 17 bytes
        name_bytes = self.node_name.encode('utf-8')[:16]
        data += bytes([len(name_bytes)]) + name_bytes

        # Public key: 32 bytes
        data += self.public_key

        # Areas: count(1) + [length(1) + name(max 12)]* = max 105 bytes
        data += bytes([len(self.areas)])
        for area in self.areas[:8]:
            area_bytes = area.encode('utf-8')[:12]
            data += bytes([len(area_bytes)]) + area_bytes

        # User count: 2 bytes
        data += self.user_count.to_bytes(2, 'big')

        return data  # ~170 bytes tipicamente


# Capability flags
CAP_FEDERATION = 0x0001      # Supporta federazione
CAP_PM_RELAY = 0x0002        # Può inoltrare PM
CAP_AREA_MIRROR = 0x0004     # Può mirrorare aree
CAP_GATEWAY = 0x0008         # Gateway verso altre reti
CAP_HIGH_BANDWIDTH = 0x0010  # Connessione veloce disponibile
```

### 7.2 Routing Table

```python
class FederationRoutingTable:
    """
    Tabella di routing per la federazione.
    Mantiene le rotte verso altri nodi.
    """

    def __init__(self):
        self.routes: Dict[int, RouteEntry] = {}
        self.user_locations: Dict[str, int] = {}  # user@home -> last_seen_node

    def update_route(self, announcement: NodeAnnouncement, via_node: Optional[int] = None):
        """Aggiorna la rotta verso un nodo"""
        node_id = announcement.node_id

        # Rotta diretta o via gateway?
        next_hop = via_node if via_node else node_id
        hop_count = 1 if not via_node else self.routes.get(via_node, RouteEntry()).hop_count + 1

        existing = self.routes.get(node_id)
        if existing and existing.hop_count <= hop_count and existing.last_seen > announcement.timestamp:
            return  # Rotta esistente è migliore

        self.routes[node_id] = RouteEntry(
            node_id=node_id,
            next_hop=next_hop,
            hop_count=hop_count,
            capabilities=announcement.capabilities,
            last_seen=announcement.timestamp,
            areas=set(announcement.areas)
        )

    def get_route(self, target_node: int) -> Optional[RouteEntry]:
        """Ottiene la rotta verso un nodo"""
        return self.routes.get(target_node)

    def find_user(self, federated_user_id: str) -> Optional[int]:
        """Trova il nodo dove si trova un utente"""
        # Prima controlla la cache delle posizioni
        if federated_user_id in self.user_locations:
            return self.user_locations[federated_user_id]

        # Altrimenti usa l'home node
        username, home_node = federated_user_id.split('@')
        return int(home_node, 16)

    def update_user_location(self, federated_user_id: str, current_node: int):
        """Aggiorna la posizione di un utente (per roaming)"""
        self.user_locations[federated_user_id] = current_node
```

---

## 8. Sicurezza

### 8.1 Autenticazione tra Nodi

```python
class NodeAuthentication:
    """
    Autenticazione mutua tra nodi usando chiavi asimmetriche.
    """

    def __init__(self, private_key: bytes):
        self.private_key = private_key
        self.public_key = self._derive_public_key(private_key)
        self.trusted_nodes: Dict[int, bytes] = {}  # node_id -> public_key

    def sign_message(self, message: bytes) -> bytes:
        """Firma un messaggio con la chiave privata"""
        # Ed25519 signature
        return ed25519_sign(self.private_key, message)

    def verify_message(self, message: bytes, signature: bytes, node_id: int) -> bool:
        """Verifica la firma di un altro nodo"""
        public_key = self.trusted_nodes.get(node_id)
        if not public_key:
            return False
        return ed25519_verify(public_key, message, signature)

    def trust_node(self, node_id: int, public_key: bytes):
        """Aggiunge un nodo alla lista dei trusted"""
        self.trusted_nodes[node_id] = public_key
```

### 8.2 Crittografia End-to-End per PM

```python
class FederatedPMEncryption:
    """
    Crittografia E2E per messaggi privati federati.
    """

    @staticmethod
    def encrypt_pm(
        sender_private: bytes,
        recipient_public: bytes,
        plaintext: bytes
    ) -> bytes:
        """
        Cripta un PM usando X25519 + ChaCha20-Poly1305.
        """
        # Deriva shared secret
        shared_secret = x25519(sender_private, recipient_public)

        # Genera nonce casuale
        nonce = os.urandom(12)

        # Cripta con ChaCha20-Poly1305
        ciphertext = chacha20_poly1305_encrypt(shared_secret, nonce, plaintext)

        # Formato: nonce(12) + ciphertext(n+16)
        return nonce + ciphertext

    @staticmethod
    def decrypt_pm(
        recipient_private: bytes,
        sender_public: bytes,
        encrypted: bytes
    ) -> bytes:
        """Decripta un PM"""
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]

        shared_secret = x25519(recipient_private, sender_public)
        return chacha20_poly1305_decrypt(shared_secret, nonce, ciphertext)
```

### 8.3 Anti-Spam e Rate Limiting

```python
class FederationRateLimiter:
    """
    Rate limiting per messaggi federati per prevenire spam.
    """

    # Limiti per tipo di messaggio
    LIMITS = {
        'node_announce': (1, 600),      # 1 ogni 10 minuti
        'sync_request': (10, 60),       # 10 al minuto
        'pm_relay': (30, 60),           # 30 al minuto
        'public_post': (5, 60),         # 5 al minuto
    }

    def __init__(self):
        self.counters: Dict[Tuple[int, str], List[float]] = {}

    def check_allowed(self, node_id: int, message_type: str) -> bool:
        """Verifica se un messaggio è permesso"""
        limit, window = self.LIMITS.get(message_type, (100, 60))
        key = (node_id, message_type)

        now = time.time()
        timestamps = self.counters.get(key, [])

        # Rimuovi timestamp vecchi
        timestamps = [t for t in timestamps if now - t < window]

        if len(timestamps) >= limit:
            return False

        timestamps.append(now)
        self.counters[key] = timestamps
        return True
```

---

## 9. Integrazione con MeshBBS Esistente

### 9.1 Modifiche al Database Schema

```sql
-- Nuova tabella per nodi federati
CREATE TABLE federation_nodes (
    node_id INTEGER PRIMARY KEY,
    node_name TEXT NOT NULL,
    public_key BLOB NOT NULL,
    capabilities INTEGER DEFAULT 0,
    last_seen INTEGER,
    is_trusted BOOLEAN DEFAULT FALSE,
    created_at INTEGER NOT NULL
);

-- Nuova tabella per aree federate
CREATE TABLE federated_areas (
    id INTEGER PRIMARY KEY,
    local_area_id INTEGER REFERENCES areas(id),
    origin_node INTEGER,
    origin_area_name TEXT,
    sync_enabled BOOLEAN DEFAULT TRUE,
    last_sync INTEGER,
    UNIQUE(origin_node, origin_area_name)
);

-- Estensione tabella messaggi
ALTER TABLE messages ADD COLUMN federation_id BLOB UNIQUE;
ALTER TABLE messages ADD COLUMN origin_node INTEGER;
ALTER TABLE messages ADD COLUMN vector_clock BLOB;

-- Estensione tabella utenti
ALTER TABLE users ADD COLUMN federated_id TEXT UNIQUE;
ALTER TABLE users ADD COLUMN home_node INTEGER;
ALTER TABLE users ADD COLUMN public_key BLOB;
```

### 9.2 Nuove Classi del Domain Model

```python
# src/bbs/federation/models.py

@dataclass
class FederatedNode:
    """Rappresenta un nodo BBS federato"""
    node_id: int
    node_name: str
    public_key: bytes
    capabilities: int
    last_seen: datetime
    is_trusted: bool
    areas: List[str]

@dataclass
class FederatedMessage:
    """Messaggio con metadati di federazione"""
    local_id: int
    federation_id: bytes  # 10 bytes: node_id + timestamp + seq
    origin_node: int
    vector_clock: VectorClock
    content: str
    author: str  # federated_user_id
    area: str
    created_at: datetime

@dataclass
class FederationConfig:
    """Configurazione della federazione"""
    enabled: bool = False
    node_name: str = "unnamed"
    announce_interval: int = 900  # 15 minuti
    sync_interval: int = 300      # 5 minuti
    trusted_nodes: List[int] = field(default_factory=list)
    federated_areas: List[str] = field(default_factory=list)
    pm_relay_enabled: bool = True
```

---

## 10. Considerazioni sulle Performance

### 10.1 Overhead di Banda

| Operazione | Frequenza | Bytes/op | Bytes/ora |
|------------|-----------|----------|-----------|
| Node Announce | 4/ora | ~170 | 680 |
| Sync Request | 12/ora | ~50 | 600 |
| Sync Response | 12/ora | ~200 | 2400 |
| PM Relay | 10/ora | ~150 | 1500 |
| **Totale** | | | **~5.2 KB/ora** |

### 10.2 Latenza Tipica

```
Scenario: PM da Alice@NodeA a Bob@NodeC via NodeB

Alice@NodeA ─────> NodeA
                    │
                    ▼ (1-5 sec)
                  NodeB
                    │
                    ▼ (1-5 sec)
                  NodeC ─────> Bob@NodeC

Latenza totale: 2-10 secondi (caso ottimale)
Con store-and-forward: minuti - ore
```

### 10.3 Scalabilità

- **Nodi supportati**: ~256 (limitato da 16-bit node_id space effettivo)
- **Utenti per nodo**: ~1000 (limitato da DB locale)
- **Messaggi/giorno**: ~1000-5000 (limitato da duty cycle LoRa)

---

## 11. Conclusioni

La federazione nativa per MeshBBS è tecnicamente fattibile con le seguenti considerazioni:

### 11.1 Punti di Forza

1. **Compatibilità LoRa**: Protocollo progettato per i vincoli di banda
2. **Resilienza**: Store-and-forward gestisce connettività intermittente
3. **Decentralizzazione**: Nessun single point of failure
4. **Sicurezza**: Crittografia E2E e autenticazione tra nodi

### 11.2 Sfide

1. **Latenza**: Inevitabile con LoRa, mitigata con cache e priorità
2. **Complessità**: Richiede implementazione attenta
3. **Testing**: Difficile testare scenari mesh reali

### 11.3 Raccomandazioni

1. Implementare in fasi incrementali (vedi FEDERATION_ROADMAP.md)
2. Iniziare con PM relay (caso d'uso più richiesto)
3. Aggiungere sync aree in seconda fase
4. Considerare gateway IP opzionale per connettività ibrida

---

## Documenti Correlati

- [FEDERATION_PROTOCOL.md](./FEDERATION_PROTOCOL.md) - Specifica del protocollo wire
- [FEDERATION_ROADMAP.md](./FEDERATION_ROADMAP.md) - Piano di implementazione
- [FEDERATION_SECURITY.md](./FEDERATION_SECURITY.md) - Considerazioni di sicurezza dettagliate
