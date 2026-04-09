# MeshBBS Federation Protocol Specification

## Wire Protocol v1.0

**Version:** 1.0
**Date:** January 2026
**Status:** Draft

---

## 1. Overview

Questo documento definisce il protocollo wire per la federazione MeshBBS, ottimizzato per la trasmissione su LoRa/MeshCore con payload limitato a ~300 bytes.

### 1.1 Design Goals

- **Compattezza**: Minimizzare overhead del protocollo
- **Affidabilità**: Gestione errori e retry integrata
- **Estensibilità**: Versioning per future espansioni
- **Sicurezza**: Autenticazione e integrità messaggi

---

## 2. Message Format

### 2.1 Header Comune (8 bytes)

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|    Version    |     Type      |            Flags              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|          Source Node          |        Destination Node       |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

**Campi:**

| Campo | Size | Descrizione |
|-------|------|-------------|
| Version | 1 byte | Versione protocollo (0x01) |
| Type | 1 byte | Tipo messaggio (vedi §2.2) |
| Flags | 2 bytes | Flag bitmap (vedi §2.3) |
| Source Node | 2 bytes | ID nodo sorgente |
| Destination Node | 2 bytes | ID nodo destinazione (0xFFFF = broadcast) |

### 2.2 Message Types

```python
class FederationMessageType:
    # Node Discovery (0x01-0x0F)
    NODE_ANNOUNCE     = 0x01  # Annuncio periodico nodo
    NODE_QUERY        = 0x02  # Richiesta info nodo
    NODE_RESPONSE     = 0x03  # Risposta info nodo
    NODE_GOODBYE      = 0x04  # Nodo si disconnette

    # Synchronization (0x10-0x1F)
    SYNC_REQUEST      = 0x10  # Richiesta sync
    SYNC_RESPONSE     = 0x11  # Risposta sync
    SYNC_DATA         = 0x12  # Dati sync
    SYNC_ACK          = 0x13  # Acknowledgment sync
    SYNC_MERKLE       = 0x14  # Scambio Merkle hash

    # Private Messages (0x20-0x2F)
    PM_RELAY          = 0x20  # Inoltra PM
    PM_DELIVERY_ACK   = 0x21  # Conferma consegna PM
    PM_DELIVERY_FAIL  = 0x22  # Consegna PM fallita
    PM_READ_RECEIPT   = 0x23  # Ricevuta di lettura

    # Public Messages (0x30-0x3F)
    POST_BROADCAST    = 0x30  # Broadcast nuovo post
    POST_REQUEST      = 0x31  # Richiesta post specifico
    POST_RESPONSE     = 0x32  # Risposta con post

    # User Management (0x40-0x4F)
    USER_LOOKUP       = 0x40  # Cerca utente
    USER_INFO         = 0x41  # Info utente
    USER_ROAMING      = 0x42  # Notifica roaming utente

    # Area Management (0x50-0x5F)
    AREA_LIST_REQUEST = 0x50  # Richiesta lista aree
    AREA_LIST_RESPONSE= 0x51  # Lista aree
    AREA_SUBSCRIBE    = 0x52  # Sottoscrivi area
    AREA_UNSUBSCRIBE  = 0x53  # Annulla sottoscrizione

    # Control (0xF0-0xFF)
    PING              = 0xF0  # Ping
    PONG              = 0xF1  # Pong
    ERROR             = 0xFE  # Errore
    RESERVED          = 0xFF  # Riservato
```

### 2.3 Flags

```
Bit 0-3:  Priority (0=low, 15=critical)
Bit 4:    Requires ACK
Bit 5:    Is Fragment (parte di messaggio frammentato)
Bit 6:    More Fragments (altri frammenti seguono)
Bit 7:    Encrypted payload
Bit 8:    Compressed payload
Bit 9:    Signed (include signature)
Bit 10-15: Reserved
```

```python
class FederationFlags:
    PRIORITY_MASK    = 0x000F
    REQUIRES_ACK     = 0x0010
    IS_FRAGMENT      = 0x0020
    MORE_FRAGMENTS   = 0x0040
    ENCRYPTED        = 0x0080
    COMPRESSED       = 0x0100
    SIGNED           = 0x0200
```

---

## 3. Message Definitions

### 3.1 NODE_ANNOUNCE (0x01)

Annuncio periodico di un nodo alla rete federata.

