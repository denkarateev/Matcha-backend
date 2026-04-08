from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # -----------------------------------------------------------------------
    # Application
    # -----------------------------------------------------------------------
    app_name: str = "MATCHA Backend"
    env: Literal["development", "staging", "production"] = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    api_v1_prefix: str = "/api/v1"

    # All server-side timestamps are in WITA (UTC+8) for Bali
    business_timezone: str = "Asia/Makassar"

    seed_demo_data: bool = False

    # -----------------------------------------------------------------------
    # Repository backend
    # -----------------------------------------------------------------------
    use_db_repos: bool = False  # USE_DB_REPOS=true → PostgreSQL repositories

    # -----------------------------------------------------------------------
    # Database (PostgreSQL via asyncpg)
    # -----------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://matcha:matcha_dev@localhost:5432/matcha",
        description=(
            "Full async DSN — must start with 'postgresql+asyncpg://'. "
            "Set via DATABASE_URL env var."
        ),
    )

    @field_validator("database_url")
    @classmethod
    def _validate_db_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL DSN "
                "(e.g. postgresql+asyncpg://user:pass@host/db)"
            )
        # Auto-upgrade plain postgres:// → postgresql+asyncpg://
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    # -----------------------------------------------------------------------
    # Redis
    # -----------------------------------------------------------------------
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis DSN for rate-limits, sessions, ephemeral counters.",
    )

    # -----------------------------------------------------------------------
    # JWT / Auth
    # -----------------------------------------------------------------------
    secret_key: str = Field(
        default="CHANGE-ME-IN-PRODUCTION-use-a-random-32-byte-hex-string",
        description="HMAC secret for signing JWT tokens.",
    )
    jwt_algorithm: str = "HS256"
    # Access token lifetime in minutes (default: 24 h)
    access_token_expire_minutes: int = 60 * 24

    # -----------------------------------------------------------------------
    # Admin panel
    # -----------------------------------------------------------------------
    admin_token: str = "matcha-admin-2026"

    # -----------------------------------------------------------------------
    # Media storage (local or S3)
    # -----------------------------------------------------------------------
    media_root: str = "/opt/matcha-backend/data/media"
    storage_backend: str = "local"  # "local" or "s3"
    s3_bucket: str = ""
    s3_region: str = "eu-central-1"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_endpoint_url: str = ""  # for MinIO or other S3-compatible

    # -----------------------------------------------------------------------
    # Pydantic Settings config
    # -----------------------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        # No prefix — env vars match field names directly:
        #   DATABASE_URL, REDIS_URL, SECRET_KEY, etc.
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
