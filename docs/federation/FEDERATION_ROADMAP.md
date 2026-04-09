# MeshBBS Federation Implementation Roadmap

## Phased Implementation Plan

**Version:** 1.0
**Date:** January 2026
**Status:** Planning

---

## Overview

Questo documento definisce il piano di implementazione per il sistema di federazione MeshBBS, suddiviso in fasi incrementali per minimizzare il rischio e permettere feedback anticipato.

---

## Phase 1: Foundation

### Obiettivo
Stabilire l'infrastruttura base per la comunicazione tra nodi senza alterare le funzionalità esistenti.

### Deliverables

#### 1.1 Federation Core Module

```
src/bbs/federation/
├── __init__.py
├── config.py           # Configurazione federazione
├── models.py           # Data models federati
├── protocol.py         # Parsing/serialization messaggi
├── transport.py        # Adattatore MeshCore
└── exceptions.py       # Eccezioni specifiche
```

**Tasks:**

- [ ] Creare struttura directory federation
- [ ] Implementare `FederationConfig` con validazione
- [ ] Definire modelli dati (`FederatedNode`, `FederatedMessage`, etc.)
- [ ] Implementare serializzazione/deserializzazione messaggi
- [ ] Creare test unitari per protocol parsing

#### 1.2 Database Schema Extensions

```sql
-- migrations/004_federation.sql

-- Nodi federati conosciuti
CREATE TABLE federation_nodes (
    node_id INTEGER PRIMARY KEY,
    node_name TEXT NOT NULL,
    public_key BLOB NOT NULL,
    capabilities INTEGER DEFAULT 0,
    first_seen INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    is_trusted BOOLEAN DEFAULT FALSE,
    trust_level INTEGER DEFAULT 0,
    metadata TEXT  -- JSON per dati extra
);

-- Coda messaggi in uscita
CREATE TABLE federation_outbound (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id BLOB UNIQUE NOT NULL,
    target_node INTEGER NOT NULL,
    message_type INTEGER NOT NULL,
    payload BLOB NOT NULL,
    priority INTEGER DEFAULT 5,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    retry_count INTEGER DEFAULT 0,
    last_retry_at INTEGER,
    status TEXT DEFAULT 'pending',
    FOREIGN KEY (target_node) REFERENCES federation_nodes(node_id)
);

-- Log messaggi processati (per deduplicazione)
CREATE TABLE federation_processed (
    message_id BLOB PRIMARY KEY,
    source_node INTEGER NOT NULL,
    message_type INTEGER NOT NULL,
    processed_at INTEGER NOT NULL,
    result TEXT
);

CREATE INDEX idx_outbound_status ON federation_outbound(target_node, status);
CREATE INDEX idx_processed_time ON federation_processed(processed_at);
```

**Tasks:**

- [ ] Creare migration script
- [ ] Aggiornare `DatabaseManager` per nuove tabelle
- [ ] Implementare repository per operazioni CRUD
- [ ] Aggiungere cleanup job per dati vecchi

#### 1.3 Configuration System

```yaml
# config.yaml additions
federation:
  enabled: false
  node_id: null  # Auto-generated if null
  node_name: "My MeshBBS"

  # Discovery
  announce_interval: 900  # seconds
  discovery_enabled: true

  # Security
  require_trusted: false
  auto_trust: false
  trusted_nodes: []

  # Performance
  max_pending_messages: 1000
  message_ttl_hours: 72
```

**Tasks:**

- [ ] Estendere schema configurazione
- [ ] Validazione configurazione all'avvio
- [ ] Hot-reload per alcune impostazioni
- [ ] CLI commands per gestione config

### Milestone Criteria

- [ ] Tutti i test passano
- [ ] Documentazione API interna completa
- [ ] Nessun impatto su funzionalità esistenti
- [ ] Migration reversibile

---

## Phase 2: Node Discovery

### Obiettivo
Implementare la discovery automatica di nodi federati nella rete.

### Deliverables

#### 2.1 Node Announcement System

