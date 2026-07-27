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
    APP_NAME: str = "MebeliX"
    APP_VERSION: str = "0.1.0"  # reported by /health and /ready

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

    # === Rate limit ===
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 5
    LOGIN_RATE_LIMIT_PERIOD: int = 300

    # === Pagination ===
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 100

    # === File storage ===
    UPLOAD_DIR: str = "uploads"  # project/scx/label files root (TZ 2.4.3); S3 mount later if needed
    MAX_PROJECT_FILE_SIZE: int = 50 * 1024 * 1024  # .project files in the corpus are < 5 MB

    # === Production floor (TZ 7–8) ===
    STRICT_STAGE_ORDER: bool = False  # E004: block scan until the previous stage is done (optional, TZ 7.2.5)
    SESSION_MAX_HOURS: int = 12  # operator shift timeout (TZ 8.5 E005)
    SCAN_UNDO_SECONDS: int = 60  # BEKOR QILISH window (TZ 8.6)

    # === Printing (TZ 12.3 / 13.2) ===
    # Yorliqlar bridge-agent navbati orqali USB GoDEX'ga boradi (G500-U'da tarmoq porti yo'q).
    # Legacy back-compat: printerlar admin paneldagi pairing tokeni bilan ulanadi
    # (bridge_agent.token_hash). Bu bo'sh bo'lsa ham /ws/bridge ishlayveradi.
    BRIDGE_TOKEN: str = ""

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
    """Refuse to boot with insecure defaults in any non-local environment (staging included)."""
    if s.ENVIRONMENT == EnvironmentOption.LOCAL:
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
