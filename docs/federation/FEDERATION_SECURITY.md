# MeshBBS Federation Security Considerations

## Security Analysis Document

**Version:** 1.0
**Date:** January 2026
**Status:** Draft

---

## 1. Executive Summary

Questo documento analizza le considerazioni di sicurezza per il sistema di federazione MeshBBS, identificando minacce, mitigazioni e best practices.

### 1.1 Security Goals

1. **Confidentiality**: I messaggi privati devono essere leggibili solo dal destinatario
2. **Integrity**: I messaggi non devono essere modificabili in transito
3. **Authenticity**: L'identità dei nodi e utenti deve essere verificabile
4. **Availability**: Il sistema deve resistere ad attacchi DoS
5. **Non-repudiation**: Le azioni devono essere attribuibili

### 1.2 Trust Model

```
┌─────────────────────────────────────────────────────────────┐
│                      TRUST LEVELS                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Level 0: UNTRUSTED                                          │
│  - Nodi appena scoperti                                      │
│  - Nessun relay di PM                                        │
│  - Sync limitato a aree pubbliche read-only                  │
│                                                               │
│  Level 1: KNOWN                                               │
│  - Nodo verificato (chiave pubblica confermata)              │
│  - Relay PM permesso con rate limiting                       │
│  - Sync bidirezionale per aree autorizzate                   │
│                                                               │
│  Level 2: TRUSTED                                             │
│  - Aggiunto manualmente dall'admin                           │
│  - Rate limiting ridotto                                      │
│  - Può propagare annunci di altri nodi                       │
│                                                               │
│  Level 3: FEDERATED                                           │
│  - Parte della rete federata ufficiale                       │
│  - Fiducia reciproca completa                                │
│  - User roaming permesso                                      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Threat Model

### 2.1 Threat Actors

| Actor | Capability | Motivation |
|-------|------------|------------|
| **Passive Eavesdropper** | Intercetta traffico LoRa | Spionaggio, raccolta dati |
| **Active Attacker** | Inietta/modifica messaggi | Disinformazione, disruption |
| **Malicious Node** | Nodo federato compromesso | Spam, data exfiltration |
| **Sybil Attacker** | Controlla molti nodi falsi | Takeover rete, censura |
| **Insider** | Admin di un nodo federato | Abuso privilegi |

### 2.2 Attack Surface

```
┌─────────────────────────────────────────────────────────────┐
│                     ATTACK SURFACE                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐ │
│  │   LoRa RF    │     │  Protocol    │     │   Data       │ │
│  │   Layer      │     │   Layer      │     │   Layer      │ │
│  ├──────────────┤     ├──────────────┤     ├──────────────┤ │
│  │ • RF jamming │     │ • Replay     │     │ • Injection  │ │
│  │ • Sniffing   │     │ • Spoofing   │     │ • Corruption │ │
│  │ • Injection  │     │ • DoS        │     │ • Leakage    │ │
│  └──────────────┘     └──────────────┘     └──────────────┘ │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 STRIDE Analysis

| Threat | Description | Affected Assets |
|--------|-------------|-----------------|
| **S**poofing | Impersonare un nodo/utente | Identity, Trust |
| **T**ampering | Modificare messaggi in transito | Messages, Data |
| **R**epudiation | Negare di aver inviato un messaggio | Accountability |
| **I**nformation Disclosure | Leggere messaggi privati | Privacy |
| **D**enial of Service | Rendere la rete inutilizzabile | Availability |
| **E**levation of Privilege | Ottenere accesso non autorizzato | Authorization |

---

## 3. Cryptographic Design

### 3.1 Algorithms

| Purpose | Algorithm | Key Size | Notes |
|---------|-----------|----------|-------|
| Node Identity | Ed25519 | 256-bit | Firma digitale |
| Key Exchange | X25519 | 256-bit | ECDH per E2E |
| Encryption | ChaCha20-Poly1305 | 256-bit | AEAD |
| Hashing | SHA-256 | 256-bit | Integrity, Merkle |
| KDF | HKDF-SHA256 | Variable | Key derivation |

### 3.2 Key Management

