from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    RABBITMQ_URL: str
    API_KEY: SecretStr
    WEBHOOK_TIMEOUT_SECONDS: float = 5.0
    WEBHOOK_MAX_ATTEMPTS: int = 3
    OUTBOX_POLL_INTERVAL: float = 2.0
    OUTBOX_BATCH_SIZE: int = 20
    OUTBOX_LOCK_SECONDS: int = 60

    @field_validator("DATABASE_URL", "RABBITMQ_URL")
    @classmethod
    def strip_urls(cls, value: str) -> str:
        return value.strip()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
