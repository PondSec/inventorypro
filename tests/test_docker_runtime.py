from pathlib import Path


def test_compose_uses_persistent_secret_generation_without_known_fallback():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "APP_SECRET_KEY: ${APP_SECRET_KEY:-}" in compose
    assert "inventorypro-compose-change-me" not in compose
    assert "INVENTORY_DATABASE_PATH: /data/inventory.db" in compose
    assert "INVENTORY_UPLOADS_DIR: /data/uploads" in compose
    assert "INVENTORY_INSTANCE_PATH: /data/instance" in compose
    assert "inventorypro-data:/data" in compose