#### 3.2.1 Node Keys

```python
class NodeKeyManager:
    """Gestione chiavi del nodo"""

    def __init__(self, key_path: str):
        self.key_path = key_path
        self._private_key: Optional[bytes] = None
        self._public_key: Optional[bytes] = None

    def generate_node_keys(self) -> Tuple[bytes, bytes]:
        """Genera nuova coppia di chiavi per il nodo"""
        private_key = os.urandom(32)
        public_key = ed25519_publickey(private_key)

        # Salva con permessi restrittivi
        self._save_private_key(private_key)

        return private_key, public_key

    def _save_private_key(self, key: bytes):
        """Salva chiave privata in modo sicuro"""
        key_file = Path(self.key_path) / "node.key"

        # Cripta con password se configurato
        if self.config.key_password:
            key = self._encrypt_key(key, self.config.key_password)

        key_file.write_bytes(key)
        os.chmod(key_file, 0o600)  # Solo owner può leggere

    def rotate_keys(self, grace_period_hours: int = 24):
        """Ruota le chiavi del nodo"""
        # Genera nuove chiavi
        new_private, new_public = self.generate_node_keys()

        # Annuncia nuova chiave ai peer
        # Mantieni vecchia chiave valida per grace period
        self._announce_key_rotation(new_public, grace_period_hours)
```

#### 3.2.2 User Keys

```python
class UserKeyManager:
    """Gestione chiavi utente per E2E encryption"""

    def generate_user_keys(self, user_id: int) -> Tuple[bytes, bytes]:
        """Genera chiavi E2E per un utente"""
        private_key = x25519_generate_private()
        public_key = x25519_public_from_private(private_key)

        # Chiave privata criptata con password utente
        encrypted_private = self._encrypt_with_user_password(
            private_key,
            user_id
        )

        # Salva nel database
        self.db.save_user_keys(
            user_id=user_id,
            public_key=public_key,
            encrypted_private=encrypted_private
        )

        return private_key, public_key

    def get_user_public_key(self, federated_id: str) -> Optional[bytes]:
        """Ottiene chiave pubblica di un utente (anche remoto)"""
        # Prima cerca in cache locale
        cached = self.key_cache.get(federated_id)
        if cached and not self._is_expired(cached):
            return cached.public_key

        # Se utente locale
        if self._is_local_user(federated_id):
            return self.db.get_user_public_key(federated_id)

        # Richiedi al nodo remoto
        return await self._fetch_remote_key(federated_id)
```

### 3.3 End-to-End Encryption

```python
class E2EEncryption:
    """Crittografia end-to-end per PM federati"""

    def encrypt_message(
        self,
        plaintext: bytes,
        sender_private: bytes,
        recipient_public: bytes
    ) -> bytes:
        """
        Cripta un messaggio per un destinatario specifico.

        Usa X25519 per key agreement + ChaCha20-Poly1305 per AEAD.
        """
        # Deriva shared secret
        shared_secret = x25519(sender_private, recipient_public)

        # Deriva chiave di cifratura con HKDF
        encryption_key = hkdf(
            ikm=shared_secret,
            salt=b"MeshBBS-E2E-v1",
            info=b"message-encryption",
            length=32
        )

        # Genera nonce casuale
        nonce = os.urandom(12)

        # Cifra con ChaCha20-Poly1305
        cipher = ChaCha20Poly1305(encryption_key)
        ciphertext = cipher.encrypt(nonce, plaintext, associated_data=None)

        # Formato: version(1) + nonce(12) + ciphertext(n+16)
        return bytes([0x01]) + nonce + ciphertext

    def decrypt_message(
        self,
        encrypted: bytes,
        recipient_private: bytes,
        sender_public: bytes
    ) -> bytes:
        """Decripta un messaggio"""
        version = encrypted[0]
        if version != 0x01:
            raise UnsupportedVersionError(f"Unknown E2E version: {version}")

        nonce = encrypted[1:13]
        ciphertext = encrypted[13:]

        # Deriva stessa chiave
        shared_secret = x25519(recipient_private, sender_public)
        encryption_key = hkdf(
            ikm=shared_secret,
            salt=b"MeshBBS-E2E-v1",
            info=b"message-encryption",
            length=32
        )

        # Decifra
        cipher = ChaCha20Poly1305(encryption_key)
        return cipher.decrypt(nonce, ciphertext, associated_data=None)
```

