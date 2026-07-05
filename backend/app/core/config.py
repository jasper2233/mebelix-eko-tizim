import os
from enum import StrEnum

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Defaults referenced both by `Settings` field defaults and by the production-readiness validator below.
_DEFAULT_SECRET_KEY = "secret-key-change-in-production"
_DEFAULT_ADMIN_PASSWORD = "!Ch4ng3Th1sP4ssW0rd!"
_DEFAULT_ADMIN_PHONE = "+998901234567"
_DEFAULT_POSTGRES_PASSWORD = "postgres"


class EnvironmentOption(StrEnum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """All application settings, flat. Grouped by `# === Section ===` comments for readability only."""

    # === Application ===
    APP_NAME: str = "FastAPI Fullstack Boilerplate"
    APP_DESCRIPTION: str | None = (
        "A production-ready FastAPI boilerplate with authentication, database, and async task queue."
    )
    APP_VERSION: str | None = "0.1.0"
    LICENSE_NAME: str | None = "MIT"
    CONTACT_NAME: str | None = None
    CONTACT_EMAIL: str | None = None

    # === Crypto / JWT ===
    SECRET_KEY: SecretStr = SecretStr(_DEFAULT_SECRET_KEY)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12

    # === PostgreSQL ===
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = _DEFAULT_POSTGRES_PASSWORD
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "postgres"
    POSTGRES_ASYNC_PREFIX: str = "postgresql+asyncpg://"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # === First admin user (created on startup) ===
    ADMIN_NAME: str = "admin"
    ADMIN_PHONE: str = _DEFAULT_ADMIN_PHONE
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = _DEFAULT_ADMIN_PASSWORD

    # === Redis (caching, queue, rate limit) ===
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    ENABLE_REDIS_QUEUE: bool = True
    ENABLE_REDIS_RATE_LIMIT: bool = True

    # === Rate-limit defaults ===
    DEFAULT_RATE_LIMIT_LIMIT: int = 10
    DEFAULT_RATE_LIMIT_PERIOD: int = 3600
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_PERIOD: int = 300

    # === Pagination ===
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 100

    # === Startup probes ===
    STARTUP_RETRY_MAX_ATTEMPTS: int = 5
    STARTUP_RETRY_DELAY_SECONDS: int = 2

    # === Threadpool ===
    THREADPOOL_TOKENS: int = 100  # AnyIO sync-bridge slots; raise if blocking calls back up.

    # === Reverse-proxy trust ===
    # Comma-separated list of upstream IPs whose X-Forwarded-* headers we trust.
    # `*` is permissive — appropriate when Caddy/nginx is the only path to the app.
    FORWARDED_ALLOW_IPS: list[str] = ["*"]

    # === Environment / CORS ===
    ENVIRONMENT: EnvironmentOption = EnvironmentOption.LOCAL
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    CORS_METHODS: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    CORS_HEADERS: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..", "..", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def POSTGRES_URI(self) -> str:
        credentials = f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
        location = f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        return f"{credentials}@{location}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}"


def _validate_production_settings(s: Settings) -> None:
    """Refuse to boot with insecure defaults in production. Caught at startup, not at first request."""
    if s.ENVIRONMENT != EnvironmentOption.PRODUCTION:
        return
    problems: list[str] = []
    if s.SECRET_KEY.get_secret_value() == _DEFAULT_SECRET_KEY:
        problems.append("SECRET_KEY is the default placeholder")
    if s.ADMIN_PASSWORD == _DEFAULT_ADMIN_PASSWORD:
        problems.append("ADMIN_PASSWORD is the default placeholder")
    if s.POSTGRES_PASSWORD == _DEFAULT_POSTGRES_PASSWORD:
        problems.append("POSTGRES_PASSWORD is the default placeholder")
    if s.ADMIN_PHONE == _DEFAULT_ADMIN_PHONE:
        problems.append("ADMIN_PHONE is the default placeholder")
    if problems:
        raise RuntimeError("Refusing to boot in production with insecure defaults: " + "; ".join(problems))


settings = Settings()
_validate_production_settings(settings)