```python
# src/bbs/federation/discovery.py

class NodeDiscoveryService:
    """Gestisce discovery e annunci dei nodi"""

    def __init__(self, config: FederationConfig, transport: FederationTransport):
        self.config = config
        self.transport = transport
        self.known_nodes: Dict[int, FederatedNode] = {}
        self._announce_task: Optional[asyncio.Task] = None

    async def start(self):
        """Avvia il servizio di discovery"""
        # Carica nodi conosciuti dal DB
        await self._load_known_nodes()

        # Avvia task di annuncio periodico
        self._announce_task = asyncio.create_task(self._announce_loop())

        # Listener per annunci ricevuti
        self.transport.on_message(
            FederationMessageType.NODE_ANNOUNCE,
            self._handle_node_announce
        )

    async def _announce_loop(self):
        """Loop di annuncio periodico"""
        while True:
            try:
                await self._send_announcement()
                await asyncio.sleep(self.config.announce_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Announce error: {e}")
                await asyncio.sleep(60)  # Retry after error

    async def _send_announcement(self):
        """Invia annuncio del nodo"""
        announcement = NodeAnnouncement(
            node_id=self.config.node_id,
            node_name=self.config.node_name,
            capabilities=self._get_capabilities(),
            public_key=self.config.public_key,
            areas=await self._get_federated_areas(),
            user_count=await self._get_user_count(),
            timestamp=int(time.time())
        )

        msg = FederationMessage.create_announce(announcement)
        await self.transport.broadcast(msg)

    async def _handle_node_announce(self, msg: FederationMessage):
        """Gestisce annuncio ricevuto"""
        announcement = NodeAnnouncement.from_message(msg)

        # Verifica firma
        if not self._verify_announcement(announcement):
            logger.warning(f"Invalid announcement from {msg.source_node}")
            return

        # Aggiorna o inserisce nodo
        await self._update_node(announcement)

        # Notifica observers
        await self._notify_node_discovered(announcement)
```

**Tasks:**

- [ ] Implementare `NodeDiscoveryService`
- [ ] Creare `NodeAnnouncement` message type
- [ ] Implementare verifica firme
- [ ] Gestire timeout e cleanup nodi inattivi
- [ ] Test con mock transport

#### 2.2 Routing Table

```python
# src/bbs/federation/routing.py

class FederationRouter:
    """Gestisce routing verso nodi federati"""

    def __init__(self):
        self.routes: Dict[int, RouteEntry] = {}
        self.user_cache: LRUCache[str, int] = LRUCache(maxsize=1000)

    def update_from_announcement(self, announcement: NodeAnnouncement, via: Optional[int] = None):
        """Aggiorna routing da annuncio"""
        node_id = announcement.node_id
        hop_count = 1 if via is None else self.routes.get(via, RouteEntry()).hops + 1

        existing = self.routes.get(node_id)
        if existing and existing.hops <= hop_count and existing.timestamp > announcement.timestamp:
            return  # Rotta esistente è migliore

        self.routes[node_id] = RouteEntry(
            node_id=node_id,
            next_hop=via or node_id,
            hops=hop_count,
            capabilities=announcement.capabilities,
            timestamp=announcement.timestamp,
            areas=set(announcement.areas)
        )

    def get_next_hop(self, target: int) -> Optional[int]:
        """Ritorna il next hop per raggiungere un target"""
        route = self.routes.get(target)
        return route.next_hop if route else None

    def find_nodes_with_area(self, area_name: str) -> List[int]:
        """Trova nodi che hanno una certa area"""
        return [
            node_id for node_id, route in self.routes.items()
            if area_name in route.areas
        ]
```

**Tasks:**

- [ ] Implementare `FederationRouter`
- [ ] Algoritmo di selezione best route
- [ ] Cache utenti per roaming
- [ ] Expiration routes vecchie

#### 2.3 CLI Commands

```bash
# Nuovi comandi CLI per discovery

meshbbs federation status
# Output: Federation status, known nodes, connectivity

meshbbs federation nodes
# Output: Lista nodi conosciuti con dettagli

meshbbs federation trust <node_id>
# Aggiunge nodo alla trust list

meshbbs federation untrust <node_id>
# Rimuove nodo dalla trust list

meshbbs federation announce
# Forza annuncio immediato
```

**Tasks:**

- [ ] Implementare comandi CLI
- [ ] Formattazione output user-friendly
- [ ] Integrazione con sistema esistente

### Milestone Criteria

- [ ] Discovery funziona in ambiente test
- [ ] Routing table si popola correttamente
- [ ] CLI commands operativi
- [ ] Documentazione utente