### 3.4 Message Authentication

```python
class MessageAuthenticator:
    """Autenticazione e integrità messaggi"""

    def sign_federation_message(
        self,
        message: FederationMessage,
        private_key: bytes
    ) -> bytes:
        """Firma un messaggio federato"""
        # Serializza messaggio senza firma
        to_sign = message.serialize_without_signature()

        # Firma Ed25519
        signature = ed25519_sign(private_key, to_sign)

        # Aggiungi firma al messaggio
        message.signature = signature
        return message.serialize()

    def verify_federation_message(
        self,
        message: FederationMessage,
        public_key: bytes
    ) -> bool:
        """Verifica firma di un messaggio"""
        if not message.signature:
            return False

        to_verify = message.serialize_without_signature()
        return ed25519_verify(public_key, to_verify, message.signature)

    def compute_message_hash(self, message: FederationMessage) -> bytes:
        """Calcola hash univoco del messaggio"""
        return hashlib.sha256(message.serialize()).digest()
```

---

## 4. Authentication & Authorization

### 4.1 Node Authentication

```python
class NodeAuthenticator:
    """Autenticazione mutua tra nodi"""

    async def authenticate_node(
        self,
        node_id: int,
        challenge: bytes
    ) -> AuthResult:
        """
        Challenge-response authentication.

        1. Node A invia challenge random
        2. Node B firma challenge con sua chiave privata
        3. Node A verifica firma con chiave pubblica di B
        """
        # Invia challenge
        response = await self.transport.request(
            target=node_id,
            message=AuthChallengeMessage(
                challenge=challenge,
                timestamp=int(time.time())
            ),
            timeout=30
        )

        # Verifica risposta
        expected_public_key = self.get_node_public_key(node_id)
        if not expected_public_key:
            return AuthResult(success=False, reason="Unknown node")

        # Verifica firma del challenge
        if not ed25519_verify(
            expected_public_key,
            challenge,
            response.signature
        ):
            return AuthResult(success=False, reason="Invalid signature")

        return AuthResult(success=True, node_id=node_id)
```

### 4.2 User Authentication for Roaming

```python
class RoamingAuthenticator:
    """Autenticazione utenti in roaming"""

    async def authenticate_roaming_user(
        self,
        user: str,  # alice@remote_node
        credential: bytes
    ) -> AuthResult:
        """
        Verifica che un utente possa fare roaming su questo nodo.

        Opzione 1: Verifica con nodo home
        Opzione 2: Verifica locale con chiave pubblica utente
        """
        username, home_node = self._parse_federated_id(user)

        # Ottieni chiave pubblica utente
        user_public_key = await self.key_manager.get_user_public_key(user)
        if not user_public_key:
            return AuthResult(success=False, reason="Unknown user")

        # Verifica che il credential sia firmato dalla chiave utente
        # Il credential contiene: timestamp + nonce + firma
        timestamp = int.from_bytes(credential[:4], 'big')
        nonce = credential[4:20]
        signature = credential[20:]

        # Verifica timestamp (max 5 minuti di skew)
        if abs(time.time() - timestamp) > 300:
            return AuthResult(success=False, reason="Credential expired")

        # Verifica firma
        to_verify = credential[:20]  # timestamp + nonce
        if not ed25519_verify(user_public_key, to_verify, signature):
            return AuthResult(success=False, reason="Invalid credential")

        return AuthResult(success=True, user=user)
```

### 4.3 Authorization Matrix

