import secrets
import warnings
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use top level .env file (one level above ./backend/)
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    # Optional public frontend URL (e.g., https://app.example.com)
    FRONTEND_HOST: str | None = None
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    
    # Force strict startup behavior (exit if DB unavailable) even in development
    FORCE_STRICT_STARTUP: bool = False

    # Optional comma-separated list or JSON list of extra CORS origins via env
    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        """Return the finalized list of allowed CORS origins.

        Always include localhost dev origins on :5174, optionally include FRONTEND_HOST
        (production/staging), and merge any extra origins from BACKEND_CORS_ORIGINS.
        Trailing slashes are stripped; order is stable.
        """
        dev_origins = {"http://localhost:5174", "http://127.0.0.1:5174"}

        extras: set[str] = set()
        for o in (self.BACKEND_CORS_ORIGINS or []):
            try:
                extras.add(str(o).rstrip("/"))
            except Exception:
                continue

        prod_host: set[str] = set()
        if self.FRONTEND_HOST:
            prod_host.add(str(self.FRONTEND_HOST).rstrip("/"))

        # Merge and return as a stable list
        merged = list(sorted(dev_origins | extras | prod_host))
        return merged

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: EmailStr | None = None

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str
    
    # PSI cache and circuit breaker settings
    PSI_CACHE_TTL_SECONDS: int = 43200  # 12 hours
    SCAN_MAX_CONCURRENCY: int = 3
    SCAN_JOB_TTL_SECONDS: int = 120
    
    # CrewAI/LLM settings
    CREW_AI_ENABLED: bool = False
    LLM_TIMEOUT_SECONDS: int = 15

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


import logging
import os

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)
_logger.info(f"Loading settings from env. POSTGRES_USER env var = {os.getenv('POSTGRES_USER')}")
settings = Settings()  # type: ignore
_logger.info(f"Settings loaded. POSTGRES_USER = {settings.POSTGRES_USER}")