---

## Phase 3: Private Message Relay

### Obiettivo
Permettere l'invio di messaggi privati a utenti su nodi remoti.

### Deliverables

#### 3.1 PM Relay Service

```python
# src/bbs/federation/pm_relay.py

class PMRelayService:
    """Servizio per relay di messaggi privati tra nodi"""

    def __init__(
        self,
        config: FederationConfig,
        transport: FederationTransport,
        router: FederationRouter,
        crypto: FederatedPMCrypto
    ):
        self.config = config
        self.transport = transport
        self.router = router
        self.crypto = crypto
        self.pending_deliveries: Dict[bytes, DeliveryStatus] = {}

    async def send_pm(
        self,
        sender: str,          # alice@local
        recipient: str,       # bob@remote_node
        content: str,
        encrypt: bool = True
    ) -> DeliveryResult:
        """Invia un PM a un utente federato"""

        # Parse recipient
        username, home_node = self._parse_federated_id(recipient)

        # Trova il nodo dove si trova l'utente
        target_node = self.router.find_user(recipient)
        if target_node is None:
            target_node = home_node

        # Ottieni next hop
        next_hop = self.router.get_next_hop(target_node)
        if next_hop is None:
            return DeliveryResult(
                success=False,
                error="No route to destination"
            )

        # Cripta contenuto E2E
        if encrypt:
            recipient_key = await self._get_recipient_key(recipient)
            encrypted_content = self.crypto.encrypt(content, recipient_key)
        else:
            encrypted_content = content.encode('utf-8')

        # Crea messaggio
        msg = PMRelayMessage(
            message_id=self._generate_message_id(),
            sender=sender,
            recipient=recipient,
            timestamp=int(time.time()),
            ttl=self.config.default_ttl,
            encrypted_content=encrypted_content
        )

        # Invia con tracking
        return await self._send_with_tracking(msg, next_hop)

    async def _handle_incoming_relay(self, msg: FederationMessage):
        """Gestisce PM in arrivo per relay o consegna"""
        pm = PMRelayMessage.from_federation_message(msg)

        # Check TTL
        if pm.ttl <= 0:
            await self._send_delivery_fail(msg, "TTL expired")
            return

        # È per un utente locale?
        if self._is_local_user(pm.recipient):
            await self._deliver_locally(pm)
        else:
            # Relay al next hop
            await self._relay_to_next(pm)

    async def _deliver_locally(self, pm: PMRelayMessage):
        """Consegna PM a utente locale"""
        try:
            # Salva nel database locale
            await self.message_service.create_private_message(
                sender=pm.sender,
                recipient=pm.recipient,
                content=pm.encrypted_content,  # L'utente decripta
                federation_id=pm.message_id
            )

            # Invia ACK
            await self._send_delivery_ack(pm)

        except Exception as e:
            await self._send_delivery_fail(pm, str(e))
```

**Tasks:**

- [ ] Implementare `PMRelayService`
- [ ] Integrazione con sistema messaggi esistente
- [ ] Crittografia E2E per PM federati
- [ ] Delivery tracking e retry
- [ ] Test end-to-end

#### 3.2 Key Exchange

```python
# src/bbs/federation/crypto.py

class FederatedKeyExchange:
    """Gestisce scambio chiavi per crittografia E2E"""

    async def get_user_public_key(self, federated_id: str) -> Optional[bytes]:
        """Ottiene chiave pubblica di un utente federato"""

        # Check cache locale
        cached = self.key_cache.get(federated_id)
        if cached:
            return cached

        # Richiedi al nodo home
        username, home_node = self._parse_federated_id(federated_id)

        response = await self.transport.request(
            target=home_node,
            message=UserLookupMessage(
                username=federated_id,
                include_key=True
            ),
            timeout=30
        )

        if response and response.public_key:
            self.key_cache.set(federated_id, response.public_key)
            return response.public_key

        return None
```

**Tasks:**

- [ ] Implementare key exchange
- [ ] Cache chiavi con TTL
- [ ] Gestione key rotation
- [ ] UI per verifica chiavi (fingerprint)

#### 3.3 User Interface Updates

Modifiche all'interfaccia BBS per supportare PM federati:

