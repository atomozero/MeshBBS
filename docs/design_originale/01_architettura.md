# 01 — Architettura e Principi di Design

> Riferimento: Roadmap sezione 1

---

## Descrizione

MeshCore BBS e' un sistema bulletin board distribuito e federato che opera su rete LoRa mesh **senza dipendenza da infrastrutture Internet**. Il firmware del Companion radio rimane originale e non modificato: tutta la logica BBS risiede nel software Python sul Raspberry Pi.

## Principi Fondamentali

| Principio | Dettaglio |
|-----------|-----------|
| Firmware intoccabile | MeshCore originale — zero modifiche al layer radio |
| Logica centralizzata | Tutto il codice BBS gira sul Raspberry Pi in Python `asyncio` |
| Connessione TCP WiFi | Heltec V3 <-> RPi via porta 5000 su LAN locale |
| Database federation-ready | Schema SQLite progettato per la federazione fin dalla v1 |
| Push federazione | Sincronizzazione immediata tra nodi BBS via messaggi diretti LoRa |
| Autenticazione implicita | Identita' basata su pubkey crittografica MeshCore (nessun login/password) |

## Schema a Layer

```
+-----------------------------------------------------------+
|              RASPBERRY PI W (Software BBS)                |
|  main.py - dispatcher.py - queue.py - database.py        |
|  modules/: users - boards - mail - federation - system    |
|                                                           |
|  config.py -> COMPANION_HOST=192.168.1.50                 |
|               COMPANION_PORT=5000                         |
+---------------------------+-------------------------------+
                            | TCP socket (WiFi LAN)
+---------------------------v-------------------------------+
|         HELTEC V3 — MeshCore companion_radio_wifi         |
|         ESP32 + SX1262 - 868 MHz EU - IP fisso            |
+---------------------------+-------------------------------+
                            | LoRa 868 MHz
              +-------------v-------------+
              |       Mesh Network        |
              |  Repeater ... Node        |
              |  BBS-B ... BBS-C          |  <- federazione
              +---------------------------+
```

## Vincoli Architetturali

### Vincolo MTU
- **MTU fisico MeshCore**: 255 byte per pacchetto
- **Header protocollo MeshCore**: ~20-30 byte
- **Payload utile**: ~225 byte
- **Prefisso risposta BBS** (es. `[BBS] `): ~10 byte
- **Testo utente massimo**: ~180 caratteri per singolo pacchetto

### Vincolo Rate Limit
- Il protocollo LoRa ha duty cycle limitato
- MeshCore impone un rate limit di circa **3 messaggi/minuto** per contatto
- La coda con priorita' (OutboxQueue) gestisce questo vincolo

### Vincolo Single-Packet
- Ogni risposta BBS deve stare in **un singolo pacchetto** (no frammentazione in v1)
- Questo limita la complessita' dei comandi e la quantita' di dati restituibili

## Flusso Dati Tipico

```
Utente LoRa
    |
    | messaggio diretto: "!boards"
    v
Heltec V3 (companion) --> TCP --> RPi (BBS)
                                    |
                                    | dispatcher.py -> boards.py
                                    | query SQLite
                                    | risposta in OutboxQueue
                                    |
RPi (BBS) --> TCP --> Heltec V3 --> LoRa --> Utente
```

## Flusso Federazione

```
Utente su BBS-A: "!post Generale ciao"
    |
BBS-A salva post localmente
    |
BBS-A costruisce pacchetto federazione (0xBB + TYPE_POST)
    |
BBS-A invia a tutti i peer configurati (BBS-B, BBS-C)
    |
BBS-B riceve, controlla anti-loop (federation_seen)
    |
BBS-B salva post con is_local=0
```

## Note di Design

- **Nessun discovery automatico in v1**: i peer sono configurati staticamente in `FEDERATION_PEERS`
- **Store-and-forward**: le mail per destinatari sconosciuti vengono inoltrate ai peer
- **Idempotenza**: il `global_id` su post e mail previene duplicazioni in scenari di re-invio
- **Graceful degradation**: se un peer e' offline, il BBS continua a funzionare localmente