```
Header (8 bytes)
+-- Payload ------------------------------------------+
| Timestamp        | 4 bytes | Unix epoch            |
| Node Name Length | 1 byte  | 0-16                  |
| Node Name        | N bytes | UTF-8                 |
| Capabilities     | 2 bytes | Bitmap                |
| Public Key       | 32 bytes| Ed25519 public key    |
| Area Count       | 1 byte  | 0-8                   |
| Areas            | N bytes | [len(1) + name(max12)]|
| User Count       | 2 bytes | Utenti registrati     |
| Signature        | 64 bytes| Ed25519 signature     |
+----------------------------------------------------+
```

**Dimensione tipica**: 8 + 4 + 1 + 10 + 2 + 32 + 1 + 40 + 2 + 64 = **164 bytes**

### 3.2 SYNC_REQUEST (0x10)

Richiesta di sincronizzazione con un altro nodo.

```
Header (8 bytes)
+-- Payload ------------------------------------------+
| Request ID       | 4 bytes | ID univoco richiesta  |
| Area Name Length | 1 byte  | 0-32                  |
| Area Name        | N bytes | UTF-8                 |
| Since Timestamp  | 4 bytes | Unix epoch            |
| Max Items        | 1 byte  | Max messaggi richiesti|
| Root Hash        | 8 bytes | Merkle root (opz.)    |
+----------------------------------------------------+
```

**Dimensione tipica**: 8 + 4 + 1 + 12 + 4 + 1 + 8 = **38 bytes**

### 3.3 SYNC_RESPONSE (0x11)

Risposta a una richiesta di sincronizzazione.

```
Header (8 bytes)
+-- Payload ------------------------------------------+
| Request ID       | 4 bytes | ID della richiesta    |
| Status           | 1 byte  | 0=OK, altri=errore    |
| Item Count       | 1 byte  | Numero messaggi       |
| Total Available  | 2 bytes | Tot. messaggi dispon. |
| Root Hash        | 8 bytes | Merkle root locale    |
| Has More         | 1 byte  | 1 se ci sono altri    |
+----------------------------------------------------+
```

**Dimensione**: 8 + 4 + 1 + 1 + 2 + 8 + 1 = **25 bytes**

### 3.4 SYNC_DATA (0x12)

Dati di sincronizzazione (singolo messaggio).

```
Header (8 bytes)
+-- Payload ------------------------------------------+
| Request ID       | 4 bytes | ID della richiesta    |
| Sequence         | 2 bytes | Numero sequenza       |
| Federation ID    | 10 bytes| ID globale messaggio  |
| Vector Clock Len | 1 byte  | Lunghezza VC          |
| Vector Clock     | N bytes | VC serializzato       |
| Author Length    | 1 byte  | 0-24                  |
| Author           | N bytes | user@node UTF-8       |
| Content Length   | 2 bytes | Lunghezza contenuto   |
| Content          | N bytes | Contenuto compresso   |
+----------------------------------------------------+
```

**Dimensione tipica**: 8 + 4 + 2 + 10 + 1 + 20 + 1 + 16 + 2 + 150 = **214 bytes**

### 3.5 PM_RELAY (0x20)

Inoltra un messaggio privato attraverso la rete.

```
Header (8 bytes)
+-- Payload ------------------------------------------+
| Message ID       | 10 bytes| ID globale messaggio  |
| Sender Length    | 1 byte  | 0-24                  |
| Sender           | N bytes | user@node UTF-8       |
| Recipient Length | 1 byte  | 0-24                  |
| Recipient        | N bytes | user@node UTF-8       |
| Timestamp        | 4 bytes | Unix epoch            |
| TTL              | 1 byte  | Hop count rimanente   |
| Encrypted Length | 2 bytes | Lunghezza payload E2E |
| Encrypted Data   | N bytes | ChaCha20-Poly1305     |
+----------------------------------------------------+
```

**Dimensione tipica**: 8 + 10 + 1 + 16 + 1 + 16 + 4 + 1 + 2 + 180 = **239 bytes**

### 3.6 PM_DELIVERY_ACK (0x21)

Conferma di consegna di un PM.

```
Header (8 bytes)
+-- Payload ------------------------------------------+
| Message ID       | 10 bytes| ID del messaggio      |
| Delivery Time    | 4 bytes | Unix epoch consegna   |
| Status           | 1 byte  | 0=delivered, 1=queued |
+----------------------------------------------------+
```