```python
class FederationAuthorization:
    """Matrice di autorizzazione per operazioni federate"""

    # Permessi per trust level
    PERMISSIONS = {
        TrustLevel.UNTRUSTED: {
            'receive_announce': True,
            'send_announce': True,
            'sync_public_read': True,
            'sync_public_write': False,
            'relay_pm': False,
            'user_roaming': False,
        },
        TrustLevel.KNOWN: {
            'receive_announce': True,
            'send_announce': True,
            'sync_public_read': True,
            'sync_public_write': True,
            'relay_pm': True,  # con rate limiting
            'user_roaming': False,
        },
        TrustLevel.TRUSTED: {
            'receive_announce': True,
            'send_announce': True,
            'sync_public_read': True,
            'sync_public_write': True,
            'relay_pm': True,
            'user_roaming': True,
            'propagate_announces': True,
        },
        TrustLevel.FEDERATED: {
            '*': True  # Tutti i permessi
        }
    }

    def is_allowed(
        self,
        node_id: int,
        operation: str
    ) -> bool:
        """Verifica se un nodo può eseguire un'operazione"""
        trust_level = self.get_node_trust_level(node_id)
        permissions = self.PERMISSIONS[trust_level]

        return permissions.get('*', False) or permissions.get(operation, False)
```

---

## 5. Anti-Spam & Rate Limiting

### 5.1 Multi-Layer Rate Limiting

```python
class FederationRateLimiter:
    """Rate limiting multi-livello per federazione"""

    def __init__(self):
        # Limiti per nodo
        self.node_limits = {
            'announce': TokenBucket(rate=1, capacity=2, per=600),      # 1 ogni 10 min
            'sync_request': TokenBucket(rate=10, capacity=20, per=60), # 10/min
            'pm_relay': TokenBucket(rate=30, capacity=50, per=60),     # 30/min
            'post_broadcast': TokenBucket(rate=5, capacity=10, per=60),# 5/min
        }

        # Limiti globali
        self.global_limits = {
            'total_messages': TokenBucket(rate=100, capacity=200, per=60),
            'total_bandwidth': TokenBucket(rate=50000, capacity=100000, per=60),  # 50KB/min
        }

        # Tracking per nodo
        self.node_buckets: Dict[int, Dict[str, TokenBucket]] = {}

    def check_rate_limit(
        self,
        node_id: int,
        message_type: str,
        size: int
    ) -> RateLimitResult:
        """Verifica rate limits per un messaggio"""

        # Check global limits
        if not self.global_limits['total_messages'].consume(1):
            return RateLimitResult(
                allowed=False,
                reason="Global message limit exceeded"
            )

        if not self.global_limits['total_bandwidth'].consume(size):
            return RateLimitResult(
                allowed=False,
                reason="Global bandwidth limit exceeded"
            )

        # Check per-node limits
        node_bucket = self._get_node_bucket(node_id, message_type)
        if not node_bucket.consume(1):
            return RateLimitResult(
                allowed=False,
                reason=f"Node rate limit exceeded for {message_type}",
                retry_after=node_bucket.time_to_next_token()
            )

        return RateLimitResult(allowed=True)
```

### 5.2 Spam Detection

```python
class SpamDetector:
    """Rilevamento spam in messaggi federati"""

    def __init__(self):
        self.message_hashes: Dict[bytes, int] = {}  # hash -> count
        self.suspicious_nodes: Dict[int, int] = {}  # node -> score

    def check_message(
        self,
        node_id: int,
        message: FederationMessage
    ) -> SpamCheckResult:
        """Analizza un messaggio per potenziale spam"""
        score = 0
        reasons = []

        # 1. Duplicate detection
        msg_hash = self._hash_content(message)
        if self.message_hashes.get(msg_hash, 0) > 3:
            score += 50
            reasons.append("Duplicate content detected")

        # 2. Rate anomaly
        if self._is_rate_anomaly(node_id):
            score += 30
            reasons.append("Unusual message rate")

        # 3. Content analysis
        if hasattr(message, 'content'):
            content_score, content_reasons = self._analyze_content(message.content)
            score += content_score
            reasons.extend(content_reasons)

        # 4. Node reputation
        score += self.suspicious_nodes.get(node_id, 0)

        # Threshold decision
        if score >= 100:
            return SpamCheckResult(is_spam=True, score=score, reasons=reasons)
        elif score >= 50:
            return SpamCheckResult(is_spam=False, suspicious=True, score=score)
        else:
            return SpamCheckResult(is_spam=False, suspicious=False, score=score)

    def _analyze_content(self, content: str) -> Tuple[int, List[str]]:
        """Analisi euristica del contenuto"""
        score = 0
        reasons = []

        # Caratteri ripetuti
        if re.search(r'(.)\1{10,}', content):
            score += 20
            reasons.append("Repeated characters")

        # Link sospetti
        urls = re.findall(r'https?://[^\s]+', content)
        if len(urls) > 5:
            score += 30
            reasons.append("Too many URLs")

        # Tutto maiuscolo
        if content.isupper() and len(content) > 20:
            score += 10
            reasons.append("All caps text")

        return score, reasons
```

