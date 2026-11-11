"""Safe temporary storage and archive inspection for imports."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile
from typing import Any

from werkzeug.utils import secure_filename


DEFAULT_MAX_IMPORT_EXPANDED_BYTES = int(
    os.environ.get("INVENTORY_MAX_IMPORT_EXPANDED_BYTES", 200 * 1024 * 1024)
)


def save_import_file(file_storage: Any, *, content_length: int | None, max_import_bytes: int):
    """Store one uploaded import in a private temporary directory."""
    if not file_storage:
        return None, "Keine Datei hochgeladen."
    if content_length and content_length > max_import_bytes:
        return None, "Datei ist zu groß."
    filename = secure_filename(file_storage.filename or "")
    if not filename:
        return None, "Ungültiger Dateiname."
    temp_dir = Path(tempfile.mkdtemp(prefix="inventory_import_"))
    file_path = temp_dir / filename
    try:
        file_storage.save(file_path)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return file_path, None


def validate_import_file(file_path: Path) -> str | None:
    """Run the configured anti-malware command without shell interpolation."""
    antivirus_cmd = os.environ.get("INVENTORY_ANTIVIRUS_COMMAND")
    if not antivirus_cmd:
        return None
    result = subprocess.run(
        [antivirus_cmd, str(file_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return result.stderr.strip() or "Datei konnte nicht geprüft werden."
    return None


def validate_import_archive(archive: Any, *, max_expanded_bytes: int = DEFAULT_MAX_IMPORT_EXPANDED_BYTES):
    """Reject traversal, symlinks and decompression expansion in ZIP imports."""
    total_uncompressed = 0
    upload_members = []
    for info in archive.infolist():
        member_name = info.filename
        if not member_name or "\x00" in member_name or "\\" in member_name:
            raise ValueError("ZIP-Archiv enthält einen ungültigen Pfad.")
        member_path = PurePosixPath(member_name)
        if member_path.is_absolute() or any(part in {"", ".", ".."} for part in member_path.parts):
            raise ValueError("ZIP-Archiv enthält einen unsicheren Pfad.")
        unix_mode = info.external_attr >> 16
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise ValueError("Symbolische Links sind in Importarchiven nicht zulässig.")
        total_uncompressed += max(0, info.file_size)
        if total_uncompressed > max_expanded_bytes:
            raise ValueError("Entpackter Inhalt überschreitet die zulässige Größe.")
        if info.is_dir() or not member_path.parts or member_path.parts[0] != "uploads":
            continue
        relative_parts = member_path.parts[1:]
        if relative_parts:
            upload_members.append((info, Path(*relative_parts)))
    return upload_members