**Dimensione**: 8 + 10 + 4 + 1 = **23 bytes**

### 3.7 POST_BROADCAST (0x30)

Broadcast di un nuovo post pubblico.

```
Header (8 bytes)
+-- Payload ------------------------------------------+
| Federation ID    | 10 bytes| ID globale messaggio  |
| Area Name Length | 1 byte  | 0-32                  |
| Area Name        | N bytes | UTF-8                 |
| Author Length    | 1 byte  | 0-24                  |
| Author           | N bytes | user@node UTF-8       |
| Timestamp        | 4 bytes | Unix epoch            |
| Content Length   | 2 bytes | 0-65535               |
| Content          | N bytes | Testo UTF-8 compresso |
| Signature        | 64 bytes| Ed25519 (opzionale)   |
+----------------------------------------------------+
```

**Dimensione tipica**: 8 + 10 + 1 + 12 + 1 + 16 + 4 + 2 + 150 = **204 bytes**

### 3.8 USER_LOOKUP (0x40)

Cerca un utente nella rete federata.

```
Header (8 bytes)
+-- Payload ------------------------------------------+
| Query ID         | 4 bytes | ID query              |
| Username Length  | 1 byte  | 0-24                  |
| Username         | N bytes | user@node UTF-8       |
| Include Profile  | 1 byte  | 1=include profile     |
+----------------------------------------------------+
```

**Dimensione tipica**: 8 + 4 + 1 + 16 + 1 = **30 bytes**

### 3.9 USER_INFO (0x41)

Informazioni su un utente.

```
Header (8 bytes)
+-- Payload ------------------------------------------+
| Query ID         | 4 bytes | ID query originale    |
| Status           | 1 byte  | 0=found, 1=not found  |
| Federated ID Len | 1 byte  | 0-24                  |
| Federated ID     | N bytes | user@node UTF-8       |
| Home Node        | 2 bytes | ID nodo home          |
| Current Node     | 2 bytes | ID nodo corrente      |
| Last Seen        | 4 bytes | Unix epoch            |
| Public Key       | 32 bytes| Chiave pubblica (opz) |
+----------------------------------------------------+
```

**Dimensione tipica**: 8 + 4 + 1 + 1 + 16 + 2 + 2 + 4 + 32 = **70 bytes**

### 3.10 ERROR (0xFE)

Messaggio di errore.

```
Header (8 bytes)
+-- Payload ------------------------------------------+
| Error Code       | 2 bytes | Codice errore         |
| Related Msg ID   | 4 bytes | ID msg che ha causato |
| Details Length   | 1 byte  | 0-100                 |
| Details          | N bytes | Descrizione UTF-8     |
+----------------------------------------------------+
```

**Error Codes**:

```python
class FederationErrorCode:
    SUCCESS           = 0x0000
    UNKNOWN_ERROR     = 0x0001
    MALFORMED_MESSAGE = 0x0002
    UNKNOWN_TYPE      = 0x0003
    NODE_NOT_FOUND    = 0x0004
    USER_NOT_FOUND    = 0x0005
    AREA_NOT_FOUND    = 0x0006
    ACCESS_DENIED     = 0x0007
    RATE_LIMITED      = 0x0008
    SIGNATURE_INVALID = 0x0009
    EXPIRED           = 0x000A
    DUPLICATE         = 0x000B
    QUEUE_FULL        = 0x000C
```

---

## 4. Fragmentation

Per messaggi che superano il limite di ~300 bytes, viene utilizzata la frammentazione.

### 4.1 Fragment Header

Quando i flag `IS_FRAGMENT` o `MORE_FRAGMENTS` sono settati:

```
Header (8 bytes) con IS_FRAGMENT=1
+-- Fragment Header (4 bytes) --+
| Original Msg ID  | 2 bytes    |
| Fragment Index   | 1 byte     |
| Total Fragments  | 1 byte     |
+-- Fragment Payload -----------+
| Data             | N bytes    |
+-------------------------------+
```

### 4.2 Reassembly

