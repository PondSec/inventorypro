#!/usr/bin/env python3
"""Fail-closed update sidecar for Inventory Pro Docker installations.

The updater intentionally runs outside the application container. It only accepts a
signed release manifest, pulls immutable image digests, creates a local SQLite
backup, waits for a health check and restores the previous image when the new
container does not become healthy. It never sends application or inventory data to
the release service.
"""

from __future__ import annotations

import base64
import fcntl
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


LOGGER = logging.getLogger("inventorypro.updater")
MANIFEST_MAX_BYTES = 256 * 1024
DEFAULT_MANIFEST_URL = (
    "https://github.com/PondSec/inventorypro/releases/latest/download/update-manifest.json"
)
SEMVER_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?$")
SHA256_IMAGE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$")


class UpdateError(RuntimeError):
    """Expected update failure that must leave the active installation untouched."""


def env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser().resolve()


POLICY_PATH = env_path("INVENTORY_UPDATE_POLICY_PATH", "/data/instance/update_policy.json")
STATE_PATH = env_path("INVENTORY_UPDATE_STATE_PATH", "/data/instance/update_state.json")
LOCK_PATH = env_path("INVENTORY_UPDATE_LOCK_PATH", "/data/instance/update.lock")
DATA_PATH = env_path("INVENTORY_UPDATE_DATA_PATH", "/data")
COMPOSE_FILE = env_path("INVENTORY_UPDATE_COMPOSE_FILE", "/workspace/docker-compose.yml")
COMPOSE_PROJECT_DIR = env_path("INVENTORY_UPDATE_COMPOSE_PROJECT_DIR", "/workspace")
APP_SERVICE = os.environ.get("INVENTORY_UPDATE_APP_SERVICE", "app")
HEALTH_URL = os.environ.get("INVENTORY_UPDATE_HEALTH_URL", "http://app:5000/login")
MANIFEST_URL = os.environ.get("INVENTORY_UPDATE_MANIFEST_URL", DEFAULT_MANIFEST_URL)
ALLOWED_IMAGE_REPOSITORY = os.environ.get(
    "INVENTORY_UPDATE_ALLOWED_IMAGE_REPOSITORY", "ghcr.io/pondsec/inventorypro"
).strip().lower()
PUBLIC_KEY_FILE = os.environ.get("INVENTORY_UPDATE_PUBLIC_KEY_FILE", "/app/release-public-key.pem")
PUBLIC_KEY_VALUE = os.environ.get("INVENTORY_UPDATE_PUBLIC_KEY", "")
HEALTH_TIMEOUT_SECONDS = int(os.environ.get("INVENTORY_UPDATE_HEALTH_TIMEOUT_SECONDS", "180"))
HEALTH_POLL_SECONDS = int(os.environ.get("INVENTORY_UPDATE_HEALTH_POLL_SECONDS", "5"))
COMMAND_TIMEOUT_SECONDS = int(os.environ.get("INVENTORY_UPDATE_COMMAND_TIMEOUT_SECONDS", "300"))


def configure_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("INVENTORY_UPDATE_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def load_json(path: Path, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback or {})
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise UpdateError(f"Ungültige lokale Update-Datei {path.name}: {error}") from error
    if not isinstance(value, dict):
        raise UpdateError(f"Ungültige lokale Update-Datei {path.name}: Objekt erwartet.")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def normalize_policy(raw_policy: dict[str, Any]) -> dict[str, Any]:
    if raw_policy.get("schemaVersion") != 1:
        raise UpdateError("Unbekannte Update-Policy-Version.")
    channel = str(raw_policy.get("channel") or "").lower()
    if channel != "stable":
        raise UpdateError("Nur der signierte Stable-Kanal ist zulässig.")
    try:
        interval = int(raw_policy.get("checkIntervalMinutes"))
    except (TypeError, ValueError) as error:
        raise UpdateError("Update-Prüfintervall ist ungültig.") from error
    if not 15 <= interval <= 1440:
        raise UpdateError("Update-Prüfintervall außerhalb des zulässigen Bereichs.")
    window = str(raw_policy.get("maintenanceWindow") or "")
    if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", window):
        raise UpdateError("Update-Wartungsfenster ist ungültig.")
    return {
        "enabled": bool(raw_policy.get("autoUpdateEnabled")),
        "channel": channel,
        "interval": interval,
        "maintenance_window": window,
    }


def is_due(policy: dict[str, Any], now: datetime | None = None) -> bool:
    """Allow exactly the configured polling interval after the local maintenance time."""
    current = now or datetime.now()
    hour, minute = (int(part) for part in policy["maintenance_window"].split(":"))
    window_start = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    elapsed_seconds = (current - window_start).total_seconds()
    return 0 <= elapsed_seconds < policy["interval"] * 60


class SafeHttpsRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts: set[str]):
        super().__init__()
        self.allowed_hosts = allowed_hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in self.allowed_hosts:
            raise UpdateError("Unsicherer Redirect beim Laden des Release-Manifests abgelehnt.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_manifest(url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise UpdateError("Manifest-URL muss HTTPS verwenden.")
    allowed_hosts = {
        host.strip().lower()
        for host in os.environ.get(
            "INVENTORY_UPDATE_ALLOWED_MANIFEST_HOSTS",
            "github.com,objects.githubusercontent.com,release-assets.githubusercontent.com",
        ).split(",")
        if host.strip()
    }
    if parsed.hostname.lower() not in allowed_hosts:
        raise UpdateError("Manifest-Host ist nicht freigegeben.")
    opener = urllib.request.build_opener(SafeHttpsRedirect(allowed_hosts))
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "InventoryPro-Updater/1"},
        method="GET",
    )
    try:
        with opener.open(request, timeout=20) as response:
            if response.status != 200:
                raise UpdateError(f"Manifest-Abruf lieferte HTTP {response.status}.")
            payload = response.read(MANIFEST_MAX_BYTES + 1)
    except urllib.error.URLError as error:
        raise UpdateError(f"Manifest konnte nicht geladen werden: {error.reason}") from error
    if len(payload) > MANIFEST_MAX_BYTES:
        raise UpdateError("Release-Manifest überschreitet die zulässige Größe.")
    try:
        manifest = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpdateError("Release-Manifest ist kein gültiges JSON.") from error
    if not isinstance(manifest, dict):
        raise UpdateError("Release-Manifest muss ein Objekt sein.")
    return manifest


