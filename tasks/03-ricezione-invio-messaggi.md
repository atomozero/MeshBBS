# Task 03: Ricezione e Invio Messaggi

## Stato: ✅ PARZIALMENTE COMPLETATO (Mock Implementation)

> **Nota**: L'interfaccia e il mock sono stati implementati. La connessione reale via meshcore_py è in attesa dell'hardware.

## Analisi

### Contesto
La gestione dei messaggi e la funzionalita core del BBS. Il sistema deve:
- Ricevere messaggi diretti (TXT_MSG) destinati al nodo BBS
- Inviare risposte ai client MeshCore
- Gestire ACK per conferma ricezione
- Supportare messaggi di canale/gruppo (GRP_TXT) in futuro

### Flusso Messaggi MeshCore

```
┌──────────┐     Flood/Path    ┌──────────┐     USB Serial    ┌─────────┐
│  Client  │ ─────────────────►│ Companion│ ─────────────────►│   BBS   │
│ MeshCore │                   │  Radio   │                   │ Software│
└──────────┘                   └──────────┘                   └─────────┘
     ▲                                                              │
     │                         ┌──────────┐                         │
     └─────────────────────────│ Risposta │◄────────────────────────┘
           Path/Flood          └──────────┘
```

### Tipi di Messaggio da Gestire

| Tipo | Codice | Direzione | Descrizione |
|------|--------|-----------|-------------|
| TXT_MSG | 0x02 | IN/OUT | Messaggio di testo diretto |
| ACK | 0x03 | IN/OUT | Conferma ricezione |
| ADVERT | 0x04 | IN | Annuncio di altri nodi |
| GRP_TXT | 0x05 | IN | Messaggio canale (futuro) |

### Struttura Messaggio MeshCore
Un messaggio MeshCore contiene:
- **Destination hash**: Hash della chiave pubblica destinatario
- **Source hash**: Hash della chiave pubblica mittente
- **MAC**: Message Authentication Code
- **Encrypted payload**: Timestamp + contenuto cifrato

### Routing
- **Primo messaggio**: Flood (broadcast attraverso tutti i repeater)
- **Messaggi successivi**: Path routing (percorso memorizzato dal delivery report)
- **Retry**: 3 tentativi, poi fallback a flood

### Sfide Identificate
1. Parsing corretto dei pacchetti binari
2. Decifratura del payload (crittografia end-to-end)
3. Gestione timeout e retry per messaggi non confermati
4. Queue di messaggi in uscita con rate limiting
5. Correlazione ACK con messaggi inviati
6. Gestione delivery report per apprendimento path

---

## Task Dettagliati

### Task 3.1: Creazione Modulo Protocol
**Descrizione**: Creare il modulo per encoding/decoding dei pacchetti MeshCore

**Sotto-attivita**:
- [ ] Creare file `meshcore/protocol.py`
- [ ] Definire costanti per tipi di payload:
  ```python
  PAYLOAD_TYPE_REQ = 0x00
  PAYLOAD_TYPE_RESPONSE = 0x01
  PAYLOAD_TYPE_TXT_MSG = 0x02
  PAYLOAD_TYPE_ACK = 0x03
  PAYLOAD_TYPE_ADVERT = 0x04
  PAYLOAD_TYPE_GRP_TXT = 0x05
  ```
- [ ] Creare classe `MeshCorePacket` per rappresentare un pacchetto
- [ ] Implementare metodo `parse(data: bytes) -> MeshCorePacket`
- [ ] Implementare metodo `serialize() -> bytes`
- [ ] Aggiungere validazione checksum/CRC

**Verifica**: Parsing di pacchetti raw restituisce oggetti strutturati

---

### Task 3.2: Implementazione Classe Message
**Descrizione**: Creare la classe per rappresentare un messaggio MeshCore

**Sotto-attivita**:
- [ ] Creare file `meshcore/messages.py`
- [ ] Definire dataclass `Message`:
  ```python
  @dataclass
  class Message:
      sender_key: str        # Chiave pubblica mittente
      recipient_key: str     # Chiave pubblica destinatario
      text: str              # Contenuto del messaggio
      timestamp: datetime    # Timestamp del messaggio
      message_id: str        # ID univoco
      hops: int = 0          # Numero di hop
      rssi: int = 0          # Signal strength
      snr: float = 0.0       # Signal-to-noise ratio
  ```
- [ ] Implementare metodo `from_packet(packet: MeshCorePacket)`
- [ ] Implementare metodo `to_packet() -> MeshCorePacket`
- [ ] Aggiungere metodi di utility (`is_direct`, `is_group`, etc.)

**Verifica**: Conversione bidirezionale tra Message e MeshCorePacket

---

### Task 3.3: Implementazione Ricezione Messaggi
**Descrizione**: Implementare la logica di ricezione e parsing dei messaggi

