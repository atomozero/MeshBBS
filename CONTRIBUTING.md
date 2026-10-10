# Contributing to MeshBBS

Grazie per il tuo interesse nel contribuire a MeshBBS! Questo documento fornisce linee guida per contribuire al progetto.

## Come Contribuire

### Segnalare Bug

1. Verifica che il bug non sia già stato segnalato nelle [Issues](https://github.com/meshbbs/meshbbs/issues)
2. Crea una nuova issue con:
   - Titolo descrittivo
   - Passi per riprodurre il problema
   - Comportamento atteso vs comportamento osservato
   - Versione di MeshBBS, Python, sistema operativo
   - Log rilevanti (se disponibili)

### Proporre Nuove Funzionalità

1. Apri una issue con il tag `enhancement`
2. Descrivi la funzionalità proposta
3. Spiega perché sarebbe utile
4. Attendi feedback prima di iniziare l'implementazione

### Contribuire Codice

1. **Fork** il repository
2. **Crea un branch** per la tua modifica:
   ```bash
   git checkout -b feature/nome-funzionalita
   # oppure
   git checkout -b fix/descrizione-bug
   ```
3. **Scrivi codice** seguendo le convenzioni del progetto
4. **Scrivi test** per le nuove funzionalità
5. **Esegui i test** per verificare che tutto funzioni:
   ```bash
   pytest tests/ -v
   ```
6. **Commit** con messaggi descrittivi
7. **Push** al tuo fork
8. Apri una **Pull Request**

## Convenzioni Codice

### Python

- Usa **Python 3.11+**
- Segui **PEP 8** per lo stile
- Usa **type hints** dove possibile
- Documenta funzioni e classi con docstring
- Formatta il codice con **black**:
  ```bash
  black src/ tests/
  ```
- Ordina gli import con **isort**:
  ```bash
  isort src/ tests/
  ```

### TypeScript/React (Web Interface)

- Usa **TypeScript** strict mode
- Componenti funzionali con hooks
- Nomi componenti in PascalCase
- Props tipizzate con interface
- Formatta con **Prettier** (configurato in `.prettierrc`)

### Commit Messages

Usa messaggi di commit chiari e descrittivi:

```
tipo: breve descrizione

Descrizione più dettagliata se necessaria.
Spiega il "perché" della modifica.

Closes #123
```

Tipi comuni:
- `feat`: Nuova funzionalità
- `fix`: Correzione bug
- `docs`: Solo documentazione
- `style`: Formattazione, nessun cambio logica
- `refactor`: Refactoring senza nuove funzionalità
- `test`: Aggiunta o modifica test
- `chore`: Manutenzione, configurazione

### Branch Naming

- `feature/nome-funzionalita` - Nuove funzionalità
- `fix/descrizione-bug` - Correzioni bug
- `docs/cosa-documentato` - Documentazione
- `refactor/cosa-refactored` - Refactoring

## Struttura Progetto

```
meshbbs/
├── src/
│   ├── launcher.py    # Launcher unificato (BBS + web leggero)
│   ├── bbs/           # Logica BBS core, comandi, modelli, repository
│   ├── meshbbs_radio/ # Comunicazione radio (meshcore_py)
│   ├── web_light/     # Pannello admin leggero (bottle.py)
│   ├── web/           # API REST FastAPI e WebSocket (legacy)
│   └── utils/         # Utility condivise
├── tests/             # Test suite
├── web/               # Frontend React
├── deploy/            # Script deployment
└── docs/              # Documentazione
```

## Setup Ambiente Sviluppo

### Backend

```bash
# Clone
git clone https://github.com/meshbbs/meshbbs.git
cd meshbbs

# Virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# oppure: venv\Scripts\activate  # Windows

# Dipendenze
pip install -r requirements.txt

# Test
pytest tests/ -v

# Avvio senza hardware (radio simulata, SOLO sviluppo)
cd src
export ADMIN_PASSWORD='una-password-di-sviluppo'
python launcher.py --mock --debug
```

Senza `--mock` il BBS non usa mai la radio simulata: si avvia e ritenta la radio reale.
Il login web richiede sempre `ADMIN_PASSWORD` impostata (nessuna password predefinita).

### Convenzioni per i comandi BBS

- I comandi usano il prefisso `!` (anche negli esempi, nei suggerimenti e in `usage`)
- Le risposte viaggiano su LoRa in chunk da 140 byte: mantienile brevi
- Per argomenti numerici usa `parse_int` di `bbs/commands/helpers.py` (rifiuta cifre Unicode e valori fuori scala)
- Per cercare utenti e aree usa i repository (`UserRepository`, `AreaRepository`): la ricerca è esatta,
  case-insensitive, senza wildcard `LIKE`; i prefissi di chiave richiedono almeno 8 caratteri
- L'identità utente è la chiave canonica (prefisso di 12 caratteri esadecimali minuscoli, vedi
  `bbs/services/user_keys.py`): non salvare chiavi complete a 64 caratteri come `public_key`
- Aggiungi il comando a una categoria di `CATEGORIES` in `help_cmd.py`; per renderlo
  utilizzabile dai moderatori imposta `moderator_allowed = True` accanto a `admin_only = True`
- Ogni output HTML del pannello web deve passare per l'escaping, ogni POST richiede il token CSRF

### Frontend

```bash
cd web

# Dipendenze
npm install

# Sviluppo
npm run dev

# Test
npm test

# Build
npm run build
```

## Test

### Eseguire i Test

```bash
# Tutti i test
pytest tests/ -v

# Solo test specifici
pytest tests/test_web_api.py -v

# Con coverage
pytest tests/ --cov=src --cov-report=html

# Test frontend
cd web && npm test
```

### Scrivere Test

- Ogni nuova funzionalità deve avere test
- Usa `pytest` per test Python
- Usa `vitest` per test React
- Mantieni i test isolati e ripetibili

## Code Review

Le Pull Request vengono revisionate per:

1. **Funzionalità**: Il codice fa quello che dovrebbe?
2. **Test**: Ci sono test adeguati?
3. **Stile**: Segue le convenzioni del progetto?
4. **Documentazione**: È documentato appropriatamente?
5. **Performance**: Ci sono problemi di performance?
6. **Sicurezza**: Ci sono vulnerabilità?

## Licenza

Contribuendo a MeshBBS, accetti che il tuo contributo sarà rilasciato sotto la [MIT License](LICENSE).

## Domande?

Se hai domande, apri una issue con il tag `question` o contatta i maintainer.

---

Grazie per contribuire a MeshBBS! 🎉
