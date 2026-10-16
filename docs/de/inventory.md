# Assets und Bestand

[English](../en/inventory.md) · [Dokumentation](../INDEX.md)

**Inventar → Bestand** ist die zentrale Arbeitsliste. Suche, Kategorie, Standort, Status und Zuweisung grenzen den Bestand ein. Die Seitengröße begrenzt die Zeilenanzahl. Ein Klick auf einen Eintrag öffnet dessen Detailbereich; umfangreiche Informationen stehen auf der Detailseite.

Ein Asset kann andere Assets mit Mengen enthalten: Ein Mini-PC enthält beispielsweise eine CPU und zwei RAM-Module. **Enthaltene Assets** zeigt diese Richtung, **Verwendet in** die übergeordneten Objekte. Suche und Auswahl bleiben im Auswahldialog getrennt erhalten. Selbstverweise und Zyklen werden abgelehnt. Allgemeine Beziehungen sind unabhängig von der Inhaltszuordnung.

Unter **Bearbeiten** lassen sich Stammdaten direkt auf der Detailseite ändern. **Speichern** übernimmt sie; **Abbrechen** verwirft bestätigte Änderungen. Bei Fehlern bleiben Eingaben erhalten. Gleichzeitige Änderungen werden über eine Versionsprüfung erkannt.

Beim Löschen eines Assets werden dessen eingehende und ausgehende Verknüpfungen aufgelöst. Andere Assets, Tickets, Bestellungen und Softwareeinträge bleiben erhalten. Unbekannte blockierende Datenbankverweise führen zu einer Fehlermeldung und einem vollständigen Rollback. Kategorien mit Bestand werden vor einer Löschung geschützt und können über eine Umzuordnung geleert werden.

## Bestehende Daten

Die automatische Assetübernahme sichert die Datenbank vorab unter `backups/pre-asset-conversion/` neben der Datenbank mit privaten Dateirechten. Ohne gültige Sicherung beginnt keine Übernahme. Bestehende Geräte, Kategorien, IDs und Rechte werden über Kompatibilitätszuordnungen erhalten; eigene Bilder referenzieren dieselben Serverdateien. Wiederholte Starts legen keine zusätzlichen Assets an.

Gleiche Namen beweisen keine Dublette. Physisch verschiedene Objekte können gleich heißen. Es gibt deshalb keine automatische namensbasierte Löschung. Eine ausdrücklich geprüfte Zusammenführung benötigt eine Sicherung und muss Seriennummern, Felder, Bilder, Verknüpfungen und Rechte berücksichtigen.