**Sotto-attivita**:
- [ ] Creare metodo `receive_message()` in connection.py:
  ```python
  async def receive_message(self) -> Optional[Message]:
      packet = await self._receive_packet()
      if packet and packet.type == PAYLOAD_TYPE_TXT_MSG:
          return Message.from_packet(packet)
      return None
  ```
- [ ] Implementare decifratura del payload (se necessario)
- [ ] Estrarre mittente dalla chiave pubblica
- [ ] Estrarre timestamp dal payload
- [ ] Loggare messaggi ricevuti con dettagli (sender, hops, rssi)
- [ ] Gestire messaggi malformati senza crash

**Verifica**: Messaggi ricevuti da client MeshCore sono correttamente parsati

---

### Task 3.4: Implementazione Invio Messaggi
**Descrizione**: Implementare la logica di invio messaggi

**Sotto-attivita**:
- [ ] Creare metodo `send_message()`:
  ```python
  async def send_message(
      self,
      destination: str,  # Chiave pubblica destinatario
      text: str,
      use_path: bool = True
  ) -> bool:
  ```
- [ ] Implementare costruzione del pacchetto TXT_MSG
- [ ] Cifrare il payload con la chiave del destinatario
- [ ] Aggiungere timestamp corrente al payload
- [ ] Implementare invio con path se disponibile, altrimenti flood
- [ ] Restituire successo/fallimento
- [ ] Loggare messaggi inviati

**Verifica**: Messaggi inviati sono ricevuti correttamente dai client MeshCore

---

### Task 3.5: Gestione ACK
**Descrizione**: Implementare gestione delle conferme di ricezione

**Sotto-attivita**:
- [ ] Creare struttura per tracking messaggi in attesa di ACK:
  ```python
  self._pending_acks: Dict[str, PendingMessage] = {}
  ```
- [ ] Implementare invio ACK alla ricezione di un messaggio:
  ```python
  async def _send_ack(self, message: Message):
      ack_packet = self._build_ack_packet(message)
      await self.send_raw(ack_packet)
  ```
- [ ] Implementare ricezione e processing degli ACK
- [ ] Correlazione ACK con messaggio originale tramite message_id
- [ ] Aggiornare stato messaggio (pending -> delivered)
- [ ] Rimuovere messaggi confermati dalla pending queue

**Verifica**: ACK ricevuti aggiornano correttamente lo stato dei messaggi

---

### Task 3.6: Implementazione Retry Logic
**Descrizione**: Implementare logica di retry per messaggi non confermati

**Sotto-attivita**:
- [ ] Definire costanti di retry:
  ```python
  MAX_RETRIES = 3
  RETRY_TIMEOUT = 30  # secondi
  FINAL_RETRY_FLOOD = True  # Ultimo retry come flood
  ```
- [ ] Creare task periodico per check timeout:
  ```python
  async def _check_pending_messages(self):
      now = datetime.now()
      for msg_id, pending in self._pending_acks.items():
          if (now - pending.sent_at).seconds > RETRY_TIMEOUT:
              if pending.retries < MAX_RETRIES:
                  await self._retry_message(pending)
              else:
                  self._handle_delivery_failure(pending)
  ```
- [ ] Implementare reset del path e flood su ultimo retry
- [ ] Callback per notifica fallimento definitivo
- [ ] Loggare tutti i retry

**Verifica**: Messaggi non confermati vengono re-inviati fino a MAX_RETRIES

---

### Task 3.7: Gestione Path e Routing
**Descrizione**: Implementare gestione dei path per routing ottimizzato

**Sotto-attivita**:
- [ ] Creare struttura per storage dei path:
  ```python
  self._known_paths: Dict[str, List[str]] = {}  # dest_key -> [repeater_keys]
  ```
- [ ] Implementare apprendimento path dal delivery report:
  ```python
  def _learn_path(self, dest_key: str, path: List[str]):
      self._known_paths[dest_key] = path
  ```
- [ ] Implementare lookup path per destinazione
- [ ] Invalidare path dopo N fallimenti consecutivi
- [ ] Salvare/caricare path da file per persistenza
- [ ] Loggare path utilizzati/appresi

**Verifica**: Messaggi successivi usano path appresi invece di flood

---

### Task 3.8: Rate Limiting e Queue Management
**Descrizione**: Implementare rate limiting per rispettare duty cycle LoRa

**Sotto-attivita**:
- [ ] Definire limiti di rate (basati su duty cycle regione):
  ```python
  # EU: 10% duty cycle a 869.525MHz
  MIN_MESSAGE_INTERVAL = 1.0  # secondi tra messaggi
  MAX_MESSAGES_PER_MINUTE = 30
  ```
- [ ] Creare queue per messaggi in uscita:
  ```python
  self._outgoing_queue: asyncio.Queue[Message] = asyncio.Queue()
  ```
- [ ] Implementare worker che processa la queue rispettando i limiti
- [ ] Prioritizzare ACK rispetto ai messaggi normali
- [ ] Loggare quando il rate limiting interviene
- [ ] Callback per notifica queue piena

**Verifica**: Messaggi vengono inviati rispettando l'intervallo minimo

