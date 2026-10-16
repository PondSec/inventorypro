# Installation and operation

[Deutsch](../de/installation.md) · [Documentation](../INDEX.md)

## Requirements and startup

Docker Engine with Compose, or running Docker Desktop, and Git are required. The [README](../../README.md#english) provides the complete quick start. The application builds from source; the host does not need Python for this process.

The optional `python3 scripts/setup.py --start` helper checks Docker, Compose and port availability, creates private persistent secrets and never overwrites an existing `.env`. Linux/macOS also support `sh scripts/setup.sh --start`; Windows supports `./scripts/setup.ps1 --start`. Choose another port with `--port 5050`. On Windows, configure appropriate account and directory permissions separately.

Compose binds port 5000 to `127.0.0.1` by default. Configure an HTTPS reverse proxy and `INVENTORY_BIND_ADDRESS` for network access. Allowed origins must match the URLs in use. Do not use example passwords or keys. A missing application key is generated securely in the persistent instance directory.

## Persistence and backup

The `inventorypro-data` volume holds `/data/inventory.db`, `/data/uploads`, `/data/instance` and configured backups under `/data/backups`. The Compose project name affects the actual volume name; retain the project name and mounts during updates. Back up the private `.env` separately, outside the repository.

1. Create a backup under **Settings → Server → Backup** and check its result.
2. Keep an external backup of the database, uploads and instance keys. Database-only backups contain no image files.
3. Use the backup function for a running SQLite database. Stop the application before copying the complete volume.
4. Restore into a separate instance and verify login, records and attachments.
5. Only then plan any required production restore. Database and encryption keys must match.

Portable inventory exports do not replace an instance backup: they exclude accounts, tickets and secrets. Backups in the same volume do not protect against losing that volume. Never use `docker compose down --volumes` to update.

## Diagnostics

```sh
docker compose ps
docker compose logs --tail 100 app
docker compose exec app python -c "import sqlite3; print(sqlite3.connect('/data/inventory.db').execute('PRAGMA integrity_check').fetchone()[0])"
```

For port conflicts, choose a free `INVENTORY_PORT` in `.env`. Initial credentials are stored privately in `/data/instance/initial_admin_credentials.txt`, not in logs. Exclude credentials, databases and keys from public issue reports.
