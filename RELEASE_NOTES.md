# Inventory Pro v0.1.3

Aktueller Release-Stand aus dem bereinigten Live-Source vom Serverstand 28.06.2026.

## Docker

Das Container-Image ist nach dem Release verfuegbar unter:

```bash
docker pull ghcr.io/pondsec/inventorypro:v0.1.3
docker pull ghcr.io/pondsec/inventorypro:latest
```

Installation per Compose:

```bash
cp packaging/docker/env.example .env
docker compose -f docker-compose.ghcr.yml up -d
```

## Windows

Der Release enthaelt `InventoryPro-v0.1.3-windows-x64.exe`. Die EXE startet Inventory Pro lokal und speichert Daten unter `%APPDATA%\InventoryPro`, sofern `INVENTORY_PRO_DATA_DIR` nicht gesetzt ist.

## Sicherheit

Das Docker-Image und die Release-Artefakte enthalten keine produktive `.env`, keine Datenbank, keine Uploads und keine Server-Zugangsdaten.
