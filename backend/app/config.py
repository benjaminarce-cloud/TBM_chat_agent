from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator, model_validator
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
    database_url_unpooled: str | None = None
    anthropic_api_key: str = ""
    anthropic_sonnet_model: str = "claude-sonnet-4-5"
    anthropic_haiku_model: str = "claude-haiku-4-5"
    openai_api_key: str = ""
    computer_use_enabled: bool = False
    computer_use_model: str = "gpt-5.6"
    computer_use_api_token: str = ""
    computer_use_allowed_domains: str = ""
    computer_use_max_steps: int = Field(default=8, ge=1, le=12)
    computer_use_max_output_tokens: int = Field(default=1_000, ge=100, le=2_000)
    computer_use_timeout_seconds: int = Field(default=90, ge=10, le=180)
    computer_use_max_concurrency: int = Field(default=1, ge=1, le=4)
    computer_use_rate_limit_capacity: int = Field(default=3, ge=1, le=20)
    computer_use_rate_limit_refill_per_minute: float = Field(default=0.5, gt=0, le=10)

    widget_token_secret: str = "development-only-change-me-32-characters"
    ip_hash_salt: str = "development-only-ip-hash-salt"
    allowed_widget_origins: str = "http://localhost:3000"
    allowed_parent_origins: str = "http://localhost:3000"
    widget_token_ttl_seconds: int = 60 * 60 * 6
    privacy_notice_version: str = "development-placeholder-v0"

    consent_rate_limit_capacity: int = Field(default=5, ge=1, le=20)
    consent_rate_limit_refill_per_minute: float = Field(default=1, gt=0, le=20)
    feedback_rate_limit_capacity: int = Field(default=5, ge=1, le=20)
    feedback_rate_limit_refill_per_minute: float = Field(default=1, gt=0, le=20)

    session_message_cap: int = Field(default=20, ge=1, le=20)
    ip_rate_limit_capacity: int = Field(default=30, ge=1)
    ip_rate_limit_refill_per_minute: float = Field(default=10, gt=0)
    session_rate_limit_capacity: int = Field(default=10, ge=1)
    session_rate_limit_refill_per_minute: float = Field(default=5, gt=0)

    transcript_retention_days: int = Field(default=90, ge=1, le=365)
    uncaptured_retention_days: int = Field(default=90, ge=1, le=365)
    captured_lead_retention_days: int = Field(default=365, ge=1, le=2555)

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

    @field_validator("database_url", "database_url_unpooled", mode="before")
    @classmethod
    def normalize_postgres_url_for_asyncpg(cls, value: str | None) -> str | None:
        """Adapt provider-standard libpq URLs to SQLAlchemy's asyncpg dialect."""
        if not value:
            return value
        parts = urlsplit(value)
        if parts.scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}:
            return value
        query: list[tuple[str, str]] = []
        for key, item in parse_qsl(parts.query, keep_blank_values=True):
            if key == "channel_binding":
                continue
            query.append(("ssl" if key == "sslmode" else key, item))
        return urlunsplit(
            (
                "postgresql+asyncpg",
                parts.netloc,
                parts.path,
                urlencode(query),
                parts.fragment,
            )
        )

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

    @property
    def computer_domains(self) -> set[str]:
        return {
            item.strip().lower().rstrip(".")
            for item in self.computer_use_allowed_domains.split(",")
            if item.strip()
        }

    @staticmethod
    def _is_https_origin(value: str) -> bool:
        try:
            parsed = urlsplit(value)
            return (
                parsed.scheme == "https"
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
                and parsed.path in {"", "/"}
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            return False

    @staticmethod
    def _database_uses_tls(value: str) -> bool:
        try:
            query = dict(parse_qsl(urlsplit(value).query))
            return query.get("ssl", "").lower() in {
                "1",
                "true",
                "require",
                "verify-ca",
                "verify-full",
            }
        except ValueError:
            return False

    @model_validator(mode="after")
    def reject_development_secrets_in_production(self) -> "Settings":
        if self.environment.lower() == "production":
            if self.widget_token_secret.startswith("development-only"):
                raise ValueError("WIDGET_TOKEN_SECRET must be replaced in production")
            if self.ip_hash_salt.startswith("development-only"):
                raise ValueError("IP_HASH_SALT must be replaced in production")
            if not self.anthropic_api_key:
                raise ValueError("ANTHROPIC_API_KEY is required in production")
            if self.privacy_notice_version.startswith("development-"):
                raise ValueError("PRIVACY_NOTICE_VERSION must identify the approved notice")
            if not self._database_uses_tls(self.database_url):
                raise ValueError("DATABASE_URL must require TLS in production")
            if self.database_url_unpooled and not self._database_uses_tls(
                self.database_url_unpooled
            ):
                raise ValueError("DATABASE_URL_UNPOOLED must require TLS in production")
            if not self.widget_origins or not all(
                self._is_https_origin(origin) for origin in self.widget_origins
            ):
                raise ValueError("ALLOWED_WIDGET_ORIGINS must contain only HTTPS origins")
            if not self.parent_origins or not all(
                self._is_https_origin(origin) for origin in self.parent_origins
            ):
                raise ValueError("ALLOWED_PARENT_ORIGINS must contain only HTTPS origins")
            if self.computer_use_enabled and (
                not self.openai_api_key
                or not self.computer_use_api_token
                or len(self.computer_use_api_token) < 32
                or not self.computer_domains
            ):
                raise ValueError(
                    "OPENAI_API_KEY, a 32+ character COMPUTER_USE_API_TOKEN, and "
                    "COMPUTER_USE_ALLOWED_DOMAINS are required when computer use is enabled"
                )
            if self.computer_use_enabled and any(
                "*" in domain or "/" in domain or ":" in domain or domain.startswith(".")
                for domain in self.computer_domains
            ):
                raise ValueError("COMPUTER_USE_ALLOWED_DOMAINS must use exact hostnames")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
