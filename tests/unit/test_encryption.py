import pytest

from app.services.encryption import encrypt_credentials, decrypt_credentials, get_encryption_key


class TestEncryptDecrypt:
    def test_roundtrip_simple(self):
        data = {"key": "value"}
        assert decrypt_credentials(encrypt_credentials(data)) == data

    def test_roundtrip_nested(self):
        data = {
            "aws": {"access_key_id": "AKIA...", "secret_access_key": "..."},
            "region": "us-east-1",
        }
        assert decrypt_credentials(encrypt_credentials(data)) == data

    def test_roundtrip_empty_dict(self):
        assert decrypt_credentials(encrypt_credentials({})) == {}

    def test_roundtrip_special_chars(self):
        data = {"password": "p@$$w0rd!&*\"'\n\ttab"}
        assert decrypt_credentials(encrypt_credentials(data)) == data

    def test_encrypt_nondeterministic(self):
        data = {"key": "value"}
        assert encrypt_credentials(data) != encrypt_credentials(data)


class TestGetEncryptionKey:
    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.ENCRYPTION_KEY", "")
        with pytest.raises(ValueError, match="ENCRYPTION_KEY not set"):
            get_encryption_key()
