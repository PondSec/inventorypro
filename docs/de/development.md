# Entwicklung und Qualitätssicherung

[English](../en/development.md) · [Dokumentation](../INDEX.md)

## Lokale Umgebung

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m playwright install chromium firefox
python -m pytest -q
```

Unter Windows `.venv\Scripts\Activate.ps1` verwenden. Runtimeabhängigkeiten sind in `requirements.lock` gebunden. Flask und Jinja bleiben der Frontend-/Backend-Stack; gemeinsame Komponenten stehen in `templates/_ui.html`, Shell und Basistemplates. Design-Tokens und Layoutregeln liegen in `static/design-system.css` und `static/enterprise.css`.

## Architektur

`app.py` enthält bestehende Verträge und die Modulregistrierung. Fachbereiche unter `inventorypro/domains/` kapseln Inventar, Medien, Exporte und weitere Dienste. Checksummierte SQL-Migrationen liegen in `migrations/`. Die Kompatibilitätsschicht erhält historische Geräte-IDs und Berechtigungsgrenzen; neue Oberflächen verwenden Assets.

Statische Oberflächentexte werden über `inventorypro/i18n.py` und `static/locale-en.json` übersetzt. JavaScript verwendet `uiText()` ausschließlich für Oberflächentexte. Nutzerdaten, technische IDs, Feldschlüssel, API-Werte und CSS-Klassen nicht übersetzen. Platzhalter und Escaping müssen erhalten bleiben.

## Tests

Die Suite verwendet isolierte Datenbanken und synthetische Datensätze. Browsertests laufen mit Chromium und Firefox. Sie prüfen unter anderem Rollen, CSRF, CRUD, Kategorieintegrität, enthaltene Assets, Ticketlöschung, Medienzugriff, Sprachwechsel, Fokus, Responsive Layouts und Themes. Plattformabhängige visuelle Baselines stehen unter `tests/visual-baselines/`.

`scripts/visual_audit.py` schreibt Screenshots standardmäßig in `.qa-artifacts/visual-audit`, nicht in die öffentliche Dokumentation. Reale Daten, Betriebsprotokolle oder interne Infrastruktur dürfen weder Testfixtures noch öffentliche Screenshots werden. Ein Testbericht nennt die tatsächlich ausgeführten Prüfungen und Einschränkungen.

Die Release-Skripte `check_release_install.py`, `check_asset_image_upgrade.py`, `check_release_upgrade.py` und `check_release_volume_rollback.py` prüfen Dockerinstallation und Rückfall. Aufrufoptionen jeweils mit `--help` lesen. Tests zuerst mit wegwerfbaren Testvolumes ausführen.


### Visuelle Prüfung der Planung

`python -m pytest -q tests/test_wishes_visual.py` vergleicht die Planungsansicht in Chromium und Firefox, mit hellem und dunklem Theme sowie Desktop- und Mobilgrößen. Die eingecheckten Pixelbaselines wurden unter macOS geprüft. Auf anderen Betriebssystemen werden Ansichten aufgenommen; ohne passende Baseline wird der Pixelvergleich als übersprungen ausgewiesen. Interaktionstests laufen trotzdem.

Neue Vergleichsbilder ausdrücklich mit `UPDATE_WISH_VISUALS=1 python -m pytest -q tests/test_wishes_visual.py` erzeugen, alle Änderungen visuell prüfen und danach ohne diese Variable erneut testen. Baselines niemals allein wegen eines fehlgeschlagenen Vergleichs ersetzen.