def load_public_key() -> Ed25519PublicKey:
    encoded = PUBLIC_KEY_VALUE.strip()
    if encoded:
        try:
            data = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise UpdateError("Update-Public-Key ist nicht gültig Base64-kodiert.") from error
    else:
        key_path = Path(PUBLIC_KEY_FILE)
        if not key_path.exists():
            raise UpdateError("Update-Public-Key fehlt. Der Updater bleibt deaktiviert.")
        data = key_path.read_bytes()
    try:
        public_key = serialization.load_pem_public_key(data)
    except ValueError as error:
        raise UpdateError("Update-Public-Key ist ungültig.") from error
    if not isinstance(public_key, Ed25519PublicKey):
        raise UpdateError("Update-Public-Key muss ein Ed25519-Schlüssel sein.")
    return public_key


def canonical_manifest(manifest: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in manifest.items() if key != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    required_keys = {"schemaVersion", "version", "image", "signatureAlgorithm", "signature"}
    missing = required_keys.difference(manifest)
    if missing:
        raise UpdateError(f"Release-Manifest unvollständig: {', '.join(sorted(missing))}.")
    if manifest["schemaVersion"] != 1:
        raise UpdateError("Unbekannte Release-Manifest-Version.")
    version = str(manifest["version"])
    if not SEMVER_PATTERN.match(version):
        raise UpdateError("Release-Version ist nicht semantisch versioniert.")
    image = str(manifest["image"]).lower()
    if not SHA256_IMAGE_PATTERN.match(image) or not image.startswith(f"{ALLOWED_IMAGE_REPOSITORY}@sha256:"):
        raise UpdateError("Release-Image ist nicht der freigegebene, unveränderliche Image-Digest.")
    if manifest["signatureAlgorithm"] != "ed25519":
        raise UpdateError("Nicht unterstützter Signaturalgorithmus.")
    try:
        signature = base64.b64decode(str(manifest["signature"]), validate=True)
    except ValueError as error:
        raise UpdateError("Release-Signatur ist nicht gültig Base64-kodiert.") from error
    try:
        load_public_key().verify(signature, canonical_manifest(manifest))
    except Exception as error:  # cryptography does not expose a more specific stable exception here
        raise UpdateError("Release-Signatur konnte nicht verifiziert werden.") from error
    return {"version": version.lstrip("v"), "image": image}


def version_tuple(version: str) -> tuple[int, int, int]:
    match = SEMVER_PATTERN.match(version)
    if not match:
        raise UpdateError("Versionsvergleich für eine ungültige Version verweigert.")
    return tuple(int(part) for part in match.groups())


def command(args: list[str], environment: dict[str, str] | None = None) -> str:
    try:
        result = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            env=environment,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        stderr = getattr(error, "stderr", "") or ""
        raise UpdateError(f"Container-Operation fehlgeschlagen: {stderr.strip() or error}") from error
    return result.stdout.strip()


def compose_args(*args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "--project-directory",
        str(COMPOSE_PROJECT_DIR),
        "--file",
        str(COMPOSE_FILE),
        *args,
    ]


def active_container_id() -> str:
    container_id = command(compose_args("ps", "--quiet", APP_SERVICE)).splitlines()
    if not container_id or not container_id[0]:
        raise UpdateError("Aktiver Inventory-Pro-Container wurde nicht gefunden.")
    return container_id[0].strip()


def active_image_reference() -> str:
    container_id = active_container_id()
    image_id = command(["docker", "inspect", "--format", "{{.Image}}", container_id])
    repo_digests = command(["docker", "image", "inspect", "--format", "{{join .RepoDigests \"\\n\"}}", image_id])
    for digest in repo_digests.splitlines():
        normalized = digest.strip().lower()
        if normalized.startswith(f"{ALLOWED_IMAGE_REPOSITORY}@sha256:"):
            return normalized
    raise UpdateError("Aktives Image hat keinen freigegebenen, wiederherstellbaren Digest.")


def backup_database(target_version: str) -> Path:
    database_path = DATA_PATH / "inventory.db"
    if not database_path.exists():
        raise UpdateError("Produktivdatenbank für Update-Backup nicht gefunden.")
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup_directory = DATA_PATH / "backups" / "updates" / f"{timestamp}-{target_version}"
    backup_directory.mkdir(parents=True, exist_ok=False)
    os.chmod(backup_directory, 0o700)
    backup_database_path = backup_directory / "inventory.db"
    source = None
    destination = None
    try:
        source = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True, timeout=30)
        destination = sqlite3.connect(backup_database_path, timeout=30)
        source.backup(destination)
        destination.commit()
        integrity = destination.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise UpdateError("Datenbank-Backup hat die Integritätsprüfung nicht bestanden.")
    except sqlite3.Error as error:
        raise UpdateError(f"Datenbank-Backup fehlgeschlagen: {error}") from error
    finally:
        if destination is not None:
            destination.close()
        if source is not None:
            source.close()
    metadata = {
        "createdAt": timestamp,
        "targetVersion": target_version,
        "database": backup_database_path.name,
        "integrityCheck": "ok",
    }
    atomic_write_json(backup_directory / "metadata.json", metadata)
    return backup_directory


