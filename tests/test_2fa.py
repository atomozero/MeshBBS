"""
Tests for Two-Factor Authentication (2FA).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
import time
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from web.auth.totp import (
    generate_secret,
    get_totp_token,
    verify_totp,
    get_provisioning_uri,
    generate_backup_codes,
    hash_backup_code,
    verify_backup_code,
    TOTPManager,
)
from web.auth.jwt import (
    create_2fa_pending_token,
    decode_2fa_pending_token,
)


class TestTOTPGeneration:
    """Test TOTP token generation."""

    def test_generate_secret(self):
        """Test generating a TOTP secret."""
        secret = generate_secret()
        assert len(secret) >= 32
        # Base32 characters only
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in secret)

    def test_generate_secret_unique(self):
        """Test that secrets are unique."""
        secrets = [generate_secret() for _ in range(10)]
        assert len(set(secrets)) == 10

    def test_get_totp_token(self):
        """Test generating a TOTP token."""
        secret = generate_secret()
        token = get_totp_token(secret)

        assert len(token) == 6
        assert token.isdigit()

    def test_totp_token_changes(self):
        """Test that TOTP tokens change over time periods."""
        secret = generate_secret()

        # Get tokens for different time offsets
        token_current = get_totp_token(secret, 0)
        token_next = get_totp_token(secret, 1)
        token_prev = get_totp_token(secret, -1)

        # At least one should be different
        tokens = [token_current, token_next, token_prev]
        assert len(set(tokens)) >= 2


class TestTOTPVerification:
    """Test TOTP verification."""

    def test_verify_current_token(self):
        """Test verifying current token."""
        secret = generate_secret()
        token = get_totp_token(secret)

        assert verify_totp(secret, token) is True

    def test_verify_with_window(self):
        """Test verification with time window."""
        secret = generate_secret()

        # Previous period token should be valid
        prev_token = get_totp_token(secret, -1)
        assert verify_totp(secret, prev_token, window=1) is True

        # Next period token should be valid
        next_token = get_totp_token(secret, 1)
        assert verify_totp(secret, next_token, window=1) is True

    def test_verify_invalid_token(self):
        """Test rejecting invalid token."""
        secret = generate_secret()

        assert verify_totp(secret, "000000") is False
        assert verify_totp(secret, "invalid") is False
        assert verify_totp(secret, "") is False
        assert verify_totp(secret, "12345") is False  # Too short

    def test_verify_wrong_secret(self):
        """Test rejecting token for wrong secret."""
        secret1 = generate_secret()
        secret2 = generate_secret()

        token = get_totp_token(secret1)
        assert verify_totp(secret2, token) is False


class TestProvisioningURI:
    """Test provisioning URI generation."""

    def test_provisioning_uri_format(self):
        """Test URI format."""
        secret = generate_secret()
        uri = get_provisioning_uri(secret, "testuser")

        assert uri.startswith("otpauth://totp/")
        assert "MeshBBS%3Atestuser" in uri or "MeshBBS:testuser" in uri
        assert f"secret={secret}" in uri
        assert "issuer=MeshBBS" in uri

    def test_provisioning_uri_contains_params(self):
        """Test URI contains required parameters."""
        secret = "TESTSECRET12345678"
        uri = get_provisioning_uri(secret, "admin")

        assert "algorithm=SHA1" in uri
        assert "digits=6" in uri
        assert "period=30" in uri


class TestBackupCodes:
    """Test backup code generation and verification."""

    def test_generate_backup_codes(self):
        """Test generating backup codes."""
        codes = generate_backup_codes()

        assert len(codes) == 10
        for code in codes:
            # Format: XXXX-XXXX
            assert len(code) == 9
            assert code[4] == "-"
            assert code[:4].isalnum()
            assert code[5:].isalnum()

    def test_generate_backup_codes_count(self):
        """Test generating custom count."""
        codes = generate_backup_codes(count=5)
        assert len(codes) == 5

    def test_hash_backup_code(self):
        """Test hashing backup codes."""
        code = "ABCD-1234"
        hash1 = hash_backup_code(code)

        # Should be SHA256 hex
        assert len(hash1) == 64
        assert all(c in "0123456789abcdef" for c in hash1)

        # Same code = same hash
        hash2 = hash_backup_code(code)
        assert hash1 == hash2

        # Normalized (case insensitive, dashes removed)
        hash3 = hash_backup_code("abcd1234")
        assert hash1 == hash3

    def test_verify_backup_code(self):
        """Test verifying backup codes."""
        codes = generate_backup_codes(count=3)
        hashed = [hash_backup_code(c) for c in codes]

        # Should find valid code
        result = verify_backup_code(codes[0], hashed)
        assert result is not None
        assert result in hashed

        # Should reject invalid code
        result = verify_backup_code("XXXX-YYYY", hashed)
        assert result is None


class TestTOTPManager:
    """Test TOTPManager class."""

    def test_setup(self):
        """Test 2FA setup."""
        manager = TOTPManager()

        secret, uri, codes = manager.setup("testuser")

        assert manager.is_enabled is True
        assert len(secret) >= 32
        assert "otpauth://" in uri
        assert len(codes) == 10
        assert manager.backup_codes_remaining == 10

    def test_verify_totp(self):
        """Test verifying TOTP."""
        manager = TOTPManager()
        secret, _, _ = manager.setup("testuser")

        token = get_totp_token(secret)
        assert manager.verify(token) is True
        assert manager.verify("000000") is False

    def test_verify_backup(self):
        """Test verifying and consuming backup code."""
        manager = TOTPManager()
        _, _, codes = manager.setup("testuser")

        # Verify backup code
        assert manager.verify_backup(codes[0]) is True
        assert manager.backup_codes_remaining == 9

        # Same code should not work again
        assert manager.verify_backup(codes[0]) is False
        assert manager.backup_codes_remaining == 9

    def test_regenerate_backup_codes(self):
        """Test regenerating backup codes."""
        manager = TOTPManager()
        _, _, old_codes = manager.setup("testuser")

        # Use some codes
        manager.verify_backup(old_codes[0])
        manager.verify_backup(old_codes[1])
        assert manager.backup_codes_remaining == 8

        # Regenerate
        new_codes = manager.regenerate_backup_codes()
        assert len(new_codes) == 10
        assert manager.backup_codes_remaining == 10

        # Old codes shouldn't work
        assert manager.verify_backup(old_codes[2]) is False


class Test2FAPendingToken:
    """Test 2FA pending JWT tokens."""

    def test_create_pending_token(self):
        """Test creating a pending token."""
        token = create_2fa_pending_token(
            admin_id=123,
            secret_key="test_secret",
            expire_minutes=5,
        )

        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_pending_token(self):
        """Test decoding a pending token."""
        token = create_2fa_pending_token(
            admin_id=456,
            secret_key="test_secret",
        )

        admin_id = decode_2fa_pending_token(token, "test_secret")
        assert admin_id == 456

    def test_decode_wrong_secret(self):
        """Test decoding with wrong secret fails."""
        token = create_2fa_pending_token(
            admin_id=789,
            secret_key="correct_secret",
        )

        admin_id = decode_2fa_pending_token(token, "wrong_secret")
        assert admin_id is None

    def test_decode_expired_token(self):
        """Test expired token is rejected."""
        # Create token that expires immediately
        token = create_2fa_pending_token(
            admin_id=123,
            secret_key="test_secret",
            expire_minutes=0,  # Already expired
        )

        # Wait a moment
        time.sleep(0.1)

        admin_id = decode_2fa_pending_token(token, "test_secret")
        # Token should be expired
        # Note: 0 minutes means it expires at creation time
        assert admin_id is None


class TestIntegration:
    """Integration tests for 2FA flow."""

    def test_full_setup_and_verify_flow(self):
        """Test complete 2FA setup and verification flow."""
        manager = TOTPManager()

        # Step 1: Setup
        secret, uri, backup_codes = manager.setup("admin")

        # Step 2: User scans QR code and enters token
        token = get_totp_token(secret)
        assert manager.verify(token) is True

        # Step 3: User can also use backup code
        assert manager.verify_backup(backup_codes[0]) is True

    def test_recovery_with_backup_code(self):
        """Test recovery using backup code."""
        manager = TOTPManager()
        secret, _, backup_codes = manager.setup("user")

        # Simulate lost phone - use backup code
        assert manager.verify_backup(backup_codes[5]) is True

        # Can still use TOTP
        token = get_totp_token(secret)
        assert manager.verify(token) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
