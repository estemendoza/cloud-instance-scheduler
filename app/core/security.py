import secrets
import string

import bcrypt


def _hash(secret: str) -> str:
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()


def _verify(secret: str, hashed: str) -> bool:
    return bcrypt.checkpw(secret.encode(), hashed.encode())


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return _hash(password)


def generate_api_key() -> str:
    """Generates a random 32-character API key string."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(32))


def get_api_key_hash(api_key: str) -> str:
    """Hashes an API key for storage."""
    return _hash(api_key)


def verify_api_key(plain_api_key: str, hashed_api_key: str) -> bool:
    """Verifies an API key against its hash."""
    return _verify(plain_api_key, hashed_api_key)
