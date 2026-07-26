# Enterprise-Readiness-Matrix

Stand: 2026-07-26. Diese Matrix dokumentiert ausschließlich nachweisbare Ergebnisse auf `dev`.

| Gate | Status | Implementierung und Testnachweis | Manuelle Prüfung | Commit | Einschränkung / offenes Risiko |
| --- | --- | --- | --- | --- | --- |
| Soll-Ist-Abgleich | teilweise erfüllt | Route-Snapshot: 168 Routen, 165 Endpunkte; lokale Suite zuletzt 166 Tests und 11 Browser-Subtests; Gesamtcoverage 65 % | Struktur- und CI-Status geprüft | `2b72df6` | Vollständige Inventur aller Restdomänen steht aus |
| Architektur | teilweise erfüllt | Backups, Customizing, Exports, Imports, Locations, Tickets und Inventar-Links sind teilweise als Domänenpakete extrahiert; Sitzungs- und Diagnose-Service der Inventar-Links ist extrahiert | Route-Snapshots vor und nach jeder Extraktion | `2b72df6` | `app.py` enthält weiterhin umfangreiche Fachlogik; Proxy-Umschreibung der Inventar-Links verbleibt vorerst dort |
| Berechtigungen | teilweise erfüllt | Dekoratoren und einzelne negative Tests vorhanden | Direkte API-Prüfungen einzelner Bereiche | bestehend | Zentrale Policy-Schicht und Ressourcenmatrix fehlen |
| Datenbank und Migrationen | teilweise erfüllt | Versionierte Migrationen und Migrationstests vorhanden | Migrationspfade noch nicht vollständig gegen alle geforderten Störungen geprüft | bestehend | Inline-Schemapfade und vollständige Recovery-Nachweise prüfen |
| Audit | teilweise erfüllt | Aktivitätsprotokollierung in mehreren Fachabläufen vorhanden | Keine vollständige Ereignismatrix geprüft | bestehend | Request-ID, Ergebnisfelder und Unveränderbarkeit fehlen als Nachweis |
| Import und Export | teilweise erfüllt | CSV, TSV, XLSX und JSON mit Schutzprüfungen und Tests vorhanden | Import- und Exportabläufe teilweise geprüft | bestehend | Vendor-Adapter, Hintergrundjobs und vollständiger Assistent offen |
| Customizing | teilweise erfüllt | Persistenz, Revisionen, Cache-Schutz und Browser-Regressionen vorhanden | Branding und Navigation geprüft | `2a3e320` | Vollständige White-Label-Matrix, E-Mail und Export noch offen |
| UX | teilweise erfüllt | Mobile Playwright-Smokes und Dialog-Fokusregression vorhanden | Kernabläufe nur teilweise abgedeckt | `7210186` | Vollständige UX- und Accessibility-Prüfung offen |
| Jobs und Scheduler | teilweise erfüllt | Einzelne Scheduler- und Backupabläufe vorhanden | Restart- und Mehrworker-Verhalten offen | bestehend | Persistente Job-Infrastruktur fehlt |
| Security | teilweise erfüllt | CSRF, Upload-, Secret-, SSRF- und Inventory-Link-Tests vorhanden | Einzelne Schutzketten geprüft | `e78f1b2` | DNS-Pinning, Redirect-Prüfung und vollständiger Security Review offen |
| Sessions, Cache und Rate Limits | teilweise erfüllt | Bounded Caches und Rate Limits vorhanden | Single-Node-Verhalten geprüft | bestehend | Gemeinsames Produktionsbackend und Multi-Node-Nachweis fehlen |
| Datenbankstrategie | teilweise erfüllt | SQLite-Repositories in neuen Domänen vorhanden | Keine PostgreSQL-Freigabe behauptet | `e78f1b2` | SQLite-Grenzen, Konkurrenztests und Skalierungsdokumentation offen |
| Observability | teilweise erfüllt | Health-Modul und Tests vorhanden | Basis-Health geprüft | bestehend | Readiness, strukturierte Logs, Metriken und Request-Korrelation offen |
| Backup und Restore | teilweise erfüllt | Manifest-, Integritäts- und Restore-Tests vorhanden | Wiederherstellungspfad teilweise geprüft | bestehend | Vollständige Störfallmatrix offen |
| Test- und Quality-Gates | nicht erfüllt | Neue Inventar-Link-Module erreichen mindestens 90 % direkte Coverage | Lokale Suite erfolgreich; Remote-CI zuletzt für `e78f1b2` erfolgreich, für `2b72df6` noch ausstehend | `2b72df6` | Gesamtcoverage 65 %, Branch-Coverage und CI-Schwelle 80 % fehlen |
| Browser-End-to-End-Tests | teilweise erfüllt | Playwright-Mobiltests laufen lokal und in CI | Mobile Navigation und Dialoge geprüft | `7210186` | Geforderte vollständige Kernablaufabdeckung fehlt |
| Linting und Typen | nicht erfüllt | Keine verbindliche vollständige Toolkette nachgewiesen | — | — | Ruff, Format-, Typ-, Import-, JS-, JSON-, YAML- und Template-Gates offen |
| CI-Security und Supply Chain | nicht erfüllt | Remote-Container-Build läuft | Build nach Push geprüft | `e78f1b2` | Audit, Secret Scan, SAST, SBOM, Container-Scan und Attestation offen |
| Release-Prozess | teilweise erfüllt | Versions- und Updateartefakte vorhanden | Release-Ablauf nicht vollständig geprüft | bestehend | Tag-Gate, Signatur- und Artefaktnachweise offen |
| Performance | nicht erfüllt | Keine vollständige synthetische Lastbasis nachgewiesen | — | — | Messungen, Indizes und Grenzwertdokumentation offen |
| Deployment und Betrieb | teilweise erfüllt | Remote-Image-Build erfolgreich | Lokaler Docker-Daemon nicht verfügbar und nicht als Erfolg gewertet | `e78f1b2` | Container-Scan und vollständige Betriebsstörfälle offen |
| Datenschutz und Datenlebenszyklus | nicht erfüllt | Keine vollständige Nachweisführung | — | — | Retention, Lösch- und Pseudonymisierungskonzept offen |
| Dokumentation und Review | nicht erfüllt | Bestehende Dokumente noch nicht gegen aktuellen Stand geprüft | — | — | Abschlussdokumentation und mehrperspektivischer Review offen |

