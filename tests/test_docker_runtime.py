from pathlib import Path


def test_compose_provides_persistent_application_secret_fallback():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "APP_SECRET_KEY: ${APP_SECRET_KEY:-" in compose
    assert "APP_SECRET_KEY: ${APP_SECRET_KEY:-}" not in compose
    assert "INVENTORY_DATABASE_PATH: /data/inventory.db" in compose
    assert "INVENTORY_UPLOADS_DIR: /data/uploads" in compose
    assert "INVENTORY_INSTANCE_PATH: /data/instance" in compose
    assert "inventorypro-data:/data" in compose