def wait_for_health() -> bool:
    deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
    request = urllib.request.Request(HEALTH_URL, method="GET")
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                if 200 <= response.status < 400:
                    return True
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(max(1, HEALTH_POLL_SECONDS))
    return False


def update_environment(image: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment["INVENTORY_IMAGE"] = image
    return environment


def deploy_image(image: str) -> None:
    environment = update_environment(image)
    command(compose_args("pull", APP_SERVICE), environment)
    command(compose_args("up", "--detach", "--no-deps", "--no-build", APP_SERVICE), environment)


def write_state(state: dict[str, Any], **changes: Any) -> None:
    state.update(changes)
    state["updatedAt"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    atomic_write_json(STATE_PATH, state)


def perform_update(policy: dict[str, Any]) -> str:
    state = load_json(STATE_PATH, {"schemaVersion": 1})
    manifest = validate_manifest(fetch_manifest(MANIFEST_URL))
    target_version = manifest["version"]
    current_version = str(state.get("currentVersion") or "")
    if current_version and version_tuple(target_version) <= version_tuple(current_version):
        write_state(state, lastCheckStatus="up_to_date", lastCheckedVersion=target_version)
        return "up_to_date"

    current_image = active_image_reference()
    backup_directory = backup_database(target_version)
    write_state(
        state,
        lastCheckStatus="installing",
        pendingVersion=target_version,
        previousImage=current_image,
        backupPath=str(backup_directory),
    )
    try:
        deploy_image(manifest["image"])
        if not wait_for_health():
            raise UpdateError("Neue Version hat den Healthcheck nicht bestanden.")
    except UpdateError as error:
        LOGGER.error("Update auf %s fehlgeschlagen, starte Rollback: %s", target_version, error)
        try:
            deploy_image(current_image)
            if not wait_for_health():
                raise UpdateError("Rollback-Container hat den Healthcheck nicht bestanden.")
        except UpdateError as rollback_error:
            write_state(
                state,
                lastCheckStatus="rollback_failed",
                lastError=str(rollback_error),
                failedVersion=target_version,
            )
            raise UpdateError("Update und Rollback sind fehlgeschlagen. Manuelle Wiederherstellung erforderlich.") from rollback_error
        write_state(
            state,
            lastCheckStatus="rolled_back",
            lastError=str(error),
            failedVersion=target_version,
            pendingVersion=None,
        )
        return "rolled_back"

    write_state(
        state,
        currentVersion=target_version,
        currentImage=manifest["image"],
        previousImage=current_image,
        pendingVersion=None,
        lastCheckStatus="updated",
        lastError=None,
    )
    return "updated"


def run_once(now: datetime | None = None) -> str:
    policy = normalize_policy(load_json(POLICY_PATH))
    if not policy["enabled"]:
        return "disabled"
    if not is_due(policy, now):
        return "outside_maintenance_window"
    return perform_update(policy)


def main() -> int:
    configure_logging()
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            LOGGER.info("Ein weiterer Updater-Durchlauf ist bereits aktiv.")
            return 0
        while True:
            try:
                result = run_once()
                LOGGER.info("Updater-Ergebnis: %s", result)
                policy = normalize_policy(load_json(POLICY_PATH))
                sleep_seconds = policy["interval"] * 60
            except UpdateError as error:
                LOGGER.error("Updater abgebrochen: %s", error)
                sleep_seconds = 15 * 60
            except Exception:
                LOGGER.exception("Unerwarteter Updater-Fehler")
                sleep_seconds = 15 * 60
            time.sleep(sleep_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