### 5.3 Reputation System

```python
class NodeReputation:
    """Sistema di reputazione per nodi federati"""

    def __init__(self):
        self.scores: Dict[int, float] = {}  # node_id -> score (0-100)
        self.history: Dict[int, List[ReputationEvent]] = {}

    def update_reputation(
        self,
        node_id: int,
        event_type: str,
        magnitude: float = 1.0
    ):
        """Aggiorna reputazione basata su eventi"""
        current = self.scores.get(node_id, 50.0)  # Start at neutral

        # Eventi positivi/negativi
        delta = {
            'valid_message': +0.1,
            'invalid_signature': -5.0,
            'spam_detected': -10.0,
            'rate_limit_exceeded': -2.0,
            'successful_sync': +0.5,
            'sync_conflict': -0.2,
            'pm_delivered': +0.2,
            'pm_failed': -1.0,
        }.get(event_type, 0) * magnitude

        # Apply with decay toward neutral
        new_score = current + delta
        new_score = 0.99 * new_score + 0.01 * 50  # Slow decay to 50

        # Clamp to valid range
        self.scores[node_id] = max(0, min(100, new_score))

        # Log event
        self._log_event(node_id, event_type, delta)

    def get_trust_level(self, node_id: int) -> TrustLevel:
        """Determina trust level basato su reputazione"""
        score = self.scores.get(node_id, 50)

        if score < 20:
            return TrustLevel.UNTRUSTED  # Probabile attacker
        elif score < 40:
            return TrustLevel.KNOWN  # Sospetto
        elif score < 70:
            return TrustLevel.TRUSTED  # Normale
        else:
            return TrustLevel.FEDERATED  # Eccellente
```

---

## 6. Attack Mitigation

### 6.1 Replay Attack Prevention

```python
class ReplayProtection:
    """Protezione contro replay attacks"""

    def __init__(self):
        # Nonce visti di recente (per message type)
        self.seen_nonces: Dict[str, Set[bytes]] = {}
        # Timestamp accettabili
        self.max_clock_skew = 300  # 5 minuti

    def check_replay(
        self,
        message: FederationMessage
    ) -> ReplayCheckResult:
        """Verifica che il messaggio non sia un replay"""

        # 1. Verifica timestamp
        if hasattr(message, 'timestamp'):
            if abs(time.time() - message.timestamp) > self.max_clock_skew:
                return ReplayCheckResult(
                    is_replay=True,
                    reason="Timestamp too old or in future"
                )

        # 2. Verifica nonce/message_id unicità
        if hasattr(message, 'message_id'):
            msg_type = type(message).__name__
            seen = self.seen_nonces.setdefault(msg_type, set())

            if message.message_id in seen:
                return ReplayCheckResult(
                    is_replay=True,
                    reason="Duplicate message ID"
                )

            seen.add(message.message_id)

            # Cleanup vecchi (keep last 10000)
            if len(seen) > 10000:
                # Rimuovi i più vecchi (assumendo ordine di inserimento)
                seen.clear()  # Simplified; use ordered set in production

        return ReplayCheckResult(is_replay=False)
```

### 6.2 Sybil Attack Mitigation

