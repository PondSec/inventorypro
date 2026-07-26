# Enterprise-Readiness-Matrix

Stand: 2026-07-26. Diese Matrix dokumentiert ausschließlich nachweisbare Ergebnisse auf `dev`.

| Gate | Status | Implementierung und Testnachweis | Manuelle Prüfung | Commit | Einschränkung / offenes Risiko |
| --- | --- | --- | --- | --- | --- |
| Soll-Ist-Abgleich | teilweise erfüllt | Route-Snapshot: 173 Routen, 170 Endpunkte; lokale Suite zuletzt 189 Tests und 35 Browser-Subtests; Gesamtcoverage 68 %; Remote-CI bis `a88ba11` erfolgreich | Struktur- und CI-Status geprüft | `db13e85` | Vollständige Inventur aller Restdomänen steht aus; CI für `db13e85` steht noch aus |
| Architektur | teilweise erfüllt | Backups, Customizing, Exports, Imports, Locations, Tickets und Inventar-Links sind teilweise als Domänenpakete extrahiert; Sitzungs- und Diagnose-Service der Inventar-Links ist extrahiert | Route-Snapshots vor und nach jeder Extraktion | `2b72df6` | `app.py` enthält weiterhin umfangreiche Fachlogik; Proxy-Umschreibung der Inventar-Links verbleibt vorerst dort |
| Berechtigungen | teilweise erfüllt | Dekoratoren und einzelne negative Tests vorhanden | Direkte API-Prüfungen einzelner Bereiche | bestehend | Zentrale Policy-Schicht und Ressourcenmatrix fehlen |
| Datenbank und Migrationen | teilweise erfüllt | Versionierte Migrationen und Migrationstests vorhanden | Migrationspfade noch nicht vollständig gegen alle geforderten Störungen geprüft | bestehend | Inline-Schemapfade und vollständige Recovery-Nachweise prüfen |
| Audit | teilweise erfüllt | Aktivitätsprotokollierung in mehreren Fachabläufen vorhanden | Keine vollständige Ereignismatrix geprüft | bestehend | Request-ID, Ergebnisfelder und Unveränderbarkeit fehlen als Nachweis |
| Import und Export | teilweise erfüllt | CSV, TSV, XLSX und JSON mit Schutzprüfungen und Tests vorhanden | Import- und Exportabläufe teilweise geprüft | bestehend | Vendor-Adapter, Hintergrundjobs und vollständiger Assistent offen |
| Customizing | teilweise erfüllt | Persistenz, Revisionen, Cache-Schutz und Browser-Regressionen vorhanden | Branding und Navigation geprüft | `2a3e320` | Vollständige White-Label-Matrix, E-Mail und Export noch offen |
| UX | teilweise erfüllt | Mobile Playwright-Smokes und Dialog-Fokusregression vorhanden | Kernabläufe nur teilweise abgedeckt | `7210186` | Vollständige UX- und Accessibility-Prüfung offen |
| Jobs und Scheduler | teilweise erfüllt | Einzelne Scheduler- und Backupabläufe vorhanden | Restart- und Mehrworker-Verhalten offen | bestehend | Persistente Job-Infrastruktur fehlt |
| Security | teilweise erfüllt | CSRF, Upload-, Secret-, SSRF- und Inventory-Link-Tests vorhanden; TOTP wird erst nach Codebestätigung aktiviert, der Reset erfolgt TOTP-gebunden und MFA kann bei globaler Policy nicht deaktiviert werden | Lokale MFA- und Reset-Regressionen geprüft | `db13e85` | DNS-Pinning, Redirect-Prüfung und vollständiger Security Review offen |
| Sessions, Cache und Rate Limits | teilweise erfüllt | Bounded Caches und Rate Limits vorhanden | Single-Node-Verhalten geprüft | bestehend | Gemeinsames Produktionsbackend und Multi-Node-Nachweis fehlen |
| Datenbankstrategie | teilweise erfüllt | SQLite-Repositories in neuen Domänen vorhanden | Keine PostgreSQL-Freigabe behauptet | `e78f1b2` | SQLite-Grenzen, Konkurrenztests und Skalierungsdokumentation offen |
| Observability | teilweise erfüllt | Nicht-OK-Health-Ergebnisse erzeugen deduplizierte Incident-Tickets mit hoher Priorität und SLA-Kategorie; Regressionstests vorhanden | Ticket-Verknüpfung im lokalen Ablauf geprüft | `db13e85` | Readiness, strukturierte Logs, Metriken und Request-Korrelation offen |
| Backup und Restore | teilweise erfüllt | Manifest-, Integritäts- und Restore-Tests vorhanden | Wiederherstellungspfad teilweise geprüft | bestehend | Vollständige Störfallmatrix offen |
| Test- und Quality-Gates | nicht erfüllt | Neue Inventar-Link-Module erreichen mindestens 90 % direkte Coverage; Updater erreicht 94 % direkte Coverage | Lokale Suite mit 189 Tests und 35 Browser-Subtests erfolgreich | `db13e85` | Gesamtcoverage 68 %, Branch-Coverage und CI-Schwelle 80 % fehlen; Remote-CI für `db13e85` steht aus |
| Browser-End-to-End-Tests | teilweise erfüllt | Playwright-Mobiltests laufen lokal und in CI | Mobile Navigation und Dialoge geprüft | `7210186` | Geforderte vollständige Kernablaufabdeckung fehlt |
| Linting und Typen | nicht erfüllt | Keine verbindliche vollständige Toolkette nachgewiesen | — | — | Ruff, Format-, Typ-, Import-, JS-, JSON-, YAML- und Template-Gates offen |
| CI-Security und Supply Chain | nicht erfüllt | Remote-Container-Build läuft erfolgreich | Build nach Push im CI-Lauf `30202728396` geprüft | `be4071f` | Audit, Secret Scan, SAST, SBOM, Container-Scan und Attestation offen; GitHub meldet noch Node-20-Deprecation für verwendete Actions |
| Release-Prozess | teilweise erfüllt | Versions- und Updateartefakte vorhanden | Release-Ablauf nicht vollständig geprüft | bestehend | Tag-Gate, Signatur- und Artefaktnachweise offen |
| Performance | nicht erfüllt | Keine vollständige synthetische Lastbasis nachgewiesen | — | — | Messungen, Indizes und Grenzwertdokumentation offen |
| Deployment und Betrieb | teilweise erfüllt | Remote-Image-Build im CI-Lauf `30202728396` erfolgreich | Lokaler Docker-Daemon nicht verfügbar und nicht als Erfolg gewertet | `be4071f` | Container-Scan und vollständige Betriebsstörfälle offen |
| Datenschutz und Datenlebenszyklus | nicht erfüllt | Keine vollständige Nachweisführung | — | — | Retention, Lösch- und Pseudonymisierungskonzept offen |
| Dokumentation und Review | nicht erfüllt | Bestehende Dokumente noch nicht gegen aktuellen Stand geprüft | — | — | Abschlussdokumentation und mehrperspektivischer Review offen |

