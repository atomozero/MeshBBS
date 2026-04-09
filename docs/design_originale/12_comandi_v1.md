# 12 — Comandi v1: Riepilogo Completo

> Riferimento: Roadmap sezione "Comandi v1"

---

## Tabella Comandi

| Comando | Parametri | Modulo | Fase | Note |
|---------|-----------|--------|------|------|
| `!help` | — | system.py | F5 | Max 180 chars di risposta |
| `!ping` | — | system.py | F5 | Test connettivita' |
| `!info` | — | system.py | F5 | Stato BBS e nodi federati |
| `!nick <n>` | nickname (max 20 chars) | system.py | F5 | Imposta nickname |
| `!nodes` | — | system.py | F5 | Lista peer online/offline |
| `!boards` | — | boards.py | F6 | Lista con conteggio post |
| `!read <board>` | `[pagina]` | boards.py | F6 | 5 post per pagina |
| `!post <board> <testo>` | — | boards.py | F6 | Max 180 chars testo |
| `!inbox` | — | mail.py | F6 | Lista mail non lette |
| `!mail <nick> <testo>` | — | mail.py | F6 | Store-and-forward |
| `!mail read <id>` | — | mail.py | F6 | Legge mail per ID |

**Totale comandi v1: 11**

## Formato Risposte

Tutte le risposte devono rispettare il vincolo di **180 caratteri** (singolo pacchetto LoRa). Ecco le risposte piu' critiche:

### !help (~110 chars)
```
BBS-NomeNodo v1.0.0
!ping !info !nick <n> !nodes
!boards !read <b> !post <b> <txt>
!inbox !mail <dst> <txt>
```

### !boards (~80 chars con 3 board)
```
Bacheche:
Generale (12 post)
Annunci (3 post)
Tecnica (7 post)
```

### !read (~150 chars per 5 post)
```
Mario (5m): Ciao a tutti dalla montagna...
[BBS-B] Luca (2h): Test federazione riuscito!
Anna (1g): Qualcuno riceve da zona nord?
```

### !inbox (~120 chars)
```
Inbox (2 nuove):
[N] #5 Mario (10m)
[N] #4 Luca (2h)
[L] #3 Anna (1g)
```

## Gestione Errori Comandi

| Errore | Risposta |
|--------|----------|
| Comando sconosciuto | `Cmd sconosciuto: !xyz\n!help per la lista` |
| Parametri mancanti | `Uso: !post <board> <testo>` |
| Board non trovata | `Board 'xyz' non trovata. Usa !boards` |
| Mail non trovata | `Mail #99 non trovata` |
| Errore interno | `Errore interno BBS` |

## Flusso Decisionale Dispatcher

```
Messaggio ricevuto
    |
    +-- Non inizia con "!" --> ignora (return None)
    |
    +-- Inizia con "!" --> upsert utente nel DB
        |
        +-- Comando trovato in _HANDLERS --> esegui handler
        |   |
        |   +-- OK --> return risposta
        |   +-- Exception --> return "Errore interno BBS"
        |
        +-- Comando non trovato --> return "Cmd sconosciuto..."
```

## Comandi Futuri (candidati v2)

| Comando | Descrizione | Motivo esclusione v1 |
|---------|-------------|---------------------|
| `!whois <nick>` | Cerca utente su nodi federati | Richiede discovery inter-nodo |
| `!del <id>` | Elimina proprio post | Moderazione non in scope v1 |
| `!ban <nick>` | Ban utente (sysop) | Sistema ruoli non in scope v1 |
| `!addboard <nome>` | Crea board | Rischio spam |
| `!thread <id>` | Rispondi a post | Troppo complesso con MTU 255 |
| `!status` | Status personale | Bassa priorita' |