```python
class SybilDefense:
    """Difesa contro Sybil attacks"""

    def __init__(self):
        self.node_clusters: Dict[str, Set[int]] = {}  # signature -> nodes

    def analyze_sybil_risk(
        self,
        node_id: int,
        announcement: NodeAnnouncement
    ) -> SybilRisk:
        """Analizza rischio Sybil per un nodo"""
        risk_score = 0
        indicators = []

        # 1. Pattern simili in annunci
        signature = self._compute_behavior_signature(announcement)
        similar_nodes = self.node_clusters.get(signature, set())
        if len(similar_nodes) > 3:
            risk_score += 30
            indicators.append(f"Similar to {len(similar_nodes)} other nodes")

        # 2. Timing sospetto
        if self._detect_coordinated_timing(node_id):
            risk_score += 40
            indicators.append("Coordinated timing detected")

        # 3. Geographic clustering
        # (Se disponibile info sulla posizione)

        # 4. Key derivation pattern
        if self._detect_related_keys(announcement.public_key):
            risk_score += 50
            indicators.append("Related key detected")

        return SybilRisk(
            score=risk_score,
            indicators=indicators,
            is_sybil=risk_score > 70
        )

    def _compute_behavior_signature(self, announcement: NodeAnnouncement) -> str:
        """Calcola signature comportamentale"""
        # Combina caratteristiche per identificare pattern
        features = [
            str(announcement.capabilities),
            str(len(announcement.areas)),
            str(announcement.user_count // 10),  # Bucket
        ]
        return hashlib.md5('|'.join(features).encode()).hexdigest()[:8]
```

### 6.3 Eclipse Attack Prevention

```python
class EclipseDefense:
    """Difesa contro Eclipse attacks"""

    def __init__(self, min_diverse_sources: int = 3):
        self.min_sources = min_diverse_sources
        self.announcement_sources: Dict[int, Set[int]] = {}

    def validate_routing_info(
        self,
        target_node: int,
        via_node: int,
        info: NodeInfo
    ) -> bool:
        """
        Verifica che le info di routing provengano da fonti diverse.
        Previene che un attacker isoli un nodo fornendo info false.
        """
        sources = self.announcement_sources.setdefault(target_node, set())
        sources.add(via_node)

        # Richiedi conferma da almeno N fonti diverse
        # prima di usare info di routing
        if len(sources) < self.min_sources:
            return False  # Non ancora confermato

        # Verifica coerenza tra fonti
        if not self._check_consistency(target_node, sources):
            return False

        return True

    def _check_consistency(self, target: int, sources: Set[int]) -> bool:
        """Verifica che le info da diverse fonti siano coerenti"""
        # Confronta public key, capabilities, etc.
        # Se troppo diverse, possibile attacco
        infos = [self.get_cached_info(target, src) for src in sources]
        public_keys = set(info.public_key for info in infos if info)

        # Tutte le fonti devono concordare sulla public key
        return len(public_keys) == 1
```

---

## 7. Privacy Considerations

### 7.1 Metadata Protection

```python
class MetadataProtection:
    """Protezione metadati sensibili"""

    def minimize_metadata(
        self,
        message: FederationMessage
    ) -> FederationMessage:
        """Rimuove metadati non necessari"""

        # Non esporre info non necessarie
        if isinstance(message, PMRelayMessage):
            # Rimuovi timestamp esatto (usa bucket temporale)
            message.timestamp = self._bucket_timestamp(message.timestamp)

            # Non esporre IP/info di rete
            message.routing_info = None

        return message

    def _bucket_timestamp(self, timestamp: int, bucket_size: int = 3600) -> int:
        """Arrotonda timestamp al bucket più vicino"""
        return (timestamp // bucket_size) * bucket_size
```

### 7.2 Traffic Analysis Resistance

```python
class TrafficAnalysisDefense:
    """Difesa contro traffic analysis"""

    def __init__(self):
        self.padding_enabled = True
        self.dummy_traffic_enabled = True

    def pad_message(self, message: bytes, target_size: int = 256) -> bytes:
        """Padding messaggi a dimensione fissa"""
        if len(message) >= target_size:
            return message

        # Random padding
        padding_size = target_size - len(message)
        padding = os.urandom(padding_size)

        # Formato: original_len(2) + message + padding
        return len(message).to_bytes(2, 'big') + message + padding

    async def generate_dummy_traffic(self):
        """Genera traffico dummy per confondere analisi"""
        while self.dummy_traffic_enabled:
            # Attendi intervallo random
            await asyncio.sleep(random.uniform(30, 120))

            # Invia messaggio dummy a nodo random
            if self.known_nodes:
                target = random.choice(list(self.known_nodes))
                dummy = self._create_dummy_message()
                await self.transport.send(dummy, target)
```

