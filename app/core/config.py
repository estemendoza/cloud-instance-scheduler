from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Cloud Instance Scheduler"
    API_V1_STR: str = "/api/v1"

    # Validation is stricter in newer Pydantic versions.
    # We can default to localhost for development if needed,
    # but production should override.
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "cis"
    POSTGRES_PORT: int = 5432

    # Security
    ENCRYPTION_KEY: str = ""  # Fernet key for encrypting credentials

    # JWT Settings
    JWT_SECRET_KEY: str = ""  # Required for JWT tokens - set in .env
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Pricing Update Schedule (daily at specified UTC time)
    PRICING_UPDATE_HOUR_UTC: int = 2
    PRICING_UPDATE_MINUTE_UTC: int = 0

    # CORS - set to True in production behind nginx proxy
    CORS_ALLOW_ALL_ORIGINS: bool = False

    # Disable OpenAPI docs in production
    DISABLE_DOCS: bool = False

    # Constructed database URL
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}"
            f"/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(
        case_sensitive=True, env_file=".env", extra="ignore")


settings = Settings()