```
Main Menu > Messages > Compose

To: bob@a1b2
    ^^^^----- nodo remoto

Subject: Hello from another node

[Composing federated message - E2E encrypted]
```

**Tasks:**

- [ ] Aggiornare compose message per federated IDs
- [ ] Mostrare status federazione in inbox
- [ ] Indicatore crittografia E2E
- [ ] Gestire errori delivery

### Milestone Criteria

- [ ] PM tra due nodi funzionano
- [ ] Crittografia E2E verificata
- [ ] Delivery confirmation funzionante
- [ ] UX chiara per utente

---

## Phase 4: Area Synchronization

### Obiettivo
Sincronizzare aree pubbliche tra nodi federati.

### Deliverables

#### 4.1 Sync Engine

```python
# src/bbs/federation/sync.py

class AreaSyncEngine:
    """Motore di sincronizzazione per aree federate"""

    def __init__(
        self,
        config: FederationConfig,
        transport: FederationTransport,
        area_service: AreaService
    ):
        self.config = config
        self.transport = transport
        self.area_service = area_service
        self.sync_state: Dict[str, SyncState] = {}

    async def sync_area(self, area_name: str, remote_node: int):
        """Sincronizza un'area con un nodo remoto"""

        # Ottieni stato locale
        local_state = await self._get_local_state(area_name)

        # Richiedi stato remoto
        response = await self.transport.request(
            target=remote_node,
            message=SyncRequestMessage(
                area=area_name,
                merkle_root=local_state.merkle_root,
                since=local_state.last_sync
            )
        )

        if response.status != 'OK':
            raise SyncError(f"Sync failed: {response.error}")

        # Confronta Merkle roots
        if response.merkle_root == local_state.merkle_root:
            logger.info(f"Area {area_name} already in sync")
            return

        # Trova differenze
        diff_buckets = await self._find_differences(
            area_name,
            remote_node,
            local_state,
            response
        )

        # Richiedi messaggi mancanti
        for bucket in diff_buckets:
            messages = await self._fetch_bucket_messages(
                remote_node,
                area_name,
                bucket
            )
            await self._apply_messages(area_name, messages)

        # Aggiorna stato sync
        self.sync_state[area_name] = SyncState(
            last_sync=int(time.time()),
            merkle_root=await self._compute_merkle_root(area_name)
        )

    async def _apply_messages(self, area: str, messages: List[FederatedMessage]):
        """Applica messaggi ricevuti risolvendo conflitti"""
        for msg in messages:
            existing = await self.area_service.get_by_federation_id(msg.federation_id)

            if existing:
                # Risolvi conflitto
                winner = self._resolve_conflict(existing, msg)
                if winner == msg:
                    await self.area_service.update_from_federation(msg)
            else:
                # Nuovo messaggio
                await self.area_service.create_from_federation(msg)
```

**Tasks:**

- [ ] Implementare `AreaSyncEngine`
- [ ] Merkle tree per diff efficienti
- [ ] Conflict resolution
- [ ] Sync scheduling
- [ ] Bandwidth throttling

#### 4.2 Federated Areas Configuration

```yaml
# config.yaml
federation:
  areas:
    # Aree locali da federare
    - name: "general"
      federate: true
      mode: "bidirectional"  # o "publish" o "subscribe"

    - name: "announcements"
      federate: true
      mode: "publish"  # Solo invio, non ricezione

    # Aree remote da mirrorare
    - name: "news@a1b2"
      federate: true
      mode: "subscribe"  # Solo ricezione
```

**Tasks:**

- [ ] Configurazione per-area
- [ ] Modalità sync (bi/publish/subscribe)
- [ ] Auto-discovery aree remote
- [ ] UI per gestione aree federate

#### 4.3 Vector Clocks Integration

```python
# src/bbs/federation/vector_clock.py

class VectorClockManager:
    """Gestisce vector clocks per ordering distribuito"""

    def __init__(self, local_node_id: int):
        self.local_node = local_node_id
        self.clocks: Dict[str, VectorClock] = {}  # area -> clock

    def get_clock(self, area: str) -> VectorClock:
        if area not in self.clocks:
            self.clocks[area] = VectorClock()
        return self.clocks[area]

    def tick(self, area: str) -> VectorClock:
        """Incrementa clock locale per nuova operazione"""
        clock = self.get_clock(area)
        clock.increment(self.local_node)
        return clock.copy()

    def merge(self, area: str, remote_clock: VectorClock):
        """Merge con clock remoto"""
        self.get_clock(area).merge(remote_clock)
```

