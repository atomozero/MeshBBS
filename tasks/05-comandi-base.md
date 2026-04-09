# Task 05: Comandi Base (/help, /post, /list)

## Stato: ✅ COMPLETATO

## Analisi

### Contesto
I comandi rappresentano l'interfaccia utente del BBS. Gli utenti interagiscono con il sistema inviando messaggi di testo con comandi nel formato `/comando [argomenti]`. Il BBS deve:
- Parsare i comandi ricevuti
- Eseguire l'azione richiesta
- Restituire una risposta formattata

### Architettura Command Handler

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
│  Messaggio  │────►│   Parser     │────►│   Handler    │────►│  Risposta   │
│  Ricevuto   │     │  Comando     │     │  Specifico   │     │  Formattata │
└─────────────┘     └──────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Validazione │
                    │  Permessi    │
                    └──────────────┘
```

### Comandi MVP (Fase 1)

| Comando | Descrizione | Esempio | Risposta |
|---------|-------------|---------|----------|
| `/help` | Mostra aiuto | `/help` | Lista comandi disponibili |
| `/post <testo>` | Pubblica messaggio | `/post Ciao!` | Conferma con ID |
| `/list [n]` | Lista ultimi n messaggi | `/list 5` | Ultimi 5 messaggi |
| `/read <id>` | Leggi messaggio specifico | `/read 42` | Contenuto messaggio |

### Formato Risposte
Le risposte devono essere compatte per rispettare i limiti LoRa (~200 bytes):

```
[BBS] <risposta>
```

Esempi:
```
[BBS] Comandi: /help /post /list /read
[BBS] #42 pubblicato
[BBS] #42 Mario (2h): Ciao a tutti!
```

### Sfide Identificate
1. Parsing robusto di comandi con argomenti variabili
2. Gestione errori user-friendly
3. Formattazione compatta per limiti LoRa
4. Rate limiting per prevenire spam
5. Gestione comandi sconosciuti
6. Troncamento messaggi lunghi
7. Gestione caratteri speciali e encoding

---

## Task Dettagliati

### Task 5.1: Creazione Modulo Commands
**Descrizione**: Creare la struttura base per il sistema di comandi

**Sotto-attivita**:
- [ ] Creare file `bbs/commands/__init__.py`
- [ ] Creare file `bbs/commands/base.py` con classe base:
  ```python
  from abc import ABC, abstractmethod
  from dataclasses import dataclass
  from typing import Optional

  @dataclass
  class CommandContext:
      sender_key: str
      sender_name: Optional[str]
      raw_message: str
      timestamp: datetime

  @dataclass
  class CommandResult:
      success: bool
      response: str
      error: Optional[str] = None

  class BaseCommand(ABC):
      name: str
      description: str
      usage: str

      @abstractmethod
      async def execute(self, ctx: CommandContext, args: list) -> CommandResult:
          pass
  ```
- [ ] Creare registry per registrazione comandi:
  ```python
  class CommandRegistry:
      _commands: Dict[str, BaseCommand] = {}

      @classmethod
      def register(cls, command: BaseCommand):
          cls._commands[command.name] = command

      @classmethod
      def get(cls, name: str) -> Optional[BaseCommand]:
          return cls._commands.get(name)
  ```
- [ ] Creare decoratore `@command` per registrazione automatica

**Verifica**: Struttura base importabile senza errori

---

### Task 5.2: Implementazione Parser Comandi
**Descrizione**: Creare il parser per estrarre comando e argomenti dal messaggio

**Sotto-attivita**:
- [ ] Creare file `bbs/commands/parser.py`
- [ ] Implementare parsing base:
  ```python
  @dataclass
  class ParsedCommand:
      command: str          # Nome comando senza /
      args: List[str]       # Lista argomenti
      raw_args: str         # Argomenti come stringa unica
      is_valid: bool        # Se il parsing e riuscito

  def parse_message(message: str) -> Optional[ParsedCommand]:
      message = message.strip()

      # Verifica se inizia con /
      if not message.startswith('/'):
          return None

      # Estrai comando e argomenti
      parts = message[1:].split(maxsplit=1)
      command = parts[0].lower()
      args_str = parts[1] if len(parts) > 1 else ""
      args = args_str.split() if args_str else []

      return ParsedCommand(
          command=command,
          args=args,
          raw_args=args_str,
          is_valid=True
      )
  ```
- [ ] Gestire comandi senza argomenti
- [ ] Gestire argomenti con spazi (quote handling)
- [ ] Normalizzare encoding (UTF-8)
- [ ] Gestire caratteri speciali

**Verifica**: Parser estrae correttamente comando e argomenti

---

### Task 5.3: Implementazione Comando /help
**Descrizione**: Creare il comando per mostrare l'aiuto

**Sotto-attivita**:
- [ ] Creare file `bbs/commands/help.py`
- [ ] Implementare HelpCommand:
  ```python
  class HelpCommand(BaseCommand):
      name = "help"
      description = "Mostra i comandi disponibili"
      usage = "/help [comando]"

      async def execute(self, ctx: CommandContext, args: list) -> CommandResult:
          if args:
              # Aiuto specifico per un comando
              cmd_name = args[0]
              cmd = CommandRegistry.get(cmd_name)
              if cmd:
                  return CommandResult(
                      success=True,
                      response=f"[BBS] {cmd.name}: {cmd.description}\nUso: {cmd.usage}"
                  )
              else:
                  return CommandResult(
                      success=False,
                      response=f"[BBS] Comando '{cmd_name}' non trovato"
                  )
          else:
              # Lista tutti i comandi
              commands = CommandRegistry.all()
              cmd_list = " ".join(f"/{c.name}" for c in commands)
              return CommandResult(
                  success=True,
                  response=f"[BBS] Comandi: {cmd_list}\nUsa /help <cmd> per dettagli"
              )
  ```
- [ ] Registrare il comando nel registry
- [ ] Testare con vari input

**Verifica**: `/help` restituisce lista comandi, `/help post` mostra dettagli

---

### Task 5.4: Implementazione Comando /post
**Descrizione**: Creare il comando per pubblicare messaggi nell'area corrente

**Sotto-attivita**:
- [ ] Creare file `bbs/commands/post.py`
- [ ] Implementare PostCommand:
  ```python
  class PostCommand(BaseCommand):
      name = "post"
      description = "Pubblica un messaggio"
      usage = "/post <messaggio>"

      def __init__(self, db_session, default_area: str = "generale"):
          self.db = db_session
          self.default_area = default_area

      async def execute(self, ctx: CommandContext, args: list) -> CommandResult:
          # Verifica che ci sia un messaggio
          if not args:
              return CommandResult(
                  success=False,
                  response="[BBS] Uso: /post <messaggio>"
              )

          # Ottieni testo completo
          text = " ".join(args)

          # Verifica lunghezza
          if len(text) > 200:
              return CommandResult(
                  success=False,
                  response="[BBS] Messaggio troppo lungo (max 200 car)"
              )

          # Ottieni o crea utente
          user_repo = UserRepository(self.db)
          user = user_repo.get_or_create(ctx.sender_key)
          user.last_seen = datetime.utcnow()

          # Ottieni area
          area = self.db.query(Area).filter_by(name=self.default_area).first()
          if not area:
              return CommandResult(
                  success=False,
                  response="[BBS] Area non trovata"
              )

          # Crea messaggio
          message = Message(
              area=area,
              sender_key=ctx.sender_key,
              body=text,
              timestamp=datetime.utcnow()
          )
          self.db.add(message)
          self.db.commit()

          return CommandResult(
              success=True,
              response=f"[BBS] #{message.id} pubblicato"
          )
  ```
- [ ] Aggiungere validazione utente non bannato
- [ ] Aggiungere logging dell'attivita
- [ ] Gestire errori database

**Verifica**: `/post Ciao!` crea un messaggio e restituisce l'ID

---

### Task 5.5: Implementazione Comando /list
**Descrizione**: Creare il comando per listare i messaggi recenti

**Sotto-attivita**:
- [ ] Creare file `bbs/commands/list.py`
- [ ] Implementare ListCommand:
  ```python
  class ListCommand(BaseCommand):
      name = "list"
      description = "Lista ultimi messaggi"
      usage = "/list [n]"
      DEFAULT_LIMIT = 5
      MAX_LIMIT = 10

      async def execute(self, ctx: CommandContext, args: list) -> CommandResult:
          # Parse limite
          limit = self.DEFAULT_LIMIT
          if args:
              try:
                  limit = min(int(args[0]), self.MAX_LIMIT)
              except ValueError:
                  return CommandResult(
                      success=False,
                      response="[BBS] Uso: /list [numero]"
                  )

          # Query messaggi
          msg_repo = MessageRepository(self.db)
          messages = msg_repo.get_recent_messages(
              area_name="generale",
              limit=limit
          )

          if not messages:
              return CommandResult(
                  success=True,
                  response="[BBS] Nessun messaggio"
              )

          # Formatta risposta
          lines = []
          for msg in messages:
              author = msg.author.nickname or msg.sender_key[:6]
              age = self._format_age(msg.timestamp)
              preview = msg.body[:30] + "..." if len(msg.body) > 30 else msg.body
              lines.append(f"#{msg.id} {author} ({age}): {preview}")

          return CommandResult(
              success=True,
              response="[BBS]\n" + "\n".join(lines)
          )

      def _format_age(self, timestamp: datetime) -> str:
          delta = datetime.utcnow() - timestamp
          if delta.days > 0:
              return f"{delta.days}g"
          elif delta.seconds > 3600:
              return f"{delta.seconds // 3600}h"
          elif delta.seconds > 60:
              return f"{delta.seconds // 60}m"
          else:
              return "ora"
  ```
- [ ] Limitare output per rispettare limiti LoRa
- [ ] Troncare messaggi lunghi con "..."
- [ ] Formattare timestamp in modo leggibile e compatto

**Verifica**: `/list` mostra ultimi 5 messaggi, `/list 3` mostra ultimi 3

---

### Task 5.6: Implementazione Comando /read
**Descrizione**: Creare il comando per leggere un messaggio specifico

**Sotto-attivita**:
- [ ] Creare file `bbs/commands/read.py`
- [ ] Implementare ReadCommand:
  ```python
  class ReadCommand(BaseCommand):
      name = "read"
      description = "Leggi un messaggio"
      usage = "/read <id>"

      async def execute(self, ctx: CommandContext, args: list) -> CommandResult:
          # Verifica argomento
          if not args:
              return CommandResult(
                  success=False,
                  response="[BBS] Uso: /read <id>"
              )

          # Parse ID
          try:
              msg_id = int(args[0])
          except ValueError:
              return CommandResult(
                  success=False,
                  response="[BBS] ID non valido"
              )

          # Query messaggio
          message = self.db.query(Message).get(msg_id)

          if not message:
              return CommandResult(
                  success=False,
                  response=f"[BBS] Msg #{msg_id} non trovato"
              )

          # Formatta risposta
          author = message.author.nickname or message.sender_key[:8]
          age = self._format_age(message.timestamp)
          area = message.area.name

          # Costruisci risposta
          response = f"[BBS] #{msg_id} in {area}\n"
          response += f"Da: {author} ({age})\n"
          response += f"{message.body}"

          # Tronca se troppo lungo
          if len(response) > 200:
              response = response[:197] + "..."

          return CommandResult(
              success=True,
              response=response
          )
  ```
- [ ] Mostrare eventuali risposte/thread
- [ ] Gestire messaggi non trovati
- [ ] Troncare messaggi lunghi

**Verifica**: `/read 1` mostra contenuto completo del messaggio #1

---

### Task 5.7: Creazione Command Dispatcher
**Descrizione**: Creare il dispatcher che coordina parsing ed esecuzione

**Sotto-attivita**:
- [ ] Creare file `bbs/commands/dispatcher.py`
- [ ] Implementare CommandDispatcher:
  ```python
  class CommandDispatcher:
      def __init__(self, db_session):
          self.db = db_session
          self._register_commands()

      def _register_commands(self):
          """Registra tutti i comandi disponibili"""
          CommandRegistry.register(HelpCommand())
          CommandRegistry.register(PostCommand(self.db))
          CommandRegistry.register(ListCommand(self.db))
          CommandRegistry.register(ReadCommand(self.db))

      async def dispatch(self, message: str, sender_key: str) -> Optional[str]:
          """Processa un messaggio e restituisce la risposta"""

          # Parse comando
          parsed = parse_message(message)

          # Se non e un comando, ignora
          if not parsed:
              return None

          # Crea contesto
          ctx = CommandContext(
              sender_key=sender_key,
              sender_name=self._get_user_name(sender_key),
              raw_message=message,
              timestamp=datetime.utcnow()
          )

          # Verifica se utente e bannato
          if self._is_banned(sender_key):
              return "[BBS] Accesso negato"

          # Ottieni handler
          command = CommandRegistry.get(parsed.command)

          if not command:
              return f"[BBS] Comando '/{parsed.command}' sconosciuto. Usa /help"

          # Esegui comando
          try:
              result = await command.execute(ctx, parsed.args)
              return result.response
          except Exception as e:
              logger.error(f"Errore comando {parsed.command}: {e}")
              return "[BBS] Errore interno"
  ```
- [ ] Aggiungere logging di tutti i comandi
- [ ] Gestire eccezioni senza crash
- [ ] Rate limiting per utente

**Verifica**: Dispatcher instrada correttamente tutti i comandi

---

### Task 5.8: Gestione Errori e Messaggi User-Friendly
**Descrizione**: Implementare gestione errori completa e messaggi chiari

**Sotto-attivita**:
- [ ] Creare file `bbs/commands/errors.py`
- [ ] Definire eccezioni custom:
  ```python
  class BBSError(Exception):
      """Base exception per errori BBS"""
      def __init__(self, message: str, user_message: str):
          super().__init__(message)
          self.user_message = user_message

  class PermissionDenied(BBSError):
      pass

  class InvalidArgument(BBSError):
      pass

  class NotFound(BBSError):
      pass

  class RateLimitExceeded(BBSError):
      pass
  ```
- [ ] Implementare error handler centralizzato:
  ```python
  def handle_error(error: Exception) -> str:
      if isinstance(error, BBSError):
          return f"[BBS] {error.user_message}"
      else:
          logger.exception("Errore non gestito")
          return "[BBS] Errore imprevisto"
  ```
- [ ] Messaggi di errore in italiano, chiari e concisi
- [ ] Suggerire azione correttiva quando possibile

**Verifica**: Errori mostrano messaggi comprensibili all'utente

---

### Task 5.9: Integrazione con Core BBS
**Descrizione**: Integrare il sistema di comandi con il core del BBS

**Sotto-attivita**:
- [ ] Modificare `bbs/core.py` per usare il dispatcher:
  ```python
  class BBSCore:
      def __init__(self, db, mesh_connection):
          self.db = db
          self.mesh = mesh_connection
          self.dispatcher = CommandDispatcher(db)

      async def handle_message(self, message: Message) -> Optional[str]:
          """Gestisce un messaggio in arrivo"""

          # Log ricezione
          logger.info(f"Ricevuto da {message.sender_key[:8]}: {message.text}")

          # Dispatch comando
          response = await self.dispatcher.dispatch(
              message=message.text,
              sender_key=message.sender_key
          )

          # Log risposta
          if response:
              logger.info(f"Risposta: {response[:50]}...")

          return response
  ```
- [ ] Aggiornare il main loop per usare BBSCore
- [ ] Testare flusso completo: ricezione -> parsing -> risposta

**Verifica**: Messaggi ricevuti vengono processati e risposte inviate

---

### Task 5.10: Test e Documentazione Comandi
**Descrizione**: Creare test e documentazione per i comandi

**Sotto-attivita**:
- [ ] Creare `tests/test_commands.py`:
  ```python
  import pytest
  from bbs.commands.parser import parse_message
  from bbs.commands.dispatcher import CommandDispatcher

  def test_parse_help():
      result = parse_message("/help")
      assert result.command == "help"
      assert result.args == []

  def test_parse_post_with_text():
      result = parse_message("/post Ciao a tutti!")
      assert result.command == "post"
      assert result.raw_args == "Ciao a tutti!"

  def test_parse_list_with_number():
      result = parse_message("/list 10")
      assert result.command == "list"
      assert result.args == ["10"]

  @pytest.mark.asyncio
  async def test_help_command(db_session):
      dispatcher = CommandDispatcher(db_session)
      response = await dispatcher.dispatch("/help", "test_key")
      assert "[BBS]" in response
      assert "/help" in response
  ```
- [ ] Test per ogni comando base
- [ ] Test per casi di errore
- [ ] Test per messaggi non-comando (devono essere ignorati)
- [ ] Creare `docs/commands.md` con documentazione utente
- [ ] Aggiungere esempi d'uso

**Verifica**: Tutti i test passano, documentazione completa

---

## Checklist Finale

- [x] Modulo commands strutturato
- [x] Parser comandi funzionante
- [x] /help implementato e testato
- [x] /post implementato e testato
- [x] /list implementato e testato
- [x] /read implementato e testato
- [x] /nick implementato e testato
- [x] /areas implementato e testato
- [x] Dispatcher operativo
- [x] Gestione errori completa
- [x] Integrazione con core BBS
- [x] Test e documentazione completi (15 test per comandi)

---

## Risorse Utili

- Click (CLI framework Python): https://click.palletsprojects.com/
- Command Pattern: https://refactoring.guru/design-patterns/command
- Python dataclasses: https://docs.python.org/3/library/dataclasses.html

---

## Note Tecniche

### Limiti Risposta LoRa
| Elemento | Limite | Note |
|----------|--------|------|
| Payload totale | ~200 bytes | Limite pratico LoRa |
| Risposta BBS | 180 chars | Margine sicurezza |
| Preview messaggio | 30 chars | In /list |
| Nickname | 16 chars | Display |

### Template Risposte
```python
TEMPLATES = {
    "help_list": "[BBS] Comandi: {commands}\nUsa /help <cmd> per dettagli",
    "help_detail": "[BBS] {name}: {description}\nUso: {usage}",
    "post_success": "[BBS] #{id} pubblicato",
    "post_error_empty": "[BBS] Uso: /post <messaggio>",
    "post_error_long": "[BBS] Max 200 caratteri",
    "list_empty": "[BBS] Nessun messaggio",
    "list_item": "#{id} {author} ({age}): {preview}",
    "read_header": "[BBS] #{id} in {area}\nDa: {author} ({age})",
    "error_not_found": "[BBS] Non trovato",
    "error_banned": "[BBS] Accesso negato",
    "error_unknown_cmd": "[BBS] Comando sconosciuto. Usa /help",
    "error_internal": "[BBS] Errore interno"
}
```

### Esempio Completo di Interazione
```
Utente: /help
BBS:    [BBS] Comandi: /help /post /list /read
        Usa /help <cmd> per dettagli

Utente: /post Ciao a tutti, come state?
BBS:    [BBS] #1 pubblicato

Utente: /list
BBS:    [BBS]
        #1 ABC123 (ora): Ciao a tutti, come state?

Utente: /read 1
BBS:    [BBS] #1 in generale
        Da: ABC123 (1m)
        Ciao a tutti, come state?

Utente: /xyz
BBS:    [BBS] Comando '/xyz' sconosciuto. Usa /help
```

### Struttura File Finale
```
bbs/
├── commands/
│   ├── __init__.py
│   ├── base.py          # BaseCommand, CommandContext, CommandResult
│   ├── parser.py        # parse_message()
│   ├── dispatcher.py    # CommandDispatcher
│   ├── errors.py        # Eccezioni custom
│   ├── help.py          # HelpCommand
│   ├── post.py          # PostCommand
│   ├── list.py          # ListCommand
│   └── read.py          # ReadCommand
├── core.py              # BBSCore (integrazione)
└── ...
```