```python
class FragmentReassembler:
    """Riassembla messaggi frammentati"""

    def __init__(self, timeout_seconds: int = 60):
        self.pending: Dict[Tuple[int, int], FragmentBuffer] = {}
        self.timeout = timeout_seconds

    def add_fragment(
        self,
        source_node: int,
        msg_id: int,
        index: int,
        total: int,
        data: bytes,
        has_more: bool
    ) -> Optional[bytes]:
        """
        Aggiunge un frammento. Ritorna il messaggio completo
        se tutti i frammenti sono stati ricevuti.
        """
        key = (source_node, msg_id)

        if key not in self.pending:
            self.pending[key] = FragmentBuffer(total)

        buffer = self.pending[key]
        buffer.add(index, data)

        if buffer.is_complete():
            complete = buffer.assemble()
            del self.pending[key]
            return complete

        return None

    def cleanup_expired(self):
        """Rimuove buffer scaduti"""
        now = time.time()
        expired = [
            k for k, v in self.pending.items()
            if now - v.created_at > self.timeout
        ]
        for k in expired:
            del self.pending[k]
```

---

## 5. Compression

I payload possono essere compressi usando LZ4 (veloce, bassa latenza CPU).

### 5.1 Compression Format

Quando il flag `COMPRESSED` è settato:

```
+-- Compressed Payload --------+
| Original Length | 2 bytes    |
| Compressed Data | N bytes    |
+------------------------------+
```

### 5.2 Implementation

```python
import lz4.frame

def compress_payload(data: bytes, min_size: int = 50) -> Tuple[bytes, bool]:
    """
    Comprimi payload se conviene.
    Ritorna (data, was_compressed).
    """
    if len(data) < min_size:
        return data, False

    compressed = lz4.frame.compress(data)

    # Comprimi solo se risparmia spazio
    if len(compressed) + 2 < len(data):
        original_len = len(data).to_bytes(2, 'big')
        return original_len + compressed, True

    return data, False

def decompress_payload(data: bytes) -> bytes:
    """Decomprime payload"""
    original_len = int.from_bytes(data[:2], 'big')
    return lz4.frame.decompress(data[2:])
```

---

## 6. Encryption

### 6.1 Node-to-Node Encryption

Opzionale, per proteggere metadati oltre al contenuto.

```
+-- Encrypted Wrapper ----------+
| Nonce            | 12 bytes   |
| Ciphertext       | N bytes    |
| Auth Tag         | 16 bytes   |
+-------------------------------+
```

Algoritmo: ChaCha20-Poly1305 con chiave derivata da X25519.

### 6.2 Key Derivation

```python
def derive_session_key(
    local_private: bytes,
    remote_public: bytes,
    context: bytes
) -> bytes:
    """
    Deriva chiave di sessione per comunicazione tra nodi.
    """
    # X25519 key exchange
    shared_secret = x25519(local_private, remote_public)

    # HKDF per derivare chiave
    return hkdf_sha256(
        ikm=shared_secret,
        salt=b"MeshBBS-Federation-v1",
        info=context,
        length=32
    )
```

---

## 7. Signatures

### 7.1 Message Signing

Quando il flag `SIGNED` è settato, una firma Ed25519 è aggiunta alla fine:

```
+-- Message --------+
| Header (8 bytes)  |
| Payload (N bytes) |
+-------------------+
| Signature (64 B)  |  <- Ed25519 signature
+-------------------+
```

### 7.2 Signature Coverage

La firma copre:
- Header completo (8 bytes)
- Payload completo (esclusa la firma stessa)

```python
def sign_message(header: bytes, payload: bytes, private_key: bytes) -> bytes:
    """Firma un messaggio federato"""
    to_sign = header + payload
    signature = ed25519_sign(private_key, to_sign)
    return header + payload + signature

def verify_message(message: bytes, public_key: bytes) -> bool:
    """Verifica firma di un messaggio"""
    signature = message[-64:]
    signed_data = message[:-64]
    return ed25519_verify(public_key, signed_data, signature)
```

---

## 8. Protocol Sequences

### 8.1 Node Discovery

```
Node A                          Node B
   |                               |
   |------ NODE_ANNOUNCE --------->|  (broadcast)
   |                               |
   |<----- NODE_ANNOUNCE ----------|  (risposta)
   |                               |
   |------ NODE_QUERY ------------>|  (richiesta dettagli)
   |                               |
   |<----- NODE_RESPONSE ----------|
   |                               |
```

### 8.2 Area Synchronization

