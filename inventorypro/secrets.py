"""Versioned Fernet encryption for application-managed secrets."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from typing import Iterable

from cryptography.fernet import Fernet, InvalidToken


class SecretConfigurationError(ValueError):
    """Raised without exposing secret material when encryption is unavailable."""


class SecretDecryptionError(ValueError):
    """Raised without exposing secret material when no configured key can decrypt it."""


FERNET_PREFIX = "fernet:v1:"


def key_identifier(key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return digest[:16]


def _configured_keys(environ: dict[str, str]) -> list[str]:
    configured = (environ.get("INVENTORY_LINKS_ENCRYPTION_KEYS") or "").strip()
    if configured:
        return [value.strip() for value in configured.split(",") if value.strip()]
    primary = (environ.get("INVENTORY_LINKS_ENCRYPTION_KEY") or "").strip()
    return [primary] if primary else []


@dataclass(frozen=True)
class EncryptionKeyring:
    keys: tuple[tuple[str, Fernet], ...]

    @classmethod
    def from_environ(cls, environ: dict[str, str] | None = None) -> "EncryptionKeyring":
        values = environ if environ is not None else os.environ
        candidates = _configured_keys(values)
        if not candidates:
            raise SecretConfigurationError(
                "INVENTORY_LINKS_ENCRYPTION_KEY fehlt; Inventory-Link-Secrets werden nicht gespeichert."
            )
        keys: list[tuple[str, Fernet]] = []
        for candidate in candidates:
            try:
                keys.append((key_identifier(candidate), Fernet(candidate)))
            except (ValueError, TypeError) as error:
                raise SecretConfigurationError(
                    "INVENTORY_LINKS_ENCRYPTION_KEY ist ungültig; Inventory-Link-Secrets werden nicht gespeichert."
                ) from error
        return cls(tuple(keys))

    @property
    def primary_identifier(self) -> str:
        return self.keys[0][0]

    def encrypt(self, secret: str) -> str:
        token = self.keys[0][1].encrypt(secret.encode("utf-8")).decode("utf-8")
        return f"{FERNET_PREFIX}{self.primary_identifier}:{token}"

    def decrypt(self, encrypted: str) -> str:
        token = encrypted
        expected_identifier = None
        if encrypted.startswith(FERNET_PREFIX):
            parts = encrypted.split(":", 3)
            if len(parts) != 4:
                raise SecretDecryptionError("Inventory-Link-Secret ist ungültig verschlüsselt.")
            _, _, expected_identifier, token = parts
        candidates: Iterable[tuple[str, Fernet]] = self.keys
        if expected_identifier:
            candidates = tuple(item for item in self.keys if item[0] == expected_identifier) or self.keys
        for _, cipher in candidates:
            try:
                return cipher.decrypt(token.encode("utf-8")).decode("utf-8")
            except (InvalidToken, UnicodeDecodeError, ValueError, TypeError):
                continue
        raise SecretDecryptionError(
            "Inventory-Link-Secret kann mit den konfigurierten Verschlüsselungsschlüsseln nicht gelesen werden."
        )


def is_plaintext_secret(value: str | None) -> bool:
    if not value:
        return False
    return value.startswith("plain:")


def encrypt_secret(secret: str | None, environ: dict[str, str] | None = None) -> str | None:
    if secret is None:
        return None
    if secret == "":
        return ""
    return EncryptionKeyring.from_environ(environ).encrypt(secret)


def decrypt_secret(value: str | None, environ: dict[str, str] | None = None) -> str:
    if not value:
        return ""
    if is_plaintext_secret(value):
        raise SecretConfigurationError(
            "Ein unverschlüsseltes Inventory-Link-Secret muss vor der Nutzung migriert werden."
        )
    try:
        return EncryptionKeyring.from_environ(environ).decrypt(value)
    except SecretDecryptionError as error:
        if not value.startswith(FERNET_PREFIX):
            raise SecretConfigurationError(
                "Ein altes Inventory-Link-Secret muss mit dem bisherigen Schlüssel migriert werden."
            ) from error
        raise


def migrate_plaintext_secret(value: str, environ: dict[str, str] | None = None) -> str:
    if value.startswith("plain:"):
        value = value.removeprefix("plain:")
    return encrypt_secret(value, environ) or ""


def generate_fernet_key() -> str:
    return Fernet.generate_key().decode("utf-8")
