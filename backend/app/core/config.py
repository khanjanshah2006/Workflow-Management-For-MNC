"""Central application settings.

``.env`` is loaded once here and every module reads configuration from the
single ``settings`` object instead of calling ``os.getenv`` directly.
When ``ENV=production`` the settings are validated at import time, so a
misconfigured deployment refuses to start.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Load backend/.env regardless of the current working directory, then any .env in the cwd.
# Real environment variables always win over values from these files.
load_dotenv(BACKEND_DIR / ".env")
load_dotenv()

DEFAULT_JWT_SECRET = "your-secret-key-change-in-production"
DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"
MIN_JWT_SECRET_LENGTH = 32
VALID_SAMESITE = ("lax", "strict", "none")


class ConfigError(RuntimeError):
    """Raised when the configuration is unsafe or incomplete."""


def _bool(value: Optional[str], default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _int(value: Optional[str], default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value)


def _csv(value: Optional[str]) -> list[str]:
    return [item.strip().rstrip("/") for item in (value or "").split(",") if item.strip()]


def normalize_database_url(url: str) -> str:
    """Force the psycopg2 driver, which is what requirements.txt installs."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


@dataclass
class Settings:
    env: str = "development"
    testing: bool = False

    # Security
    jwt_secret_key: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    enforce_admin_mfa: bool = False
    job_token: str = ""

    # HTTP
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    enable_docs: bool = True
    max_upload_mb: int = 5
    log_level: str = "INFO"

    # Database. ``database_url_raw`` is exactly what the environment provided.
    database_url_raw: str = ""
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_connect_timeout: int = 10

    # Backups, reports and anomaly detection
    backup_dir: str = "./backups"
    pg_dump_path: str = ""
    backup_timeout_seconds: int = 300
    failed_login_threshold: int = 5
    failed_login_window_minutes: int = 15
    reports_dir: str = ""

    # Which required variables were actually present in the environment.
    _provided: frozenset = field(default_factory=frozenset, repr=False)

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> "Settings":
        e = os.environ if environ is None else environ
        provided = frozenset(
            k for k in ("JWT_SECRET_KEY", "DATABASE_URL", "CORS_ORIGINS") if (e.get(k) or "").strip()
        )
        cors = _csv(e.get("CORS_ORIGINS"))
        return cls(
            env=(e.get("ENV") or "development").strip().lower(),
            testing=_bool(e.get("TESTING"), False),
            jwt_secret_key=e.get("JWT_SECRET_KEY") or DEFAULT_JWT_SECRET,
            jwt_algorithm=e.get("JWT_ALGORITHM") or "HS256",
            access_token_expire_minutes=_int(e.get("ACCESS_TOKEN_EXPIRE_MINUTES"), 60),
            refresh_token_expire_days=_int(e.get("REFRESH_TOKEN_EXPIRE_DAYS"), 7),
            enforce_admin_mfa=_bool(e.get("ENFORCE_ADMIN_MFA"), False),
            job_token=e.get("JOB_TOKEN") or "",
            cors_origins=cors or ["http://localhost:5173"],
            cookie_secure=_bool(e.get("COOKIE_SECURE"), False),
            cookie_samesite=(e.get("COOKIE_SAMESITE") or "lax").strip().lower(),
            enable_docs=_bool(e.get("ENABLE_DOCS"), True),
            max_upload_mb=_int(e.get("MAX_UPLOAD_MB"), 5),
            log_level=(e.get("LOG_LEVEL") or "INFO").strip().upper(),
            database_url_raw=(e.get("DATABASE_URL") or "").strip(),
            db_pool_size=_int(e.get("DB_POOL_SIZE"), 5),
            db_max_overflow=_int(e.get("DB_MAX_OVERFLOW"), 5),
            db_connect_timeout=_int(e.get("DB_CONNECT_TIMEOUT"), 10),
            backup_dir=e.get("BACKUP_DIR") or "./backups",
            pg_dump_path=e.get("PG_DUMP_PATH") or "",
            backup_timeout_seconds=_int(e.get("BACKUP_TIMEOUT_SECONDS"), 300),
            failed_login_threshold=_int(e.get("FAILED_LOGIN_THRESHOLD"), 5),
            failed_login_window_minutes=_int(e.get("FAILED_LOGIN_WINDOW_MINUTES"), 15),
            reports_dir=e.get("REPORTS_DIR") or "",
            _provided=provided,
        )

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def database_url(self) -> str:
        return normalize_database_url(self.database_url_raw or DEFAULT_DATABASE_URL)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def refresh_cookie_max_age(self) -> int:
        return self.refresh_token_expire_days * 24 * 3600

    def validate(self) -> "Settings":
        if self.env not in ("development", "production"):
            raise ConfigError(f"ENV must be 'development' or 'production', got '{self.env}'")
        if self.cookie_samesite not in VALID_SAMESITE:
            raise ConfigError(f"COOKIE_SAMESITE must be one of {', '.join(VALID_SAMESITE)}")
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ConfigError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")

        if self.is_production:
            missing = [k for k in ("JWT_SECRET_KEY", "DATABASE_URL", "CORS_ORIGINS") if k not in self._provided]
            if missing:
                raise ConfigError(f"Missing required production settings: {', '.join(missing)}")
            if self.jwt_secret_key == DEFAULT_JWT_SECRET:
                raise ConfigError("JWT_SECRET_KEY is still the default value")
            if len(self.jwt_secret_key) < MIN_JWT_SECRET_LENGTH:
                raise ConfigError(f"JWT_SECRET_KEY must be at least {MIN_JWT_SECRET_LENGTH} characters")
        return self


settings = Settings.from_env().validate()
