# Ausgeführte Qualitätssicherung

Stand 15.10.2026. Testdaten sind synthetisch; keine bestehende Installation wird
für Tests verwendet. Entwicklungscheckout liegt außerhalb des iCloud-Verzeichnisses.

## Lokale Ergebnisse

- Vollständiges pytest auf macOS, Python 3.14.7: **288 Tests und 46 Subtests
  bestanden**, 129 Sekunden. Enthält echte Chromium-/Firefox-Interaktionen,
  gemeinsame Shells, 320/390/1440 px, Light/Dark, Fokusführung, Tickets,
  Inventarsuche, Speichern mit CSRF, Auto-Updates an/aus, Planungsassistent und 3D.
- Anschließende Sicherheitskorrektur an Legacy-Workflowaggregaten: weitere
  gezielte Regression, **14 Tests bestanden**, darunter eingeschränkte Rollen
  und Ausschluss fremder Tickets. Ein vollständiger erneuter Lauf ist bei
  weiteren Produktänderungen nötig; der vorherige Lauf enthält diese zwei
  neuen Sicherheitsfälle noch nicht.
- Docker 29.7.2: aktuelles App-Image erfolgreich gebaut. Isolierter Container
  mit Python 3.12 prüft Runtime-Imports, Migrationen 001–004, SQLite integrity_check
  und enthaltene Planungsdateien. Frühere isolierte Compose-Prüfung verifiziert
  Production-Start, HTTP-Login und persistentes Secret über Neustart hinweg.
- Zwei Warnungen stammen aus ldap3/pyasn1 (veraltete tagMap/typeMap-Importe).

## GitLab CI

`.gitlab-ci.yml` führt auf dev und Merge Requests nach dev die vollständige
pytest-Suite mit Chromium und Firefox aus. Historie wird vollständig geladen,
weil der Kompatibilitätstest den tatsächlich ausgelieferten alten Updater lädt.
JUnit und Screenshots werden 14 Tage als Artefakte erhalten. Keine Deployment-,
Release- oder Image-Push-Jobs. YAML lokal mit Ruby/Psych erfolgreich geparst.

Ein geeigneter GitLab-Runner und Netzwerkzugriff auf die Paket-/Browserquellen
sind erforderlich. Ein erfolgreicher lokaler Lauf beweist keinen erfolgreichen
GitLab-Lauf; Status der ersten Pipeline separat prüfen.

Referenz: [GitLab-Jobartefakte](https://docs.gitlab.com/ci/jobs/job_artifacts/).

## Grenzen

Keine pauschale WCAG-Konformitätszertifizierung, Safari-/Windows-/macOS-
Installationsabnahme oder pixelbasierte visuelle Baseline-Regression behauptet.
Screenshots wurden gezielt visuell geprüft; deren Erzeugung ist kein automatischer
Pixelvergleich. Release-Signierschlüssel, GitLab-Registry und Legacy-Publisher
müssen vor einer Veröffentlichung operativ nachgewiesen werden.
