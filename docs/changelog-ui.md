# Änderungen des Enterprise-Relaunchs

## 0.3.0 – Stable, 15.10.2026

Auf GitLab und im kompatiblen GitHub-Feed veröffentlicht. Finale Images,
Signaturen, alte/neue Updater und Datenbankrücksetzung sind tatsächlich geprüft:
[Releaseabnahme](release-0.3.0-qa.md), [Changelog](changelog-ui.md).

- Gemeinsame kompakte Navigation, Kopfzeile, Tabellen, Formulare und Details
  mit Light-/Dark-Theme in allen Modulen. Bestand als Inventarstartseite.
- Ausschließlich Assets und Asset-Kategorien; Assets können andere Assets mit
  Mengen und Zuordnungsnotizen enthalten. Automatische transaktionale Übernahme
  bisheriger Geräte mit privater Vorabsicherung und erhaltenen Berechtigungen.
- Produktkatalog mit konservativer Modellerkennung, lizenziertem Starterbild,
  öffentlicher Bildsuche, lokalem Cache, eigenen serverseitigen Fotos und Fallbacks.
- Durchsuchbare Filter, kurze paginierte Listen, Zeilenklick zur Objektansicht,
  Detailseiten und Mengen-/Beziehungsauswahl statt langer Checkboxlisten.
- Sichere Kategorieentfernung mit Umordnung; keine implizite Inventarlöschung.
- Ticketlöschung löst unabhängige Roadmap-/Wissens-/Monitoringverweise sauber
  und meldet verbleibende Konflikte ohne teilweise Datenlöschung.
- Kompakte Wissensbasis, Roadmap, Beschaffung, Auswertungen, Standorte,
  Benutzerverwaltung sowie aufgabenbezogene Servereinstellungen.
- Automatische Updates in den Einstellungen ein-/ausschaltbar; bestehende
  Richtlinien, Wartungsfenster und kompatible alte Updatefeeds bleiben erhalten.
- Lager-/Platzplanung mit geführter Einrichtung, Einheiten, Packliste, 2D und 3D.
- Portable Inventarexporte mit Zusammensetzungen, Katalogdaten und Uploads;
  sichere Zusammenführung und unveränderte vollständige Instanzsicherung.
- Echte Chromium-/Firefox-Interaktionstests, fünf visuelle Bildschirmbreiten,
  geprüfte macOS-Pixelbaselines und tatsächliche Docker-Upgrade-/Rollbacktests.