```
Node A                          Node B
   |                               |
   |------ SYNC_REQUEST ---------->|  (area="general", since=T)
   |                               |
   |<----- SYNC_RESPONSE ----------|  (status=OK, count=5, root_hash=H)
   |                               |
   |  [se root_hash diverso]       |
   |                               |
   |<----- SYNC_DATA (1/5) --------|
   |<----- SYNC_DATA (2/5) --------|
   |<----- SYNC_DATA (3/5) --------|
   |<----- SYNC_DATA (4/5) --------|
   |<----- SYNC_DATA (5/5) --------|
   |                               |
   |------ SYNC_ACK -------------->|  (received all)
   |                               |
```

### 8.3 Private Message Relay

```
Node A              Node B              Node C
   |                   |                   |
   |  Alice@A vuole PM a Bob@C            |
   |                   |                   |
   |-- PM_RELAY ------>|                   |
   |   (to: bob@c)     |                   |
   |                   |-- PM_RELAY ------>|
   |                   |   (TTL--)         |
   |                   |                   |
   |                   |<-- PM_DELIVERY_ACK|
   |<-- PM_DELIVERY_ACK|                   |
   |                   |                   |
```

### 8.4 User Lookup

```
Node A                          Node B
   |                               |
   |------ USER_LOOKUP ----------->|  (username="bob@c")
   |                               |
   |  [Node B conosce bob@c]       |
   |                               |
   |<----- USER_INFO --------------|  (found, current_node=C)
   |                               |
```

---

## 9. State Machine

### 9.1 Node Connection States

```
              ┌─────────────┐
              │  UNKNOWN    │
              └──────┬──────┘
                     │ receive NODE_ANNOUNCE
                     ▼
              ┌─────────────┐
         ┌────│ DISCOVERED  │────┐
         │    └──────┬──────┘    │
         │           │           │ timeout
  trust  │           │ verify    │
         │           ▼           │
         │    ┌─────────────┐    │
         └───►│  VERIFIED   │────┘
              └──────┬──────┘
                     │ establish session
                     ▼
              ┌─────────────┐
              │  CONNECTED  │◄───┐
              └──────┬──────┘    │ reconnect
                     │           │
          timeout/   │           │
          goodbye    │           │
                     ▼           │
              ┌─────────────┐    │
              │DISCONNECTED │────┘
              └─────────────┘
```

### 9.2 Sync States

```
              ┌─────────────┐
              │    IDLE     │
              └──────┬──────┘
                     │ sync_interval elapsed
                     ▼
              ┌─────────────┐
              │  REQUESTING │
              └──────┬──────┘
                     │ receive SYNC_RESPONSE
                     ▼
              ┌─────────────┐
              │  RECEIVING  │
              └──────┬──────┘
                     │ all data received
                     ▼
              ┌─────────────┐
              │  APPLYING   │
              └──────┬──────┘
                     │ changes applied
                     ▼
              ┌─────────────┐
              │    IDLE     │
              └─────────────┘
```

---

## 10. Error Handling

### 10.1 Timeout Values

| Operation | Timeout | Retry |
|-----------|---------|-------|
| NODE_QUERY | 30s | 2 |
| SYNC_REQUEST | 60s | 3 |
| PM_RELAY | 10s per hop | 5 |
| USER_LOOKUP | 30s | 2 |

### 10.2 Retry Strategy

```python
class ProtocolRetry:
    """Gestione retry per operazioni di protocollo"""

    def __init__(self, operation: str):
        self.operation = operation
        self.config = RETRY_CONFIG[operation]
        self.attempt = 0

    def should_retry(self) -> bool:
        return self.attempt < self.config['max_retries']

    def get_delay(self) -> float:
        # Exponential backoff with jitter
        base = self.config['base_delay']
        delay = base * (2 ** self.attempt)
        jitter = random.uniform(0, delay * 0.1)
        return min(delay + jitter, self.config['max_delay'])

    def record_attempt(self):
        self.attempt += 1

RETRY_CONFIG = {
    'sync': {'max_retries': 3, 'base_delay': 5.0, 'max_delay': 60.0},
    'pm_relay': {'max_retries': 5, 'base_delay': 2.0, 'max_delay': 300.0},
    'lookup': {'max_retries': 2, 'base_delay': 3.0, 'max_delay': 30.0},
}
```

---

## 11. Implementation Notes

### 11.1 Message Serialization

