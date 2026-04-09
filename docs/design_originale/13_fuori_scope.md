# 13 — Fuori Scope v1

> Riferimento: Roadmap sezione "Fuori Scope v1"

---

## Feature Escluse dalla v1

| Feature | Motivo Esclusione | Candidato per |
|---------|------------------|---------------|
| Moderazione post | Complessita' non necessaria — sysop gestisce manualmente | v2 |
| Creazione board dinamica | Rischio spam — board fisse in v1 | v2 |
| Thread e risposte | Troppo complesso con MTU 255 byte | v2/v3 |
| File e allegati | Impossibile: MTU 255 byte per pacchetto | Mai (limite hardware) |
| Ruoli utente multipli | Solo sysop hardcoded — sistema ruoli in v2 | v2 |
| Web dashboard | Fuori scope: BBS opera interamente via LoRa | v2 (opzionale) |
| Gossip peer list | Discovery transitiva automatica | v2 |
| Canali pubblici come trigger | Solo messaggi diretti in v1 | v2 |

## Analisi Dettagliata

### Moderazione Post
**Problema**: senza sistema di ruoli, chi puo' moderare? Solo il sysop fisicamente sul RPi.
**Workaround v1**: il sysop puo' eliminare post direttamente dal database SQLite.
**Piano v2**: comando `!del <post_id>` per autori dei propri post + `!ban` per sysop.

### Board Dinamiche
**Problema**: qualsiasi utente potrebbe creare board infinite, saturando lo spazio.
**Workaround v1**: le 3 board predefinite coprono i casi d'uso principali.
**Piano v2**: solo sysop puo' creare board tramite CLI locale sul RPi.

### Thread e Risposte
**Problema**: un sistema di thread richiede:
- ID riferimento nel post (`reply_to`)
- UI per mostrare la struttura (indentazione, contesto)
- Piu' dati per pacchetto, violando il limite MTU
**Workaround v1**: gli utenti possono citare manualmente (`@Mario: concordo`).

### File e Allegati
**Problema**: con 180 byte utili per pacchetto, anche un'immagine 1x1 pixel e' troppo grande.
**Realta'**: questa feature e' **impossibile** con il vincolo LoRa attuale. Nessuna frammentazione in v1.
**Nota**: in v2 si potrebbe implementare frammentazione/riassemblaggio, ma la banda LoRa (~300 bps) renderebbe il trasferimento estremamente lento.

### Ruoli Utente
**Problema attuale**: tutti gli utenti hanno gli stessi privilegi. Il sysop e' identificato solo dal fatto di avere accesso fisico al RPi.
**Piano v2**: tabella `roles` con almeno: `user`, `moderator`, `sysop`. La pubkey del sysop configurata in `config.py`.

### Web Dashboard
**Principio**: il BBS opera **esclusivamente** via LoRa mesh. Aggiungere un'interfaccia web introdurrebbe:
- Superficie di attacco (porta HTTP esposta)
- Complessita' di deploy (web server, certificati)
- Incoerenza filosofica (dipendenza da infrastruttura IP)
**Piano v2**: dashboard read-only su localhost per monitoraggio, non per interazione utente.

### Gossip Peer List
**Stato v1**: i peer sono configurati **manualmente** in `FEDERATION_PEERS`.
**Piano v2**: peer discovery tramite gossip — ogni nodo condivide la sua lista peer con i peer, permettendo scoperta transitiva. Richiede:
- Nuovo tipo pacchetto federazione (`TYPE_PEER_LIST = 0x05`)
- Logica di merge liste con deduplicazione
- TTL per limitare la propagazione

### Canali Pubblici
**Stato v1**: il BBS risponde solo a **messaggi diretti** (DM) indirizzati al nodo companion.
**Piano v2**: il companion potrebbe ascoltare anche canali pubblici MeshCore, permettendo comandi BBS in canali condivisi. Richiede:
- Verifica supporto nella libreria meshcore Python
- Gestione spam (chiunque nel canale potrebbe inviare comandi)
- Risposte in canale vs DM (privacy)
