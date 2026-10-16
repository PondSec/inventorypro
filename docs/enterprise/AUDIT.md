# Enterprise-Relaunch: technischer Ausgangsstand

Datum: 2026-10-15. Maßgeblich: GitLab `dev`, Commit `900b489`.
Der ursprüngliche lokale Checkout (`347bad1`) ist abweichend und wird nicht überschrieben.
Aktiver sauberer Checkout: `/Users/pond/.codex/workspaces/inventorypro-enterprise`.
Kein AGENTS.md und kein InventoryPro_Codex_Enterprise_Polish.md im Repository vorhanden.

## Kritisch

1. **Start und Lieferumfang:** app.py importiert inventorypro.config, csrf, migrations,
   secrets und mehrere Domainmodule. Der aktuelle dev-Baum enthält weder das Paket
   inventorypro noch migrations. Docker kopiert beide ebenfalls nicht. In der
   Git-Historie (`9666963`) existieren die benötigten Implementierungen. Sie müssen
   gezielt wiederhergestellt und gegen den aktuellen Anwendungscode getestet werden.
2. **Datenverlust:** DELETE /api/categories/<id> löscht Geräte, Notizen, Tags und
   Wartungsaufgaben ohne gesonderte Bestätigung. Assets werden bei Kategorie-Löschung
   still ihrer Kategorie beraubt. Beide Abläufe brauchen Referenzschutz und explizite
   Umzuordnung; dynamische Werte und Verknüpfungen müssen erhalten bleiben.
3. **Bekanntes Produktionssecret:** Compose setzt einen öffentlich bekannten
   APP_SECRET_KEY-Fallback; .env.example enthält ein bekanntes Administratorkennwort.
   Sichere, persistente Secrets und eindeutige Erstzugangsdaten sind erforderlich.
4. **Updatekette:** Standardmanifest, Hostfreigabe und Image-Repository zeigen auf
   GitHub/GHCR. Der alte Updater akzeptiert ausschließlich signierte schemaVersion-1-
   Manifeste und sein freigegebenes Image-Repository. Ein bloßer Wechsel der URL
   erreicht bereits installierte Sidecars nicht. Ein Übergang benötigt weiterhin
   ein mit dem bestehenden Schlüssel signiertes Manifest am alten Endpunkt und ein
   kompatibles GHCR-Image. Veröffentlichung/Signierschlüssel sind separate operative
   Voraussetzungen; kein Release oder Produktionsdeployment wird hier ausgelöst.

## Hoch

- **Shell und Interaktion:** base_app wird nur von einem Teil der Seiten verwendet.
  Tickets besitzen sd-shell; Health, Beschaffung, Statistiken, Abhängigkeiten,
  Zeitmaschine, Instanzportal und Einstellungen besitzen eigene Dokumentstrukturen.
  Topbar, Theme, CSRF-Skripte und Navigation müssen zentral vererbt werden.
- **Inventarmodell:** categories → devices ist eigenständig; asset_categories →
  assets → asset_entries bildet Komponenten/Bestand mit Mengen, Beziehungen und
  Zuordnungen ab. Backendmodelle bleiben erhalten. Begriffe und Wege sollen Aufgaben
  erklären, nicht Tabellen abbilden. Dynamische Felder dürfen nicht verloren gehen.
- **Detail-/Auswahloberflächen:** umfangreiche Alpine-Modals in index.html und
  static/script.js; Fokusfilter berücksichtigt derzeit versteckte Elemente nicht.
  Geräte-/Komponentenauswahl, Speicherung und Navigationszustand brauchen Browser-QA.
- **Lagerplanung:** Berechnung, Relationen und 3D bleiben erhalten; Einrichtung über
  Kategorien/Feldmapping ist zu technisch. Maße, Einheiten und fehlende Werte müssen
  vor der Berechnung verständlich geprüft werden.
- **CI:** GitHub-Releaseworkflow veröffentlicht bei main-Push; kein GitLab-CI vorhanden.
  Entwicklungsprüfungen müssen auf dev laufen, Veröffentlichungen explizit bleiben.

## Weitere Prüfbereiche

Tickets: Queues, Bulk, SLA und Tastaturkürzel erhalten. Wissensbasis, Roadmap,
Beschaffung, Standorte, Auswertungen, Abhängigkeiten, Zeitmaschine, Health, Rollen,
Servereinstellungen, Import/Export, Instanzlinks und Authentifizierung verwenden
unterschiedliche Form-/Seitenmuster. Vereinheitlichung inkrementell mit Funktionstests.
app.py umfasst rund 15.000 Zeilen; vorhandene Domainmodule werden weiterverwendet.
Backup/Restore, SQLite-Migrationen, CSRF, Berechtigungen, SLA und Binpacking werden
zuerst mit vorhandenen Tests geprüft. Daten werden ausschließlich synthetisch erzeugt.

## Ausführungsumgebung

macOS ARM64, Python 3.14.7, Node und Docker-CLI vorhanden. Docker-Daemon beim Audit
nicht erreichbar; kein Container-Build/-Start ausgeführt. Python-Testumgebung wird
separat aufgebaut. Browserinstallation und Playwright-Ausführung stehen noch aus.
GitLab lesen und Push-Dry-Run auf dev erfolgreich. Originalordner enthält eine
unberührte lokale .DS_Store-Änderung und blockierende iCloud-Dataless-Dateien.

## Abnahme

Keine vollständige Abnahme allein durch Quellcodeprüfung. Fortschritt, tatsächlich
 ausgeführte Tests, Commit-IDs und verbleibende Grenzen: [Qualitätsbericht](QUALITY.md).
