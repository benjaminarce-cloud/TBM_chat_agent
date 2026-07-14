from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tbm_chat"
    anthropic_api_key: str = ""
    anthropic_sonnet_model: str = "claude-sonnet-4-5"
    anthropic_haiku_model: str = "claude-haiku-4-5"

    widget_token_secret: str = "development-only-change-me-32-characters"
    ip_hash_salt: str = "development-only-ip-hash-salt"
    allowed_widget_origins: str = "http://localhost:3000"
    allowed_parent_origins: str = "http://localhost:3000"
    widget_token_ttl_seconds: int = 60 * 60 * 6

    session_message_cap: int = Field(default=20, ge=1, le=20)
    ip_rate_limit_capacity: int = Field(default=30, ge=1)
    ip_rate_limit_refill_per_minute: float = Field(default=10, gt=0)
    session_rate_limit_capacity: int = Field(default=10, ge=1)
    session_rate_limit_refill_per_minute: float = Field(default=5, gt=0)

    sonnet_max_tokens: int = Field(default=400, ge=1, le=400)
    haiku_max_tokens: int = Field(default=350, ge=1, le=350)

    resend_api_key: str = ""
    handoff_from_email: str = ""
    handoff_to_email: str = ""
    admin_alert_email: str = ""
    daily_session_alert_threshold: int | None = Field(default=None, gt=0)
    daily_spend_alert_usd: float | None = Field(default=None, gt=0)

    sonnet_input_cost_per_million: float | None = Field(default=None, ge=0)
    sonnet_output_cost_per_million: float | None = Field(default=None, ge=0)
    haiku_input_cost_per_million: float | None = Field(default=None, ge=0)
    haiku_output_cost_per_million: float | None = Field(default=None, ge=0)

    kb_compiled_path: Path = Path(__file__).resolve().parents[1] / "kb" / "compiled.md"
    kb_version_path: Path = Path(__file__).resolve().parents[1] / "kb" / "VERSION"

    @property
    def widget_origins(self) -> set[str]:
        return {
            item.strip().rstrip("/")
            for item in self.allowed_widget_origins.split(",")
            if item.strip()
        }

    @property
    def parent_origins(self) -> set[str]:
        return {
            item.strip().rstrip("/")
            for item in self.allowed_parent_origins.split(",")
            if item.strip()
        }

    @model_validator(mode="after")
    def reject_development_secrets_in_production(self) -> "Settings":
        if self.environment.lower() == "production":
            if self.widget_token_secret.startswith("development-only"):
                raise ValueError("WIDGET_TOKEN_SECRET must be replaced in production")
            if self.ip_hash_salt.startswith("development-only"):
                raise ValueError("IP_HASH_SALT must be replaced in production")
            if not self.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is required in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
