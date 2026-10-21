from typing import List, Optional, Literal
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator, Field
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
    WEBHOOK_PROVIDER: str = Field('florasecure-simulator', pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
    WEBHOOK_TIMESTAMP_TOLERANCE: int = Field(300, ge=0, le=900)
    WEBHOOK_MAX_BODY_BYTES: int = Field(65536, ge=1024, le=1048576)
    WEBHOOK_PREVIOUS_SECRET: Optional[str] = None
    WEBHOOK_PREVIOUS_START: int = 0
    WEBHOOK_PREVIOUS_UNTIL: int = 0

    @model_validator(mode='after')
    def validate_webhook_overlap(self):
        if self.WEBHOOK_PREVIOUS_SECRET:
            if len(self.WEBHOOK_PREVIOUS_SECRET) < 32 or self.WEBHOOK_PREVIOUS_SECRET == self.WEBHOOK_SECRET:
                raise ValueError('Previous webhook key must be strong and different')
            if not 0 < self.WEBHOOK_PREVIOUS_UNTIL-self.WEBHOOK_PREVIOUS_START <= 900:
                raise ValueError('Previous webhook key requires an explicit overlap of at most 900 seconds')
        elif self.WEBHOOK_PREVIOUS_START or self.WEBHOOK_PREVIOUS_UNTIL:
            raise ValueError('Overlap timestamps require a previous key')
        return self

    # Optional production IdP settings
    KEYCLOAK_REALM: Optional[str] = None
    KEYCLOAK_CLIENT_ID: Optional[str] = None
    KEYCLOAK_SERVER_URL: Optional[str] = None
    KEYCLOAK_ISSUER: Optional[str] = None
    # Explicit release selection; failure never changes this mode or accepts legacy JWTs.
    AUTH_MODE: Literal["legacy", "oidc"] = "legacy"
    OIDC_ISSUER: Optional[str] = None
    OIDC_AUDIENCE: str = "florasecure-api"
    OIDC_CLIENT_ID: str = "florasecure-spa"
    OIDC_CA_FILE: Optional[str] = None
    OIDC_JWKS_TTL: int = Field(60, ge=1, le=300)
    OIDC_JWKS_REFRESH_INTERVAL: int = Field(5, ge=1, le=60)

    @model_validator(mode="after")
    def validate_oidc(self):
        if self.AUTH_MODE == "oidc":
            parsed = urlsplit(self.OIDC_ISSUER or "")
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                    parsed.password or parsed.query or parsed.fragment or
                    not parsed.path.startswith("/realms/") or self.OIDC_ISSUER.endswith("/")):
                raise ValueError("OIDC mode requires one exact trusted HTTPS realm issuer")
            if not self.OIDC_AUDIENCE or not self.OIDC_CLIENT_ID:
                raise ValueError("OIDC audience and client must be configured")
        return self

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
