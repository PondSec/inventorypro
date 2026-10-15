# Ausgeführte Dockerprüfung der Assetübernahme

Stand: Quellcommit `f192b44`, lokales QA-Image `inventorypro-release-qa:f192b44`,
APP_VERSION `0.3.0-qa.f192b44`. Docker Desktop 29.7.2, Linux ARM64, Python 3.12.
Dies ist ein lokales QA-Image, kein öffentlich freigegebener Stable-Release.

## Neuinstallation

`scripts/check_release_install.py --image … --version 0.3.0-qa.f192b44` bestanden:

- Eigenes temporäres Compose-Projekt und Datenvolume, anschließend entfernt.
- Vollständige Pythonmodule, Migrationen, kanonischer Bestand und Starterbilder.
- Privater persistenter Zufallsschlüssel und private Erstzugangsdatei mit 0600.
- Neustart erhält denselben Schlüssel; erzeugte Zugangsdaten funktionieren per
  tatsächlichem HTTP-Login und erzwingen den ersten Passwortwechsel.

## Upgrade und Rückfall

`scripts/check_asset_image_upgrade.py` gegen das tatsächlich veröffentlichte
0.2.0-Image mit Digest
`sha256:33e78db242be0a14d56de3486824dc7bac001055afd3999ad007d5a7eb1680a3`
und das lokale QA-Image bestanden:

- 20 synthetische Altgeräte, zwei vorhandene Zusammenstellungen, Inhaltsmengen,
  Beschreibungen, dynamische Werte, Benutzer-/Rollenverweise und Ticket/Roadmap.
- Automatische Übernahme ergibt 22 Assets, zwei Inhaltsbeziehungen und eine
  geprüfte Vorabkopie. Altzeilen bleiben erhalten; ein weiterer Neustart dupliziert nichts.
- Auto-Updates bleiben deaktiviert, individuelles Wartungsfenster und Intervall
  sowie Anwendungsschlüssel und vorhandene Upload-Datei bleiben erhalten.
- Tatsächlicher HTTP-Login, Asset-Pagination und lokal ausgeliefertes MacBook-
  Katalogfoto funktionieren. Ticket mit Roadmap-Verweis wird per HTTP ohne 503 gelöscht.
- App gestoppt, Vorabkopie in das isolierte Volume zurückgespielt, altes Image
  gestartet: alle ursprünglichen Geschäftszeilen wiederhergestellt.

Die Prüfdaten erfüllen die alten API-Invarianten (gültige Kategorie, Ersteller-ID).
Additive neue Spalten werden beim Vergleich erlaubt; vorhandene Spaltenwerte und
Zeilenanzahlen werden geprüft. Das Skript verändert keine Kundencontainer.

Diese Prüfung ersetzt nicht den noch ausstehenden Test der endgültigen signierten
Manifeste, der alten/neuen Updater und der veröffentlichten Multiarch-Images.
