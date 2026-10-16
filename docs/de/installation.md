# Installation und Betrieb

[English](../en/installation.md) · [Dokumentation](../INDEX.md)

## Voraussetzungen und Start

Docker Engine mit Compose oder ein gestartetes Docker Desktop sowie Git werden benötigt. Im [README](../../README.md#deutsch) steht der vollständige Schnellstart. Die Anwendung wird aus dem Quellcode gebaut; Python muss auf dem Host dafür nicht installiert sein.

Optional führt `python3 scripts/setup.py --start` durch die lokale Einrichtung. Der Helfer prüft Docker, Compose und den Port, erzeugt private persistente Secrets und überschreibt keine bestehende `.env`. Linux/macOS unterstützen `sh scripts/setup.sh --start`, Windows `./scripts/setup.ps1 --start`. Ein anderer Port wird mit `--port 5050` gewählt. Windows-Dateirechte müssen separat zum Benutzerkonto passen.

Compose bindet Port 5000 standardmäßig an `127.0.0.1`. Für Netzbetrieb einen HTTPS-Reverseproxy und `INVENTORY_BIND_ADDRESS` konfigurieren. Erlaubte Origins müssen zu den verwendeten URLs passen. Keine Standardzugänge oder Beispielschlüssel übernehmen. Ein fehlender Anwendungsschlüssel wird sicher im Instanzverzeichnis erzeugt.

## Datenhaltung und Backup

Das Volume `inventorypro-data` enthält `/data/inventory.db`, `/data/uploads`, `/data/instance` und konfigurierte Backups unter `/data/backups`. Der Compose-Projektname beeinflusst den tatsächlichen Volumenamen; Projektname und Mounts müssen bei Updates gleich bleiben. Eine private `.env` außerhalb des Repositories zusätzlich sichern.

1. Unter **Einstellungen → Server → Sicherung** eine Sicherung anlegen und das Ergebnis prüfen.
2. Datenbank, Uploads und Instanzschlüssel extern sichern. Eine reine Datenbanksicherung enthält keine Bilddateien.
3. Eine laufende SQLite-Datenbank über die Backupfunktion sichern. Für eine vollständige Volumenkopie die Anwendung anhalten.
4. Das Backup in einer getrennten Instanz wiederherstellen und Anmeldung, Datensätze sowie Anhänge prüfen.
5. Erst anschließend einen notwendigen produktiven Restore planen. Datenbank und Schlüssel müssen zusammenpassen.

Portable Inventarexporte ersetzen keine Instanzsicherung: Sie enthalten keine Konten, Tickets oder Secrets. Backups im selben Volume schützen nicht gegen den Verlust dieses Volumes. Niemals `docker compose down --volumes` zum Aktualisieren verwenden.

## Diagnose

```sh
docker compose ps
docker compose logs --tail 100 app
docker compose exec app python -c "import sqlite3; print(sqlite3.connect('/data/inventory.db').execute('PRAGMA integrity_check').fetchone()[0])"
```

Bei belegtem Port einen freien `INVENTORY_PORT` in `.env` wählen. Erstzugangsdaten liegen geschützt unter `/data/instance/initial_admin_credentials.txt`, nicht in den Logs. Zugangsdaten, Datenbanken und Schlüssel nicht in öffentliche Fehlerberichte aufnehmen.