### 7.3 User Anonymity

```python
class AnonymityService:
    """Servizio per comunicazioni anonime (opzionale)"""

    async def send_anonymous_pm(
        self,
        content: str,
        recipient: str
    ) -> SendResult:
        """
        Invia PM anonimo usando onion routing semplificato.

        Il messaggio passa attraverso nodi intermedi che
        non conoscono mittente e destinatario insieme.
        """
        # Seleziona path di 2-3 nodi
        path = self._select_anonymous_path(recipient)

        # Cripta a strati (come onion)
        encrypted = content.encode('utf-8')
        for node in reversed(path):
            node_key = await self.get_node_public_key(node)
            encrypted = self._encrypt_layer(encrypted, node_key)

        # Invia al primo nodo del path
        return await self.transport.send_anonymous(encrypted, path[0])
```

---

## 8. Secure Development Practices

### 8.1 Security Checklist

```markdown
## Pre-Release Security Checklist

### Cryptography
- [ ] Tutte le chiavi generate con CSPRNG
- [ ] Nonce mai riutilizzati
- [ ] Constant-time comparison per segreti
- [ ] Key derivation usa HKDF non hash diretto
- [ ] Zeroization memoria sensibile

### Authentication
- [ ] Challenge-response per auth nodi
- [ ] Timeout su tutte le operazioni auth
- [ ] Lockout dopo tentativi falliti
- [ ] Logging tentativi di auth

### Input Validation
- [ ] Tutti gli input esterni validati
- [ ] Bounds checking su tutti i buffer
- [ ] Encoding validato (UTF-8)
- [ ] Message size limits enforced

### Error Handling
- [ ] Nessuna info sensibile in errori
- [ ] Fail-secure su errori
- [ ] Logging errori sicurezza
- [ ] Rate limit su errori

### Code Quality
- [ ] Static analysis (bandit) clean
- [ ] Dependency audit (safety) clean
- [ ] No hardcoded secrets
- [ ] Code review completato
```

### 8.2 Incident Response Plan

```python
class SecurityIncidentHandler:
    """Gestione incidenti di sicurezza"""

    async def handle_security_incident(
        self,
        incident_type: str,
        details: Dict[str, Any]
    ):
        """Risposta automatica a incidenti di sicurezza"""

        if incident_type == 'compromised_node':
            await self._handle_compromised_node(details['node_id'])

        elif incident_type == 'key_compromise':
            await self._handle_key_compromise(details)

        elif incident_type == 'spam_attack':
            await self._handle_spam_attack(details['source_node'])

        # Log incident
        await self._log_security_incident(incident_type, details)

        # Alert admin
        await self._alert_admin(incident_type, details)

    async def _handle_compromised_node(self, node_id: int):
        """Risposta a nodo compromesso"""
        # 1. Blocca immediatamente il nodo
        await self.authorization.block_node(node_id)

        # 2. Notifica altri nodi fidati
        await self.broadcast_security_alert(
            alert_type='compromised_node',
            node_id=node_id
        )

        # 3. Invalida sessioni/chiavi
        await self.key_manager.revoke_node_keys(node_id)

        # 4. Audit recente attività dal nodo
        await self.audit_node_activity(node_id)
```

---

## 9. Compliance & Audit

### 9.1 Audit Logging

