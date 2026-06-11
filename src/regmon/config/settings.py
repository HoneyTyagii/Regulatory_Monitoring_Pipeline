"""Typed application settings loaded from environment variables and YAML.

Configuration precedence (highest first):

1. Explicit overrides passed to :func:`load_settings`.
2. Process environment variables (and values from a loaded ``.env`` file).
3. A YAML configuration file (if provided).
4. Field defaults defined on the models below.

Sensitive values (API keys, passwords, webhook URLs) are wrapped in
:class:`pydantic.SecretStr` so they are never accidentally printed in logs or
tracebacks. Use :func:`regmon.config.secrets.reveal` to access the raw value
at the point of use.
"""

from __future__ import annotations

import os
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class Environment(str, Enum):
    """Deployment environment the process is running in."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Provider(str, Enum):
    """Pluggable LLM / embedding provider backends."""

    MOCK = "mock"
    OPENAI = "openai"


LogFormat = Literal["console", "json"]


class _ConfigBase(BaseModel):
    """Shared config for settings sub-models."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        frozen=True,
    )


class AppSettings(_ConfigBase):
    """General application behavior."""

    env: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_format: LogFormat = "console"
    dry_run: bool = True

    @field_validator("log_level")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class StorageSettings(_ConfigBase):
    """Database and vector store locations."""

    database_url: str = "sqlite:///./data/regmon.sqlite"
    vectorstore_path: Path = Path("./data/vectorstore")
    raw_storage_path: Path = Path("./data/raw")


class LLMSettings(_ConfigBase):
    """LLM and embedding provider configuration."""

    llm_provider: Provider = Provider.MOCK
    embedding_provider: Provider = Provider.MOCK
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"


class CrawlSettings(_ConfigBase):
    """Crawler politeness and timeout configuration."""

    user_agent: str = "regmon-bot/0.1 (+https://example.com/bot)"
    rate_limit_per_sec: float = Field(default=1.0, gt=0)
    timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=3, ge=0, le=10)
    backoff_factor: float = Field(default=0.5, ge=0)
    respect_robots: bool = True


class NotificationSettings(_ConfigBase):
    """Outbound notification channels (Slack + SMTP email)."""

    slack_webhook_url: SecretStr | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    notify_from: str = "regmon@example.com"
    notify_to: list[str] = Field(default_factory=lambda: ["compliance-team@example.com"])

    @field_validator("notify_to", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        """Accept a comma-separated string or a list of recipients."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class Settings(_ConfigBase):
    """Top-level, fully-typed application settings."""

    app: AppSettings = Field(default_factory=AppSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    crawl: CrawlSettings = Field(default_factory=CrawlSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)


# Mapping of ``section -> {field: ENV_VAR_NAME}``. Keeping this explicit (rather
# than deriving it) makes the env contract obvious and greppable.
_ENV_MAP: dict[str, dict[str, str]] = {
    "app": {
        "env": "REGMON_ENV",
        "log_level": "REGMON_LOG_LEVEL",
        "log_format": "REGMON_LOG_FORMAT",
        "dry_run": "REGMON_DRY_RUN",
    },
    "storage": {
        "database_url": "REGMON_DATABASE_URL",
        "vectorstore_path": "REGMON_VECTORSTORE_PATH",
        "raw_storage_path": "REGMON_RAW_STORAGE_PATH",
    },
    "llm": {
        "llm_provider": "REGMON_LLM_PROVIDER",
        "embedding_provider": "REGMON_EMBEDDING_PROVIDER",
        "openai_api_key": "OPENAI_API_KEY",
        "openai_model": "OPENAI_MODEL",
        "openai_embedding_model": "OPENAI_EMBEDDING_MODEL",
    },
    "crawl": {
        "user_agent": "REGMON_CRAWL_USER_AGENT",
        "rate_limit_per_sec": "REGMON_CRAWL_RATE_LIMIT_PER_SEC",
        "timeout_seconds": "REGMON_CRAWL_TIMEOUT_SECONDS",
        "max_retries": "REGMON_CRAWL_MAX_RETRIES",
        "backoff_factor": "REGMON_CRAWL_BACKOFF_FACTOR",
        "respect_robots": "REGMON_CRAWL_RESPECT_ROBOTS",
    },
    "notifications": {
        "slack_webhook_url": "REGMON_SLACK_WEBHOOK_URL",
        "smtp_host": "REGMON_SMTP_HOST",
        "smtp_port": "REGMON_SMTP_PORT",
        "smtp_username": "REGMON_SMTP_USERNAME",
        "smtp_password": "REGMON_SMTP_PASSWORD",
        "notify_from": "REGMON_NOTIFY_FROM",
        "notify_to": "REGMON_NOTIFY_TO",
    },
}


def _read_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML config file into a nested dict, or raise if malformed."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"config file not found: {file_path}")
    with file_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"config file must contain a mapping at top level: {file_path}")
    return data


def _read_environ(environ: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Project relevant environment variables into a nested settings dict.

    Empty string values are treated as *unset* so that placeholder entries in a
    ``.env`` file (e.g. ``OPENAI_API_KEY=``) do not override real defaults.
    """
    result: dict[str, dict[str, Any]] = {}
    for section, fields in _ENV_MAP.items():
        for field_name, env_var in fields.items():
            raw = environ.get(env_var)
            if raw is None or raw.strip() == "":
                continue
            result.setdefault(section, {})[field_name] = raw.strip()
    return result


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base``, returning a new dict."""
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def load_settings(
    *,
    env_file: str | Path | None = ".env",
    yaml_file: str | Path | None = None,
    environ: dict[str, str] | None = None,
    overrides: dict[str, Any] | None = None,
) -> Settings:
    """Build a :class:`Settings` instance from all configuration layers.

    Parameters
    ----------
    env_file:
        Path to a ``.env`` file to load into the environment before reading.
        Pass ``None`` to skip loading. Missing files are ignored.
    yaml_file:
        Optional YAML file providing base configuration values.
    environ:
        Environment mapping to read from. Defaults to ``os.environ``.
    overrides:
        Highest-precedence nested dict applied last (useful in tests).
    """
    if env_file is not None and Path(env_file).is_file():
        load_dotenv(env_file, override=False)

    source_environ = environ if environ is not None else dict(os.environ)

    layered: dict[str, Any] = {}
    if yaml_file is not None:
        layered = _deep_merge(layered, _read_yaml(yaml_file))
    layered = _deep_merge(layered, _read_environ(source_environ))
    if overrides:
        layered = _deep_merge(layered, overrides)

    return Settings(**layered)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` loaded from the default env.

    The result is memoized; call :func:`reload_settings` to rebuild it (e.g.
    after changing environment variables in tests).
    """
    return load_settings()


def reload_settings() -> Settings:
    """Clear the cached settings and load them again."""
    get_settings.cache_clear()
    return get_settings()


__all__ = [
    "AppSettings",
    "CrawlSettings",
    "Environment",
    "LLMSettings",
    "NotificationSettings",
    "Provider",
    "Settings",
    "StorageSettings",
    "get_settings",
    "load_settings",
    "reload_settings",
]
