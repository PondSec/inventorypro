# Installation und Betrieb mit Docker Compose

## Schnellstart ohne Standardpasswort

Voraussetzung: Docker Engine mit Compose oder gestartetes Docker Desktop.

```sh
git clone --branch dev https://gitlab.pondsec.com/PondSec/inventorypro.git
cd inventorypro
docker compose up --detach --build --wait app
docker compose exec app cat /data/instance/initial_admin_credentials.txt
```

Öffnen: [http://localhost:5000](http://localhost:5000). Die zufälligen Erstzugangsdaten
sind nur für jemanden mit lokalem Dockerzugriff lesbar. Beim ersten Login muss das
Passwort geändert werden. Es gibt keine öffentlich nutzbare Setupregistrierung.
Die Zugangsdaten stehen nicht in den Containerlogs.

Der Port ist standardmäßig nur an 127.0.0.1 gebunden. Für Netzwerkbetrieb eine
bewusste Bind-Adresse und einen HTTPS-Reverseproxy konfigurieren. Vorhandene
Installationen behalten ihre bisherigen Ports und Mounts bei.

## Optionaler Einrichtungshelfer

Mit Python 3 (keine zusätzlichen Pythonpakete nötig):

```sh
python3 scripts/setup.py --start
# Anderer freier Port:
python3 scripts/setup.py --port 5050 --start
```

Windows PowerShell: `./scripts/setup.ps1 --start` (Python 3 über `py` oder `python`).
Linux/macOS: `sh scripts/setup.sh --start`.

Der Helfer prüft Docker/Compose und Portverfügbarkeit, erzeugt eine private `.env`
mit zufälligen persistenten Session-/Verschlüsselungsschlüsseln und startet den
App-Service. Vorhandene `.env` wird niemals überschrieben. Eine bestehende
Compose-Installation wird nicht durch den Einrichtungshelfer neu konfiguriert.
Windows benötigt geeignete Benutzerrechte für den Projektordner; POSIX-Dateimodi
ersetzen keine Windows-ACLs.

Auch ohne Helfer erzeugt die Produktionsanwendung ihren Session-Schlüssel sicher
unter `/data/instance/application-secret.key`, sofern APP_SECRET_KEY fehlt. Der
Schlüssel überlebt Containerneustarts. Ein bekannter alter Compose-Platzhalter
wird beim Update automatisch durch diesen persistenten Zufallswert ersetzt;
bestehende Sitzungen müssen sich dann einmal neu anmelden. Individuelle vorhandene
APP_SECRET_KEY-Werte und Verschlüsselungsschlüssel werden nicht verändert.

## Erste Schritte

1. Eigenes Passwort setzen und unter Kontosicherheit TOTP aktivieren.
2. Einen Standort anlegen und ein erstes Gerät erfassen.
3. Benutzer/Rollen nach Aufgaben vergeben.
4. In Einstellungen ein Backup ausführen und eine Wiederherstellung in einer
   separaten Testinstanz prüfen.

## Persistenz und Sicherung

Der Compose-Projektname bestimmt den Namen des Datenvolumes. Denselben Projektnamen
und dieselben Mounts bei jedem Update beibehalten. Das Datenvolume enthält:

- `/data/inventory.db`: SQLite-Datenbank
- `/data/uploads`: Anhänge
- `/data/instance`: Session-Schlüssel, Laufzeitkonfiguration und Updatepolicy
- `/data/backups`: konfigurierte Sicherungen

Die komplette Datenhaltung und die private `.env` getrennt vom Repository sichern.
SQLite während des Betriebs über die Backupfunktion sichern, nicht durch einfaches
Kopieren einer geöffneten Datenbank. Für eine vollständige Volumesicherung die
Anwendung anhalten und das gesamte Volume einschließlich Uploads und Instanzschlüsseln
mit der vorhandenen Infrastruktur sichern. Ein Backup im selben Volume ersetzt
keine externe Sicherung. Restore zuerst isoliert prüfen.

## Updates vorhandener Installationen

Keine Neuinstallation und keine Umstellung vorhandener Mounts vornehmen. Der alte
Updater erhält freigegebene Versionen weiterhin über den kompatiblen Releasefeed.
Neue Updater lesen das signierte Manifest bei GitLab. Einzelheiten und die
betrieblichen Veröffentlichungsanforderungen: [Updatekompatibilität](docs/enterprise/UPDATE-COMPATIBILITY.md).
Automatische Updates lassen sich in Einstellungen → Server ein- und ausschalten.
Der Sidecar muss bereits eingerichtet sein; ein Schalter allein installiert keinen
privilegierten Docker-Dienst.

Bei bewusst manueller Aktualisierung erst Backup erstellen, dann im bestehenden
Checkout `git pull --ff-only origin dev` und `docker compose up --detach --build --wait app`
verwenden. Bei lokalen Änderungen oder abweichenden Branches abbrechen und die
Historie klären. Kein Datenvolume löschen.

## Diagnose

```sh
docker compose ps
docker compose logs --tail 100 app
docker compose exec app python -c "import sqlite3; print(sqlite3.connect('/data/inventory.db').execute('PRAGMA integrity_check').fetchone()[0])"
```

Bei Portkonflikten die andere Anwendung nicht automatisch beenden. Einen anderen
INVENTORY_PORT in `.env` konfigurieren. Secrets nicht in Fehlermeldungen, Tickets
oder Screenshots weitergeben. Der Initialzugang liegt in der privaten Datei,
nicht in einer vermeintlichen Standardpasswortliste.

## Ausgeführte Entwicklungsprüfungen

2026-10-15: Docker 29.7.2/macOS ARM64, Image mit Python 3.12 gebaut; isolierte
Compose-Produktionsinstanz ohne konfigurierten Anwendungsschlüssel gestartet,
HTTP-Loginseite erfolgreich geladen, Neustart mit unverändertem persistenten
Schlüssel sowie Datenbankintegrität und private Erstzugangsdatei geprüft.
Testprojekt und dessen eigens erzeugtes Volume danach entfernt.
Linux-/Windows-Hosts und PowerShell wurden nicht ausgeführt.
