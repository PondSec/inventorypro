"""Runtime configuration with explicit secure defaults."""

from __future__ import annotations

from dataclasses import dataclass
import os
import secrets


class ConfigurationError(RuntimeError):
    """Raised when a required runtime setting is missing or unsafe."""


@dataclass(frozen=True)
class ApplicationSecret:
    value: str
    environment: str
    generated_for_development: bool


def application_environment(environ: dict[str, str] | None = None) -> str:
    values = environ if environ is not None else os.environ
    value = (values.get("INVENTORY_ENV") or values.get("FLASK_ENV") or "development").strip().lower()
    if value not in {"development", "test", "production"}:
        raise ConfigurationError(
            "INVENTORY_ENV muss development, test oder production sein."
        )
    return value


def resolve_application_secret(environ: dict[str, str] | None = None) -> ApplicationSecret:
    values = environ if environ is not None else os.environ
    environment = application_environment(values)
    configured_key = (values.get("APP_SECRET_KEY") or "").strip()
    if configured_key:
        return ApplicationSecret(configured_key, environment, False)
    if environment == "production":
        raise ConfigurationError(
            "APP_SECRET_KEY fehlt. Im Produktionsmodus ist ein persistenter "
            "APP_SECRET_KEY zwingend erforderlich."
        )
    return ApplicationSecret(secrets.token_urlsafe(48), environment, True)
