"""Runtime configuration with explicit secure defaults."""

from __future__ import annotations

from dataclasses import dataclass
import os
import secrets
from pathlib import Path
import stat
import tempfile


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


KNOWN_PLACEHOLDERS = {
    "inventorypro-compose-change-me-persistently-before-production",
    "change-this-long-random-secret", "change-me", "secret", "development-secret",
}


def persistent_instance_secret(instance_path: str) -> str:
    """Publish once atomically, with private permissions and no symlink following."""
    directory = Path(instance_path)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "application-secret.key"
    temporary = None
    try:
        if not target.exists():
            with tempfile.NamedTemporaryFile(mode="w", encoding="ascii", dir=directory,
                                             prefix=".application-secret-", delete=False) as handle:
                temporary = Path(handle.name)
                os.chmod(temporary, 0o600)
                handle.write(secrets.token_urlsafe(48))
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
        descriptor = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "r", encoding="ascii") as handle:
            metadata = os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode) or (os.name != "nt" and metadata.st_mode & 0o077):
                raise ConfigurationError("Persistenter Anwendungsschlüssel muss eine private reguläre Datei sein (0600).")
            value = handle.read(513).strip()
        if not 48 <= len(value) <= 512 or value in KNOWN_PLACEHOLDERS:
            raise ConfigurationError("Persistenter Anwendungsschlüssel ist ungültig.")
        return value
    except (OSError, UnicodeError) as error:
        raise ConfigurationError("Persistenter Anwendungsschlüssel kann nicht sicher geladen werden.") from error
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def resolve_application_secret(environ: dict[str, str] | None = None) -> ApplicationSecret:
    values = environ if environ is not None else os.environ
    environment = application_environment(values)
    configured_key = (values.get("APP_SECRET_KEY") or "").strip()
    if configured_key and configured_key not in KNOWN_PLACEHOLDERS:
        return ApplicationSecret(configured_key, environment, False)
    if environment == "production" and values.get("INVENTORY_INSTANCE_PATH"):
        return ApplicationSecret(persistent_instance_secret(values["INVENTORY_INSTANCE_PATH"]), environment, False)
    if environment == "production":
        raise ConfigurationError(
            "APP_SECRET_KEY fehlt. Im Produktionsmodus ist ein persistenter "
            "APP_SECRET_KEY zwingend erforderlich."
        )
    return ApplicationSecret(secrets.token_urlsafe(48), environment, True)
