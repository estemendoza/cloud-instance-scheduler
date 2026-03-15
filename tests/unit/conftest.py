import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    """Provide a valid Fernet key for every unit test."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr("app.core.config.settings.ENCRYPTION_KEY", key)
