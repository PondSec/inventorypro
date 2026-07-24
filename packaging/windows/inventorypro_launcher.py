from __future__ import annotations

import os
import secrets
import sys
import threading
import webbrowser
from pathlib import Path

from cryptography.fernet import Fernet


APP_NAME = "InventoryPro"


def app_data_dir() -> Path:
    base = os.environ.get("INVENTORY_PRO_DATA_DIR")
    if base:
        return Path(base).expanduser()
    root = os.environ.get("APPDATA") or str(Path.home())
    return Path(root) / APP_NAME


def read_or_create(path: Path, factory) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    value = factory()
    path.write_text(value + "\n", encoding="utf-8")
    return value


def configure_environment() -> Path:
    data_dir = app_data_dir()
    instance_dir = data_dir / "instance"
    uploads_dir = data_dir / "uploads"
    secrets_dir = data_dir / "secrets"

    data_dir.mkdir(parents=True, exist_ok=True)
    instance_dir.mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    secrets_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("INVENTORY_HOST", "127.0.0.1")
    os.environ.setdefault("INVENTORY_PORT", "5000")
    os.environ.setdefault("INVENTORY_DATABASE_PATH", str(data_dir / "inventory.db"))
    os.environ.setdefault("INVENTORY_UPLOADS_DIR", str(uploads_dir))
    os.environ.setdefault("INVENTORY_INSTANCE_PATH", str(instance_dir))
    os.environ.setdefault(
        "APP_SECRET_KEY",
        read_or_create(secrets_dir / "app_secret_key.txt", lambda: secrets.token_hex(32)),
    )
    os.environ.setdefault(
        "BACKUP_ENCRYPTION_KEY",
        read_or_create(secrets_dir / "backup_fernet_key.txt", lambda: Fernet.generate_key().decode("ascii")),
    )
    os.environ.setdefault(
        "INVENTORY_LINKS_ENCRYPTION_KEY",
        read_or_create(secrets_dir / "inventory_links_fernet_key.txt", lambda: Fernet.generate_key().decode("ascii")),
    )
    os.environ.setdefault("INVENTORY_LINKS_ALLOW_PLAINTEXT_SECRETS", "0")
    return data_dir


def bundled_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def start_browser(host: str, port: int) -> None:
    browse_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{browse_host}:{port}"
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    print(f"Inventory Pro startet: {url}")


def main() -> None:
    data_dir = configure_environment()
    root = bundled_root()
    os.chdir(root)

    import app as inventory_app

    inventory_app.app.template_folder = str(root / "templates")
    inventory_app.app.static_folder = str(root / "static")

    inventory_app.init_db()
    with inventory_app.app.app_context():
        settings_row = inventory_app.get_server_settings(inventory_app.get_db())
        settings, _ = inventory_app.serialize_server_settings(settings_row)
        runtime = inventory_app.load_runtime_settings()
        if not runtime or runtime == inventory_app.DEFAULT_SERVER_SETTINGS["server"]:
            runtime = settings["server"]
            inventory_app.store_runtime_settings(runtime)
        inventory_app.RUNTIME_SETTINGS_CACHE = runtime
        inventory_app.schedule_backup_jobs(settings)
        inventory_app.schedule_health_jobs()

    host = str(runtime["host"])
    port = int(runtime["port"])
    print(f"Datenverzeichnis: {data_dir}")
    start_browser(host, port)
    inventory_app.app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
