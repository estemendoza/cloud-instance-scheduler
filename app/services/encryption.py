from cryptography.fernet import Fernet
import json
from typing import Dict, Any
from app.core.config import settings

# Generate encryption key with: Fernet.generate_key()
# Store in environment variable: ENCRYPTION_KEY


def get_encryption_key() -> bytes:
    """Get encryption key from settings."""
    # For MVP, we'll use a key from environment
    # In production, use a proper key management service
    key = getattr(settings, 'ENCRYPTION_KEY', None)
    if not key:
        raise ValueError("ENCRYPTION_KEY not set in environment")

    if isinstance(key, str):
        key = key.encode()

    return key


def encrypt_credentials(data: Dict[str, Any]) -> str:
    """
    Encrypt credential data for storage.

    Args:
        data: Dictionary of credential data

    Returns:
        Encrypted string
    """
    key = get_encryption_key()
    fernet = Fernet(key)

    # Convert dict to JSON string
    json_str = json.dumps(data)

    # Encrypt
    encrypted = fernet.encrypt(json_str.encode())

    return encrypted.decode()


def decrypt_credentials(encrypted: str) -> Dict[str, Any]:
    """
    Decrypt stored credentials.

    Args:
        encrypted: Encrypted credential string

    Returns:
        Decrypted dictionary
    """
    key = get_encryption_key()
    fernet = Fernet(key)

    # Decrypt
    decrypted = fernet.decrypt(encrypted.encode())

    # Parse JSON
    return json.loads(decrypted.decode())