## Aktuelle Reihenfolge

1. Update-Zeitformatfehler mit End-to-End- und Scheduler-Regressionen untersuchen und beheben.
2. Fachdomänen in kleinen, nachweisbaren Schritten aus `app.py` lösen und Repository-Struktur entlang der Domänen vereinheitlichen.
3. Anschließend die offenen Enterprise-Gates in Tabellenreihenfolge mit Tests, CI-Nachweisen und Aktualisierung dieser Matrix bearbeiten.

## Phasenprotokoll

| Phase | Status | Relevante Commits | Ausgeführte Tests | Testergebnis | Coverage | Manuelle Prüfungen | Bekannte Einschränkungen | Offene Punkte |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1.1 Inventar-Link: Sitzung und Diagnose | abgeschlossen | `2b72df6` | 18 Link-Tests; Proxy-POST dreimal wiederholt; vollständige Suite mit 166 Tests und 11 Browser-Subtests; CSS-Build | alle lokalen Prüfungen erfolgreich | Service 90 %, Inventar-Link-Domäne 91 %, gesamt 65 % | Vollständiger Routensnapshot vor und nach der Extraktion identisch: 168 Routen | Lokaler Docker-Daemon nicht verfügbar; Container-Test lokal nicht ausgeführt; Remote-CI für diesen Commit steht noch aus | Proxy-Umschreibung bleibt in `app.py`; globale 80-%-Coverage und weitere Gates offen |