**Tasks:**

- [ ] Implementare VectorClock
- [ ] Persistenza clocks
- [ ] Compaction per clocks grandi
- [ ] Visualizzazione per debug

### Milestone Criteria

- [ ] Sync bidirezionale funziona
- [ ] Conflict resolution corretta
- [ ] Performance accettabile
- [ ] Nessuna perdita messaggi

---

## Phase 5: Advanced Features

### Obiettivo
Aggiungere funzionalità avanzate per migliorare l'esperienza utente.

### Deliverables

#### 5.1 User Roaming

```python
# src/bbs/federation/roaming.py

class UserRoamingService:
    """Gestisce roaming utenti tra nodi"""

    async def announce_presence(self, user: str, current_node: int):
        """Annuncia che un utente è attivo su questo nodo"""
        msg = UserRoamingMessage(
            user=user,
            home_node=self._get_home_node(user),
            current_node=current_node,
            timestamp=int(time.time())
        )

        # Broadcast ai nodi interessati
        await self.transport.broadcast(msg)

    async def handle_roaming_announcement(self, msg: UserRoamingMessage):
        """Aggiorna posizione utente nel router"""
        self.router.update_user_location(
            msg.user,
            msg.current_node
        )
```

Permette a un utente registrato su NodeA di connettersi temporaneamente a NodeB e ricevere i suoi PM.

**Tasks:**

- [ ] Implementare roaming service
- [ ] Authentication cross-node
- [ ] PM forwarding durante roaming
- [ ] Timeout e cleanup sessioni

#### 5.2 Gateway to IP Networks

```python
# src/bbs/federation/gateway.py

class IPGatewayService:
    """Gateway opzionale per connettività IP"""

    def __init__(self, config: GatewayConfig):
        self.config = config
        self.websocket_server = None
        self.http_client = None

    async def start(self):
        """Avvia gateway se configurato"""
        if self.config.websocket_enabled:
            self.websocket_server = await self._start_websocket()

        if self.config.http_enabled:
            self.http_client = aiohttp.ClientSession()

    async def relay_via_ip(self, msg: FederationMessage, target: str):
        """Relay messaggio via IP a nodo remoto con connettività"""
        # Per nodi con accesso IP, usa HTTP/WebSocket
        # invece di LoRa per maggiore velocità
        pass
```

Per nodi che hanno anche connettività Internet, permette sync più veloce.

**Tasks:**

- [ ] WebSocket server per real-time
- [ ] HTTP API per sync bulk
- [ ] Auto-detection connettività
- [ ] Fallback a LoRa se IP non disponibile

#### 5.3 Federation Web Dashboard

```
/admin/federation

┌─────────────────────────────────────────────────────┐
│ Federation Status                                    │
├─────────────────────────────────────────────────────┤
│ Node ID: 0xA1B2                                     │
│ Status: ● Active                                     │
│ Known Nodes: 5                                       │
│ Pending Messages: 12                                 │
├─────────────────────────────────────────────────────┤
│ Connected Nodes                                      │
│ ┌─────────┬──────────┬─────────┬─────────────────┐ │
│ │ Node ID │ Name     │ Hops    │ Last Seen       │ │
│ ├─────────┼──────────┼─────────┼─────────────────┤ │
│ │ 0xB1C2  │ Milano   │ 1       │ 2 min ago       │ │
│ │ 0xC1D2  │ Torino   │ 2       │ 5 min ago       │ │
│ │ 0xD1E2  │ Genova   │ 1       │ 1 min ago       │ │
│ └─────────┴──────────┴─────────┴─────────────────┘ │
├─────────────────────────────────────────────────────┤
│ Sync Status                                          │
│ ┌─────────────┬─────────────┬─────────────────────┐ │
│ │ Area        │ Status      │ Last Sync           │ │
│ ├─────────────┼─────────────┼─────────────────────┤ │
│ │ general     │ ● Synced    │ 3 min ago          │ │
│ │ news        │ ● Syncing   │ In progress...     │ │
│ │ tech        │ ○ Pending   │ Scheduled          │ │
│ └─────────────┴─────────────┴─────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

**Tasks:**

- [ ] Endpoint API per status
- [ ] Componenti UI dashboard
- [ ] Real-time updates via WebSocket
- [ ] Grafici statistiche

#### 5.4 Monitoring & Alerting

```python
# src/bbs/federation/monitoring.py

