"""Verified SQLite backup artifact and restore operations."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tempfile
import zipfile


def backup_manifest_path(backup_path: str | Path) -> Path:
    return Path(f"{backup_path}.manifest.json")


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_backup_manifest(backup_path: str | Path, application_version: str) -> Path:
    artifact_path = Path(backup_path)
    payload = {
        "schemaVersion": 1,
        "artifact": artifact_path.name,
        "sha256": file_sha256(artifact_path),
        "sizeBytes": artifact_path.stat().st_size,
        "createdAt": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "applicationVersion": application_version,
    }
    manifest_path = backup_manifest_path(artifact_path)
    temporary_path = manifest_path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.chmod(temporary_path, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(temporary_path, manifest_path)
    return manifest_path


def verify_backup_manifest(backup_path: str | Path) -> bool:
    artifact_path = Path(backup_path)
    manifest_path = backup_manifest_path(artifact_path)
    if not manifest_path.exists():
        return False
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("Backup-Manifest ist ungültig.") from error
    if payload.get("artifact") != artifact_path.name:
        raise ValueError("Backup-Manifest passt nicht zum Artefakt.")
    if payload.get("sha256") != file_sha256(artifact_path):
        raise ValueError("Backup-Prüfsumme stimmt nicht.")
    return True


def _copy_restore_source(source, destination: Path, maximum_bytes: int) -> None:
    copied = 0
    with source, destination.open("wb") as output:
        while chunk := source.read(1024 * 1024):
            copied += len(chunk)
            if copied > maximum_bytes:
                raise ValueError("Backup überschreitet die konfigurierte Restore-Größe.")
            output.write(chunk)


def validate_backup_archive(archive: zipfile.ZipFile, maximum_bytes: int) -> list[zipfile.ZipInfo]:
    database_members = []
    total_uncompressed = 0
    for info in archive.infolist():
        member_path = PurePosixPath(info.filename)
        if (
            not info.filename
            or "\x00" in info.filename
            or "\\" in info.filename
            or member_path.is_absolute()
            or any(part in {"", ".", ".."} for part in member_path.parts)
        ):
            raise ValueError("Backup-Archiv enthält einen unsicheren Pfad.")
        unix_mode = info.external_attr >> 16
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise ValueError("Backup-Archiv enthält einen symbolischen Link.")
        if info.is_dir():
            continue
        total_uncompressed += max(0, info.file_size)
        if total_uncompressed > maximum_bytes:
            raise ValueError("Entpacktes Backup überschreitet die konfigurierte Restore-Größe.")
        if member_path.suffix.lower() == ".db":
            database_members.append(info)
    return database_members


def validate_sqlite_backup(database_path: str | Path) -> None:
    path = Path(database_path)
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
        connection.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
        connection.close()
    except sqlite3.Error as error:
        raise ValueError("Backup ist keine lesbare SQLite-Datenbank.") from error
    if result.lower() != "ok":
        raise ValueError("SQLite-Integritätsprüfung des Backups ist fehlgeschlagen.")


def materialize_sqlite_backup(backup_path, staging_directory, encryption_provider, maximum_bytes):
    artifact_path = Path(backup_path).resolve(strict=True)
    verify_backup_manifest(artifact_path)
    staging_path = Path(staging_directory)
    staging_path.mkdir(parents=True, exist_ok=True)
    raw_path = artifact_path
    temporary_paths = []
    try:
        if artifact_path.suffix == ".enc":
            cipher = encryption_provider()
            if not cipher:
                raise ValueError("BACKUP_ENCRYPTION_KEY fehlt oder ist ungültig.")
            encrypted_data = artifact_path.read_bytes()
            if len(encrypted_data) > maximum_bytes:
                raise ValueError("Verschlüsseltes Backup überschreitet die konfigurierte Restore-Größe.")
            try:
                decrypted_data = cipher.decrypt(encrypted_data)
            except Exception as error:
                raise ValueError("Backup kann mit dem konfigurierten Schlüssel nicht entschlüsselt werden.") from error
            if len(decrypted_data) > maximum_bytes:
                raise ValueError("Entschlüsseltes Backup überschreitet die konfigurierte Restore-Größe.")
            raw_path = staging_path / f"decrypted-backup{Path(artifact_path.stem).suffix}"
            raw_path.write_bytes(decrypted_data)
            os.chmod(raw_path, stat.S_IRUSR | stat.S_IWUSR)
            temporary_paths.append(raw_path)

        restore_source = staging_path / "restore-source.db"
        if raw_path.suffix == ".zip" or artifact_path.name.endswith(".zip.enc"):
            with zipfile.ZipFile(raw_path) as archive:
                database_members = validate_backup_archive(archive, maximum_bytes)
                if len(database_members) != 1:
                    raise ValueError("Backup-Archiv muss genau eine SQLite-Datenbank enthalten.")
                with archive.open(database_members[0]) as source:
                    _copy_restore_source(source, restore_source, maximum_bytes)
        elif raw_path.suffix == ".db":
            if raw_path.stat().st_size > maximum_bytes:
                raise ValueError("Backup überschreitet die konfigurierte Restore-Größe.")
            shutil.copyfile(raw_path, restore_source)
        else:
            raise ValueError("Nur SQLite-Backupdateien (.db, .zip oder .enc) können wiederhergestellt werden.")
        validate_sqlite_backup(restore_source)
        return restore_source
    except Exception:
        for path in temporary_paths:
            path.unlink(missing_ok=True)
        raise


def restore_sqlite_backup(backup_path, database_path, encryption_provider, maximum_bytes):
    target_path = Path(database_path).resolve()
    artifact_path = Path(backup_path).resolve(strict=True)
    if artifact_path == target_path:
        raise ValueError("Backup und Zieldatenbank dürfen nicht identisch sein.")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target_path.parent, prefix=".restore-") as directory:
        restore_source = materialize_sqlite_backup(
            artifact_path,
            directory,
            encryption_provider,
            maximum_bytes,
        )
        restored_path = Path(directory) / "restored.db"
        with sqlite3.connect(f"file:{restore_source}?mode=ro", uri=True) as source:
            with sqlite3.connect(restored_path) as destination:
                source.backup(destination)
        validate_sqlite_backup(restored_path)
        rollback_path = None
        if target_path.exists():
            rollback_path = target_path.with_name(
                f"{target_path.stem}.pre-restore-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{target_path.suffix}"
            )
            with sqlite3.connect(f"file:{target_path}?mode=ro", uri=True) as source:
                with sqlite3.connect(rollback_path) as destination:
                    source.backup(destination)
        os.replace(restored_path, target_path)
    return {"database": str(target_path), "rollback": str(rollback_path) if rollback_path else None}