---

### Task 3.9: Gestione Advert Ricevuti
**Descrizione**: Processare gli advert ricevuti da altri nodi

**Sotto-attivita**:
- [ ] Implementare handler per PAYLOAD_TYPE_ADVERT:
  ```python
  async def _handle_advert(self, packet: MeshCorePacket):
      advert = Advert.from_packet(packet)
      # Memorizza/aggiorna info sul nodo
      self._update_contact(advert)
  ```
- [ ] Creare classe `Advert` per rappresentare un annuncio
- [ ] Estrarre informazioni: nome, chiave pubblica, posizione, tipo
- [ ] Memorizzare contatti conosciuti:
  ```python
  self._contacts: Dict[str, Contact] = {}
  ```
- [ ] Aggiornare timestamp "last_seen" dei contatti
- [ ] Callback per notifica nuovo contatto

**Verifica**: Nuovi nodi che inviano advert vengono registrati

---

### Task 3.10: Test End-to-End Messaggistica
**Descrizione**: Creare test completi per il sistema di messaggistica

**Sotto-attivita**:
- [ ] Creare script `test_messaging.py`
- [ ] Test 1: Ricezione messaggio da client MeshCore
  ```python
  async def test_receive():
      conn = MeshCoreConnection("/dev/ttyUSB0")
      await conn.connect()
      print("In attesa di messaggi...")
      msg = await conn.receive_message()
      print(f"Ricevuto: {msg.text} da {msg.sender_key[:8]}...")
  ```
- [ ] Test 2: Invio risposta al mittente
- [ ] Test 3: Verifica ricezione ACK
- [ ] Test 4: Test retry su mancato ACK (simulato)
- [ ] Test 5: Test rate limiting con burst di messaggi
- [ ] Documentare risultati dei test

**Verifica**: Tutti i test passano e la messaggistica e bidirezionale

---

## Checklist Finale

- [x] Modulo protocol.py creato
- [x] Classe Message implementata
- [x] Ricezione messaggi funzionante (mock)
- [x] Invio messaggi funzionante (mock)
- [ ] Gestione ACK implementata (attesa hardware)
- [ ] Retry logic operativa (attesa hardware)
- [ ] Path routing implementato (attesa hardware)
- [ ] Rate limiting attivo (attesa hardware)
- [x] Advert processing funzionante (mock)
- [x] Test con Mock completati (15 test)
- [ ] Test end-to-end con hardware

---

## Risorse Utili

- MeshCore Packet.h: https://github.com/meshcore-dev/MeshCore/blob/main/src/Packet.h
- meshcore_py source: https://github.com/fdlamotte/meshcore_py
- meshcore.js (reference): https://github.com/liamcottle/meshcore.js
- LoRa Duty Cycle: https://www.thethingsnetwork.org/docs/lorawan/duty-cycle/

---

## Note Tecniche

### Formato Messaggio TXT_MSG
```
┌───────────────┬───────────────┬─────────┬─────────────────────────┐
│ Dest Hash     │ Src Hash      │   MAC   │  Encrypted Payload      │
│ (4 bytes)     │ (4 bytes)     │(4 bytes)│  (timestamp + text)     │
└───────────────┴───────────────┴─────────┴─────────────────────────┘
```

### Formato ACK
```
┌───────────────┬───────────────┬─────────┬──────────────┐
│ Dest Hash     │ Src Hash      │   MAC   │  Message ID  │
│ (4 bytes)     │ (4 bytes)     │(4 bytes)│  (4 bytes)   │
└───────────────┴───────────────┴─────────┴──────────────┘
```

### Esempio Completo Ricezione/Invio
```python
import asyncio
from meshcore.connection import MeshCoreConnection
from meshcore.messages import Message

async def echo_bot():
    """Bot che risponde a ogni messaggio ricevuto."""
    conn = MeshCoreConnection("/dev/ttyUSB0")
    await conn.connect()
    print(f"[BBS] Online - {conn.identity.name}")

    while True:
        try:
            # Attendi messaggio
            msg = await conn.receive_message()

            if msg:
                print(f"[RX] {msg.sender_key[:8]}: {msg.text}")

                # Prepara risposta
                response = f"[BBS] Echo: {msg.text}"

                # Invia risposta
                success = await conn.send_message(
                    destination=msg.sender_key,
                    text=response
                )

                if success:
                    print(f"[TX] Risposta inviata")
                else:
                    print(f"[TX] Invio fallito")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[ERR] {e}")

    await conn.disconnect()

if __name__ == "__main__":
    asyncio.run(echo_bot())
```

### Limiti Tecnici da Considerare
| Parametro | Valore | Note |
|-----------|--------|------|
| Max payload | ~200 bytes | Limite LoRa |
| Duty cycle EU | 10% | A 869.525MHz |
| Timeout ACK | 30s | Configurabile |
| Max retries | 3 | Poi fallback flood |
| Max hops | 64 | Limite firmware |
