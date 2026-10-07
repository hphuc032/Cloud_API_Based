from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    DEBUG: bool = False
    PROJECT_NAME: str = "Cloud API Security - NT219"
    API_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Webhook
    WEBHOOK_SECRET: str

    # Optional production IdP settings
    KEYCLOAK_REALM: Optional[str] = None
    KEYCLOAK_CLIENT_ID: Optional[str] = None
    KEYCLOAK_SERVER_URL: Optional[str] = None
    KEYCLOAK_ISSUER: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("SECRET_KEY", "WEBHOOK_SECRET")
    @classmethod
    def validate_secret(cls, value: str, info):
        weak_values = {
            "secret",
            "changeme",
            "change-me",
            "change-me-in-production",
            "default-webhook-secret-change-me",
            "my_super_secret_key_change_this_in_production",
            "change_this_to_a_long_random_secret_key",
            "change_this_to_a_long_random_webhook_secret",
        }

        if value in weak_values or len(value) < 32:
            raise ValueError(f"{info.field_name} must be a strong secret with at least 32 characters")

        return value


settings = Settings()