## Aktuelle Reihenfolge

1. Update-Zeitformatfehler mit End-to-End- und Scheduler-Regressionen beheben. **Lokal abgeschlossen, CI-Nachweis offen.**
2. Fachdomänen in kleinen, nachweisbaren Schritten aus `app.py` lösen und Repository-Struktur entlang der Domänen vereinheitlichen.
3. Anschließend die offenen Enterprise-Gates in Tabellenreihenfolge mit Tests, CI-Nachweisen und Aktualisierung dieser Matrix bearbeiten.

## Phasenprotokoll

| Phase | Status | Relevante Commits | Ausgeführte Tests | Testergebnis | Coverage | Manuelle Prüfungen | Bekannte Einschränkungen | Offene Punkte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.1 Inventar-Link: Sitzung und Diagnose | abgeschlossen | `2b72df6`, `be4071f` | 18 Link-Tests; Proxy-POST dreimal wiederholt; vollständige Suite mit 166 Tests und 11 Browser-Subtests; CSS-Build; Remote-CI | alle lokalen Prüfungen sowie Remote-Test und Image-Build erfolgreich | Service 90 %, Inventar-Link-Domäne 91 %, gesamt 65 % | Vollständiger Routensnapshot vor und nach der Extraktion identisch: 168 Routen | Lokaler Docker-Daemon nicht verfügbar; Container-Test lokal nicht ausgeführt | Proxy-Umschreibung bleibt in `app.py`; globale 80-%-Coverage und weitere Gates offen |
| 1.2 MFA, Update-Fenster und Health-Incidents | lokal abgeschlossen; CI ausstehend | `db13e85` | 54 zielgerichtete Tests; vollständige Suite mit 189 Tests und 35 Browser-Subtests; CSS-Build; Python-Kompilierung; JavaScript- und Workflow-YAML-Prüfung | alle lokalen Prüfungen erfolgreich | Updater 94 %, Security-Tests 99 %, gesamt 68 % | Routeninventar: 173 Routen, 170 Endpunkte; vier absichtliche Pfad-/Methodenaufteilungen, keine Methodenüberlappung; isolierte Vorschau neu gestartet | Lokaler Docker-Daemon nicht verfügbar; Container-Test lokal nicht ausgeführt; 55 Deprecation-Warnungen zu `datetime.utcnow` | Remote-CI für `db13e85`; 80-%-Gesamtcoverage, weitere Sicherheits- und Release-Gates sowie Domänenextraktionen offen |
