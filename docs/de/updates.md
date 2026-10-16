# Updates und Veröffentlichung

[English](../en/updates.md) · [Dokumentation](../INDEX.md)

## Vorhandene Installationen

Ein laufender alter Updater liest weiterhin das signierte Manifest aus dem GitHub-Release und installiert das passende GHCR-Image. Neue Updater verwenden GitLab. Jeder Stable-Release muss beide kompatiblen Manifeste und identische getestete Images anbieten. Der ursprüngliche Signierschlüssel bleibt erforderlich. Ein App-Update ersetzt keinen bereits laufenden alten Sidecar; der Kompatibilitätsspiegel wird deshalb weitergeführt.

Automatische Updates können unter **Einstellungen → Server → Updates** deaktiviert werden. Ein deaktivierter Updater fragt keine Releases ab. Der Schalter installiert keinen fehlenden Sidecar. Neue Installationen aktivieren ihn optional mit `INVENTORY_UPDATER_ENABLED=1` in `.env` und `docker compose --profile updater up --detach --build --wait`. Der Updater benötigt Dockerzugriff und dieselbe Datenhaltung wie die Anwendung.

Eine bereits ausgefallene Anwendung kann ein laufender Updater ersetzen. Wurde der Updater wegen einer fehlgeschlagenen Health-Abhängigkeit nie gestartet, ist ein einmaliger lokaler Eingriff erforderlich. Eine automatische Reparatur ohne laufenden Prozess ist nicht möglich.

## Sicherheit und Rückfall

HTTPS-Hostfreigabe, Stable-Kanal, Ed25519-Signatur und Image-Digest werden geprüft. Der neue Updater hält die Anwendung vor Migrationen an, sichert die ruhende SQLite-Datenbank und stellt bei fehlgeschlagenem Healthcheck die vorherige Datenbank und das vorherige Image wieder her. Uploads und Instanzschlüssel im bestehenden Volume behalten.

Für manuelle Updates zuerst sichern. In einem unveränderten Checkout `git pull --ff-only` und `docker compose up --detach --build --wait app` verwenden. Bei abweichender Historie oder lokalen Änderungen abbrechen und den Stand klären; kein erzwungenes Überschreiben. Kein Datenvolume löschen.

## Releaseverfahren

1. Änderungen auf `dev` prüfen, testen, einzeln committen und pushen.
2. Vor einer Freigabe vollständige Regression sowie Installations-, Upgrade- und Rollbacktests ausführen.
3. Einen regulären Merge nach `main` vorbereiten. Die Releaseversion in `.release/request.json` bewusst setzen und den geprüften `dev`-Stand nach GitHub spiegeln.
4. Die vorhandene Pipeline prüft den GitLab-Quellstand, testet, baut AMD64/ARM64-Images und signiert beide Manifeste mit dem bestehenden geschützten Schlüssel. Das Ergebnis bleibt zunächst ein Entwurf.
5. Identische Images in beiden Registries und öffentliche Paketdownloads prüfen. Erst dann beide Releases freigeben.
6. Die tatsächlichen Latest-Manifeste mit altem und neuem Validator prüfen. Veröffentlichungszugänge nach Gebrauch widerrufen.

Ein Quellcode-Push allein ist kein freigegebenes Update. Private Schlüssel und Infrastrukturzugänge bleiben außerhalb des Repositories.
