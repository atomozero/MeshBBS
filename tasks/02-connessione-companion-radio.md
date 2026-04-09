# Task 02: Connessione Base al Companion Radio

## Stato: ✅ COMPLETATO

> **Nota**: L'interfaccia, il mock e la connessione reale via meshcore_py sono stati implementati. Il sistema usa automaticamente il mock se meshcore_py non è disponibile o la connessione hardware fallisce.

## Analisi

### Contesto
La connessione al companion radio è il cuore del sistema BBS. Il companion radio (dispositivo LoRa con firmware USB Serial Companion) funge da gateway tra la rete mesh MeshCore e il software BBS in esecuzione sul Raspberry Pi.

### Architettura della Connessione

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Rete LoRa     │◄───────►│ Companion Radio │◄───────►│  Software BBS   │
│   MeshCore      │   RF    │  (Heltec V3)    │   USB   │  (Raspberry Pi) │
└─────────────────┘         └─────────────────┘  Serial └─────────────────┘
```

### Implementazione Attuale

**File creati**:
- `src/meshcore/connection.py` - Classi di connessione
- `src/meshcore/protocol.py` - Definizioni protocollo
- `src/meshcore/messages.py` - Dataclass per messaggi

**Classi implementate**:
- `BaseMeshCoreConnection` - Interfaccia astratta
- `MeshCoreConnection` - Placeholder per connessione reale
- `MockMeshCoreConnection` - Mock per sviluppo/test

---

## Task Dettagliati

### Task 2.1: Studio della Libreria meshcore_py
**Stato**: ⏳ Da completare con hardware

**Sotto-attività**:
- [ ] Clonare repository: `git clone https://github.com/fdlamotte/meshcore_py`
- [x] Identificare API necessaria (documentata)
- [ ] Testare con hardware reale

---

### Task 2.2: Creazione Modulo Connection
**Stato**: ✅ COMPLETATO

**File**: `src/meshcore/connection.py`

**Implementato**:
```python
class BaseMeshCoreConnection(ABC):
    def __init__(self):
        self.identity: Optional[Identity] = None
        self.connected: bool = False
        self._message_callbacks: List[MessageCallback] = []
        self._running: bool = False

    @abstractmethod
    async def connect(self) -> bool: ...
    @abstractmethod
    async def disconnect(self) -> None: ...
    @abstractmethod
    async def send_message(self, destination: str, text: str, use_path: bool = True) -> bool: ...
    @abstractmethod
    async def send_advert(self, flood: bool = False) -> bool: ...
    @abstractmethod
    async def receive(self) -> Optional[Message]: ...
```

**Verifica**: ✅ Test passati (15 test in test_connection.py)

---

### Task 2.3: Implementazione Connessione Seriale
**Stato**: ⏳ In attesa hardware (Mock implementato)

**Mock implementato** per sviluppo:
```python
class MockMeshCoreConnection(BaseMeshCoreConnection):
    async def connect(self) -> bool:
        self.connected = True
        return True

    async def inject_message(self, sender_key: str, text: str, ...):
        # Per test: inietta messaggi nella coda
```

---

### Task 2.4: Gestione Identità del Nodo BBS
**Stato**: ✅ COMPLETATO (Mock)

**Implementato**:
```python
@dataclass
class Identity:
    public_key: str
    name: str
    node_type: NodeType = NodeType.ROOM

    @property
    def short_key(self) -> str:
        return self.public_key[:8]
```

---

### Task 2.5: Implementazione Lettura Asincrona
**Stato**: ✅ COMPLETATO (Mock)

**Implementato**:
```python
async def receive(self) -> Optional[Message]:
    try:
        message = await asyncio.wait_for(
            self._message_queue.get(),
            timeout=1.0,
        )
        await self._notify_message(message)
        return message
    except asyncio.TimeoutError:
        return None
```

---

### Task 2.6: Implementazione Scrittura
**Stato**: ✅ COMPLETATO (Mock)

**Implementato**:
```python
async def send_message(self, destination: str, text: str, use_path: bool = True) -> bool:
    if not self.connected:
        return False
    message = Message(
        sender_key=self.identity.public_key,
        recipient_key=destination,
        text=text,
        timestamp=datetime.utcnow(),
    )
    self._sent_messages.append(message)
    return True
```

---

### Task 2.7: Implementazione Riconnessione Automatica
**Stato**: ⏳ Da implementare con hardware

---

### Task 2.8: Creazione Loop Principale di Comunicazione
**Stato**: ✅ COMPLETATO

**File**: `src/bbs/core.py`

```python
async def run(self) -> None:
    while self._running:
        try:
            message = await self.connection.receive()
            if message:
                response = await self.handle_message(message)
                if response:
                    await self.connection.send_message(
                        destination=message.sender_key,
                        text=response,
                    )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.exception(f"Error in main loop: {e}")
            await asyncio.sleep(1)
```

---

### Task 2.9: Test di Integrazione con Companion Radio
**Stato**: ✅ COMPLETATO (con Mock)

**Test implementati** in `tests/test_connection.py`:
- test_connect
- test_disconnect
- test_send_message
- test_send_message_not_connected
- test_send_advert
- test_receive_timeout
- test_inject_and_receive
- test_clear_sent_messages

**Verifica**: ✅ 15 test passati

---

### Task 2.10: Invio Advert del Nodo BBS
**Stato**: ✅ COMPLETATO (Mock)

**Implementato** in `src/bbs/core.py`:
```python
async def _periodic_advert(self) -> None:
    interval = self.config.advert_interval_minutes * 60
    while self._running:
        await asyncio.sleep(interval)
        if self._running:
            await self.connection.send_advert(flood=True)
```

---

## Checklist Finale

- [x] Interfaccia connessione definita (BaseMeshCoreConnection)
- [x] Mock implementation per sviluppo/test
- [x] Gestione identità implementata
- [x] Lettura/scrittura asincrona (mock)
- [x] Loop principale operativo
- [x] Test passati (17 test)
- [x] Connessione reale via meshcore_py
- [x] Fallback automatico a mock se hardware non disponibile
- [ ] Test end-to-end con hardware reale

---

## Prossimi Passi (con hardware)

1. Installare meshcore_py
2. Implementare `MeshCoreConnection` reale
3. Testare connessione seriale
4. Implementare riconnessione automatica
5. Test end-to-end con rete mesh

---

## Risorse Utili

- meshcore_py: https://github.com/fdlamotte/meshcore_py
- meshcore-cli (esempio d'uso): https://github.com/fdlamotte/meshcore-cli
- pyserial documentation: https://pyserial.readthedocs.io/
- Python asyncio: https://docs.python.org/3/library/asyncio.html

---

## Note Tecniche

### Parametri Porta Seriale
```python
SERIAL_CONFIG = {
    "baudrate": 115200,
    "bytesize": serial.EIGHTBITS,
    "parity": serial.PARITY_NONE,
    "stopbits": serial.STOPBITS_ONE,
    "timeout": 1.0,
    "write_timeout": 1.0
}
```

### Codici Tipo Payload (implementati in protocol.py)
```python
class PacketType(IntEnum):
    REQ = 0x00
    RESPONSE = 0x01
    TXT_MSG = 0x02
    ACK = 0x03
    ADVERT = 0x04
    GRP_TXT = 0x05
    GRP_DATA = 0x06
    ANON_REQ = 0x07
    PATH = 0x08
```
