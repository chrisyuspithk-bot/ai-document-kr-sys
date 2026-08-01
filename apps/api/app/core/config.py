"""Application settings.

All values can be overridden via environment variables prefixed with ``AIDG_``
or a ``.env`` file. See the repository root ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AIDG_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Core ---
    app_name: str = "AIDG & KR System API"
    environment: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Infrastructure ---
    database_url: str = "postgresql+asyncpg://aidg:aidg@localhost:5432/aidg"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "aidg-documents"
    # auto = S3 when s3_endpoint is set, otherwise local disk
    storage_backend: str = "auto"
    local_storage_root: str = "data/uploads"

    # --- Security / JWT ---
    jwt_secret: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- OIDC (Microsoft Entra ID) — optional ---
    oidc_enabled: bool = False
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_audience: str | None = None

    # --- Seeding ---
    seed_admin_password: str = "admin1234!"

    # --- LLM providers ---
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    jina_api_key: str | None = None
    jina_embedding_model: str = "jina-embeddings-v3"
    jina_embedding_base_url: str = "https://api.jina.ai/v1"

    # --- Speech-to-text ---
    # openrouter (default) | mock | qwen_asr
    stt_provider: str = "openrouter"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Audio-capable model. Qwen text models (e.g. qwen3.7-flash) reject audio
    # input on OpenRouter (HTTP 404), so the default is a verified audio model.
    openrouter_asr_model: str = "mistralai/voxtral-small-24b-2507"
    qwen_asr_api_key: str | None = None
    qwen_asr_base_url: str | None = None
    azure_speech_key: str | None = None
    azure_speech_region: str | None = None

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip().strip("[]")
            return [part.strip().strip("\"'") for part in cleaned.split(",") if part.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