```python
class FederationMessage:
    """Classe base per messaggi federati"""

    def __init__(self):
        self.version = 1
        self.msg_type = 0
        self.flags = 0
        self.source_node = 0
        self.dest_node = 0

    def serialize_header(self) -> bytes:
        """Serializza header comune"""
        return bytes([
            self.version,
            self.msg_type,
            (self.flags >> 8) & 0xFF,
            self.flags & 0xFF,
            (self.source_node >> 8) & 0xFF,
            self.source_node & 0xFF,
            (self.dest_node >> 8) & 0xFF,
            self.dest_node & 0xFF,
        ])

    @classmethod
    def parse_header(cls, data: bytes) -> 'FederationMessage':
        """Parse header da bytes"""
        msg = cls()
        msg.version = data[0]
        msg.msg_type = data[1]
        msg.flags = (data[2] << 8) | data[3]
        msg.source_node = (data[4] << 8) | data[5]
        msg.dest_node = (data[6] << 8) | data[7]
        return msg

    def to_bytes(self) -> bytes:
        """Serializza messaggio completo (override in subclasses)"""
        raise NotImplementedError

    @classmethod
    def from_bytes(cls, data: bytes) -> 'FederationMessage':
        """Parse messaggio da bytes (factory method)"""
        msg_type = data[1]
        parser = MESSAGE_PARSERS.get(msg_type)
        if not parser:
            raise ValueError(f"Unknown message type: {msg_type}")
        return parser(data)
```

### 11.2 Integration with MeshCore

```python
class FederationTransport:
    """Adattatore per inviare messaggi federati via MeshCore"""

    def __init__(self, meshcore_client):
        self.client = meshcore_client
        self.pending_acks: Dict[int, asyncio.Future] = {}

    async def send_message(
        self,
        msg: FederationMessage,
        reliable: bool = True
    ) -> bool:
        """Invia un messaggio federato"""
        data = msg.to_bytes()

        # Frammentazione se necessario
        if len(data) > MAX_PAYLOAD_SIZE:
            fragments = self._fragment(data)
            for frag in fragments:
                await self._send_fragment(frag)
            return True

        # Invio diretto
        if msg.dest_node == BROADCAST_NODE:
            await self.client.broadcast(data)
        else:
            await self.client.send_to_node(msg.dest_node, data)

        if reliable and (msg.flags & FederationFlags.REQUIRES_ACK):
            return await self._wait_for_ack(msg)

        return True

    async def receive_message(self) -> FederationMessage:
        """Riceve un messaggio federato"""
        data = await self.client.receive()
        return FederationMessage.from_bytes(data)
```

---

## 12. Appendices

### A. Constants

```python
# Protocol constants
PROTOCOL_VERSION = 1
MAX_PAYLOAD_SIZE = 290  # bytes, leaving room for LoRa overhead
BROADCAST_NODE = 0xFFFF
MAX_HOPS = 8
DEFAULT_TTL = 5

# Timing constants (seconds)
NODE_ANNOUNCE_INTERVAL = 900   # 15 minutes
SYNC_INTERVAL = 300            # 5 minutes
PM_DELIVERY_TIMEOUT = 3600     # 1 hour
MESSAGE_TTL = 259200           # 72 hours

# Size limits
MAX_USERNAME_LENGTH = 16
MAX_AREA_NAME_LENGTH = 32
MAX_MESSAGE_LENGTH = 4096
MAX_AREAS_PER_NODE = 8
```

### B. Capability Flags

```python
CAP_FEDERATION     = 0x0001  # Supporta federazione base
CAP_PM_RELAY       = 0x0002  # Può inoltrare PM
CAP_AREA_MIRROR    = 0x0004  # Può mirrorare aree remote
CAP_GATEWAY        = 0x0008  # Gateway verso IP/altre reti
CAP_HIGH_BW        = 0x0010  # Connessione veloce disponibile
CAP_COMPRESSION    = 0x0020  # Supporta compressione LZ4
CAP_ENCRYPTION     = 0x0040  # Supporta crittografia N2N
CAP_STORE_FORWARD  = 0x0080  # Ha store-and-forward attivo
```

### C. Glossary

- **FQNA**: Fully Qualified Node Address
- **TTL**: Time To Live (hop count)
- **N2N**: Node-to-Node (encryption)
- **E2E**: End-to-End (encryption)
- **VC**: Vector Clock
