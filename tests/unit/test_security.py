from app.core.security import generate_api_key, get_api_key_hash, verify_api_key


class TestGenerateApiKey:
    def test_length(self):
        assert len(generate_api_key()) == 32

    def test_alphanumeric(self):
        assert generate_api_key().isalnum()

    def test_uniqueness(self):
        assert generate_api_key() != generate_api_key()


class TestApiKeyHashVerify:
    def test_roundtrip(self):
        key = generate_api_key()
        hashed = get_api_key_hash(key)
        assert verify_api_key(key, hashed) is True

    def test_wrong_key(self):
        key_a = generate_api_key()
        key_b = generate_api_key()
        assert verify_api_key(key_b, get_api_key_hash(key_a)) is False