```python
class SecurityAuditLog:
    """Log di audit per eventi di sicurezza"""

    def __init__(self, log_path: str):
        self.log_path = log_path
        self._ensure_log_integrity()

    def log_event(
        self,
        event_type: str,
        actor: str,
        action: str,
        target: str,
        result: str,
        details: Dict[str, Any] = None
    ):
        """Log evento di sicurezza con integrità"""
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            actor=actor,
            action=action,
            target=target,
            result=result,
            details=details or {},
            previous_hash=self._get_last_hash()
        )

        # Firma entry per integrità
        entry.hash = self._compute_entry_hash(entry)
        entry.signature = self._sign_entry(entry)

        self._write_entry(entry)

    def verify_log_integrity(self) -> bool:
        """Verifica integrità della chain di audit"""
        entries = self._read_all_entries()

        for i, entry in enumerate(entries):
            # Verifica hash
            if self._compute_entry_hash(entry) != entry.hash:
                return False

            # Verifica chain
            if i > 0 and entry.previous_hash != entries[i-1].hash:
                return False

            # Verifica firma
            if not self._verify_signature(entry):
                return False

        return True
```

### 9.2 Data Retention

```python
class DataRetentionPolicy:
    """Policy di data retention per conformità"""

    RETENTION_PERIODS = {
        'federation_messages': 90,      # giorni
        'audit_logs': 365,              # giorni
        'user_keys': 'until_rotation',
        'node_keys': 'until_rotation',
        'routing_info': 7,              # giorni
    }

    async def apply_retention_policy(self):
        """Applica policy di retention"""
        for data_type, period in self.RETENTION_PERIODS.items():
            if isinstance(period, int):
                cutoff = datetime.utcnow() - timedelta(days=period)
                await self._delete_older_than(data_type, cutoff)

    async def _delete_older_than(self, data_type: str, cutoff: datetime):
        """Elimina dati più vecchi del cutoff"""
        # Secure deletion con overwrite
        pass
```

---

## 10. Recommendations

### 10.1 Implementation Priorities

| Priority | Item | Rationale |
|----------|------|-----------|
| **P0** | E2E encryption for PM | Core privacy requirement |
| **P0** | Node authentication | Prevent impersonation |
| **P0** | Rate limiting | Prevent DoS |
| **P1** | Message signing | Integrity verification |
| **P1** | Replay protection | Prevent message replay |
| **P2** | Reputation system | Long-term trust |
| **P2** | Traffic analysis defense | Enhanced privacy |
| **P3** | Anonymity features | Optional privacy |

### 10.2 Ongoing Security Tasks

- [ ] Security audit ogni major release
- [ ] Penetration testing annuale
- [ ] Bug bounty program
- [ ] Dependency update mensili
- [ ] Security training per contributors

### 10.3 Future Considerations

1. **Post-Quantum Cryptography**: Monitorare sviluppi PQC per futura migrazione
2. **Hardware Security**: Supporto per HSM/TPM per chiavi nodo
3. **Formal Verification**: Verifica formale protocollo critico
4. **Decentralized Identity**: Integrazione con DID standards

---

## Appendix A: Security Configuration Example

```yaml
# config.yaml - Security settings
federation:
  security:
    # Authentication
    require_node_auth: true
    auth_timeout_seconds: 30
    max_auth_failures: 5
    auth_lockout_minutes: 15

    # Encryption
    require_e2e_encryption: true
    allowed_ciphers:
      - "chacha20-poly1305"
    key_rotation_days: 90

    # Rate Limiting
    rate_limiting:
      enabled: true
      announce_per_hour: 6
      sync_per_minute: 10
      pm_per_minute: 30

    # Trust
    default_trust_level: "untrusted"
    auto_trust_after_days: 30
    min_reputation_for_trust: 60

    # Audit
    audit_logging: true
    audit_log_path: "/var/log/meshbbs/audit.log"
    log_retention_days: 365
```

---

## Appendix B: Glossary

| Term | Definition |
|------|------------|
| AEAD | Authenticated Encryption with Associated Data |
| CSPRNG | Cryptographically Secure Pseudo-Random Number Generator |
| E2E | End-to-End (encryption) |
| ECDH | Elliptic Curve Diffie-Hellman |
| HKDF | HMAC-based Key Derivation Function |
| HSM | Hardware Security Module |
| N2N | Node-to-Node |
| PQC | Post-Quantum Cryptography |
| TPM | Trusted Platform Module |