class FederationMonitor:
    """Monitora salute della federazione"""

    async def check_health(self) -> HealthReport:
        """Check completo dello stato federazione"""
        return HealthReport(
            node_status=await self._check_node_status(),
            connectivity=await self._check_connectivity(),
            sync_status=await self._check_sync_status(),
            queue_status=await self._check_queue_status()
        )

    async def _check_connectivity(self) -> ConnectivityReport:
        """Verifica connettività con nodi conosciuti"""
        results = {}
        for node_id in self.router.known_nodes:
            try:
                latency = await self._ping_node(node_id)
                results[node_id] = ConnectivityStatus(
                    reachable=True,
                    latency_ms=latency
                )
            except TimeoutError:
                results[node_id] = ConnectivityStatus(
                    reachable=False,
                    last_seen=self.router.get_last_seen(node_id)
                )
        return ConnectivityReport(nodes=results)
```

**Tasks:**

- [ ] Health check endpoints
- [ ] Alerting per problemi
- [ ] Metriche Prometheus
- [ ] Log strutturato

### Milestone Criteria

- [ ] Roaming funziona tra nodi
- [ ] Gateway IP opzionale operativo
- [ ] Dashboard informativa
- [ ] Monitoring attivo

---

## Phase 6: Production Hardening

### Obiettivo
Rendere il sistema pronto per uso in produzione.

### Deliverables

#### 6.1 Security Audit

- [ ] Code review sicurezza
- [ ] Penetration testing
- [ ] Audit crittografia
- [ ] Vulnerability scan

#### 6.2 Performance Optimization

- [ ] Profiling CPU/memoria
- [ ] Ottimizzazione query DB
- [ ] Caching strategico
- [ ] Load testing

#### 6.3 Documentation

- [ ] Guida utente federazione
- [ ] Guida amministratore
- [ ] Troubleshooting guide
- [ ] API reference completa

#### 6.4 Testing

- [ ] Test coverage > 80%
- [ ] Integration tests multi-nodo
- [ ] Chaos testing (network failures)
- [ ] Long-running stability tests

---

## Implementation Priority Matrix

| Feature | Value | Effort | Priority |
|---------|-------|--------|----------|
| PM Relay | High | Medium | **P0** |
| Node Discovery | High | Low | **P0** |
| Area Sync | Medium | High | **P1** |
| User Roaming | Medium | Medium | **P2** |
| IP Gateway | Low | High | **P3** |
| Web Dashboard | Low | Medium | **P3** |

---

## Risk Assessment

### High Risk

| Risk | Mitigation |
|------|------------|
| Protocol incompatibility | Version negotiation, backwards compat |
| Security vulnerabilities | Audit, fuzzing, bug bounty |
| Data loss during sync | Checksums, retry, idempotency |

### Medium Risk

| Risk | Mitigation |
|------|------------|
| Performance degradation | Monitoring, throttling |
| User experience complexity | UX testing, documentation |
| Maintenance burden | Clean code, good tests |

### Low Risk

| Risk | Mitigation |
|------|------------|
| Feature creep | Strict scope control |
| Documentation debt | Doc alongside code |

---

## Success Metrics

### Functional

- [ ] PM delivery rate > 99% (when nodes reachable)
- [ ] Sync latency < 5 minutes (typical case)
- [ ] Zero data loss in normal operations

### Performance

- [ ] < 10KB/hour federation overhead
- [ ] < 5% CPU usage for federation
- [ ] < 50MB additional memory

### Adoption

- [ ] 3+ community nodes federating
- [ ] Positive user feedback
- [ ] No blocking bugs

---

## Appendix: Dependency Graph

```
Phase 1 (Foundation)
    │
    ├──► Phase 2 (Discovery)
    │         │
    │         ├──► Phase 3 (PM Relay)
    │         │
    │         └──► Phase 4 (Area Sync)
    │                   │
    │                   └──► Phase 5 (Advanced)
    │                             │
    └─────────────────────────────┴──► Phase 6 (Production)
```
