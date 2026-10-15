# Ausgeführte Qualitätssicherung

Stand 15.10.2026. Ausschließlich synthetische Daten und isolierte Testprojekte.
Entwicklungscheckout liegt außerhalb des iCloud-Verzeichnisses.

## Automatisierte Regression

- macOS, Python 3.14.7: vollständige Regression nach Dialogkorrektur mit
  **304 Tests und 46 Untertests bestanden**, 169 Sekunden. Anschließend zehn
  zusätzliche Releaseauftragfälle und drei vorhandene Brückentests bestanden.
- GitLab-Pipelines 27 (e1fe889) und 28 (2dc4faf): **314 Tests und 46 Untertests
  bestanden**, Python 3.12, Chromium und Firefox. JUnit weist 360 Fälle, null
  Fehler und null Fehlschläge aus. Ältere vollständige Pipelines 23–26 ebenfalls grün.
- GitHub-Releasejob 38722344216: vollständige Regression und Multiarch-Build
  erfolgreich. Vorgängerjob bestand ebenfalls 314 Tests/46 Untertests, scheiterte
  danach an Cloudflares Botprüfung beim Registrylogin; kein Release dabei veröffentlicht.
- Echte Browserinteraktionen: gemeinsame Shells, 320/390/1440 px, Light/Dark,
  Fokusführung, Tickets, Inventarsuche, CSRF, Auto-Updates an/aus, Planung und 3D.
  Statusfarben werden in beiden Themes gegen 4,5:1 geprüft; gesperrter Browserspeicher
  verhindert die Initialisierung nicht. Kein pauschaler WCAG-Konformitätsnachweis.
- Zwei Warnungen stammen aus ldap3/pyasn1 (veraltete tagMap/typeMap-Importe).

## Release-Images 0.2.0

Quellstand: `2dc4faf7e622c553c559cf72d17627c75fa19f90` auf dev.
Multiarch-Digest (linux/amd64 und linux/arm64):
`sha256:33e78db242be0a14d56de3486824dc7bac001055afd3999ad007d5a7eb1680a3`.

- Originaler Signierschlüssel in Actions verwendet, beide tatsächlich erzeugten
  Manifeste gegen den ausgelieferten öffentlichen Schlüssel geprüft. Echter alter
  Validator akzeptiert Legacy-Manifest, neuer Validator GitLab-Manifest.
- Unveränderte vollständige OCI-Kopie GHCR → GitLab einschließlich Plattformen
  und Provenienzmanifesten. Anonymer GitLab-Abruf und Digestvergleich bestanden;
  öffentliches signiertes Paketmanifest bytegleich mit dem signierten Artefakt.
- Frische Compose-Installation des fertigen Images auf Linux und macOS/Docker
  bestanden: HTTP-Login, Runtimeimports einschließlich backups/openpyxl, Migrationen,
  SQLite-Integrität, private zufällige Erstzugangsdaten, erzwungener Passwortwechsel,
  persistentes Secret nach Neustart. Testprojekte/-volumes anschließend entfernt.
- Linux: tatsächlich ausgelieferter alter Updatercode ersetzt den App-Container
  mit dem signierten Release. Gerät/Kategorie/Seriennummer/dynamische Felder und
  Upload bleiben erhalten, Migration und Backup erfolgreich. Neuer Updater zieht
  GitLab-Image; absichtlich negativer Healthcheck löst Datenbank- und Image-Rollback
  aus. Originalschema/-daten wiederhergestellt, vorheriges GHCR-Image gesund.
- macOS: Legacy-App-Upgrade ebenfalls bestanden. Zusätzliche Host-/Guest-SQLite-
  Zugriffe auf einen Bindmount verursachten im Rollback-Test einen disk-I/O-Fehler.
  Deshalb separat im tatsächlichen Docker-Named-Volume geprüft: unveränderte
  Updaterfunktionen sichern/restaurieren Schema und Daten innerhalb Docker;
  anschließender App-Neustart gesund. Nicht als bestandenen gemischten Host-/Guest-
  SQLite-Betrieb ausgegeben; produktive Compose-Datenhaltung bleibt im Named-Volume.

Das alte öffentliche Image 0.0.6 startet unverändert wegen fehlendem inventorypro
und openpyxl nicht. Nur für die lauffähige Legacy-Testbasis wurden restauriertes
Runtimepaket, Migrationen und fehlende Abhängigkeiten eingebunden; beim Upgrade
wurden diese Test-Mounts entfernt. Das neue Image liefert alles selbst aus.
Healthchecks liefen im tatsächlichen Docker-Service-Netz, entsprechend dem Sidecar;
ein früher Host-Port-Testreset wurde nicht als bestandene Abnahme gewertet.

Wiederholbar mit `scripts/check_release_install.py`, `check_release_upgrade.py` und
`check_release_volume_rollback.py`; ausschließlich isolierte synthetische Umgebungen.

## CI und Grenzen

GitLab CI validiert Registry-Rundlauf mit kurzlebigem Jobtoken und synthetischem
OCI-Testimage, danach die vollständige pytest-Suite. JUnit/Screenshots bleiben
14 Tage als Artefakte. Keine Produktionsdeployments aus Testpipelines.

Keine Safari-/Windows-Installationsabnahme oder pixelbasierte visuelle Baseline-
Regression behauptet. Gezielt geprüfte Screenshots ersetzen keinen Pixelvergleich.
Ein nie gestarteter/nicht eingerichteter Updater kann keinen Release automatisch
installieren; deaktivierte Auto-Updates und Wartungsfenster werden respektiert.
