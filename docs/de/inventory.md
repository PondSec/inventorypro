# Assets und Bestand

[English](../en/inventory.md) · [Dokumentation](../INDEX.md)

**Inventar → Bestand** ist die zentrale Arbeitsliste. Suche, Kategorie, Standort, Status und Zuweisung grenzen den Bestand ein. Die Seitengröße begrenzt die Zeilenanzahl. Ein Klick auf einen Eintrag öffnet dessen Detailbereich; umfangreiche Informationen stehen auf der Detailseite.

Ein Asset kann andere Assets mit Mengen enthalten: Ein Mini-PC enthält beispielsweise eine CPU und zwei RAM-Module. **Enthaltene Assets** zeigt diese Richtung, **Verwendet in** die übergeordneten Objekte. Suche und Auswahl bleiben im Auswahldialog getrennt erhalten. Selbstverweise und Zyklen werden abgelehnt. Allgemeine Beziehungen sind unabhängig von der Inhaltszuordnung.

Unter **Bearbeiten** lassen sich Stammdaten direkt auf der Detailseite ändern. **Speichern** übernimmt sie; **Abbrechen** verwirft bestätigte Änderungen. Bei Fehlern bleiben Eingaben erhalten. Gleichzeitige Änderungen werden über eine Versionsprüfung erkannt.

Beim Löschen eines Assets werden dessen eingehende und ausgehende Verknüpfungen aufgelöst. Andere Assets, Tickets, Bestellungen und Softwareeinträge bleiben erhalten. Unbekannte blockierende Datenbankverweise führen zu einer Fehlermeldung und einem vollständigen Rollback. Kategorien mit Bestand werden vor einer Löschung geschützt und können über eine Umzuordnung geleert werden.

## Bestehende Daten

Die automatische Assetübernahme sichert die Datenbank vorab unter `backups/pre-asset-conversion/` neben der Datenbank mit privaten Dateirechten. Ohne gültige Sicherung beginnt keine Übernahme. Bestehende Geräte, Kategorien, IDs und Rechte werden über Kompatibilitätszuordnungen erhalten; eigene Bilder referenzieren dieselben Serverdateien. Wiederholte Starts legen keine zusätzlichen Assets an.

Gleiche Namen beweisen keine Dublette. Physisch verschiedene Objekte können gleich heißen. Es gibt deshalb keine automatische namensbasierte Löschung. Eine ausdrücklich geprüfte Zusammenführung benötigt eine Sicherung und muss Seriennummern, Felder, Bilder, Verknüpfungen und Rechte berücksichtigen.

## Mehrere Assets bearbeiten oder löschen

1. Assets über die Checkboxen markieren. Die Checkbox im Tabellenkopf wählt die Einträge der aktuellen Seite aus, höchstens 100. Beim Seitenwechsel wird die Auswahl aufgehoben.
2. **Gemeinsam bearbeiten** öffnet die Liste der ausgewählten Assets. Für Kategorie, Standort, Kostenstelle, Garantieende und Ausmusterungsangaben jeweils **Unverändert lassen**, **Wert setzen** oder **Wert entfernen** wählen.
3. **Änderungen speichern** übernimmt ausschließlich die ausgewählten Felder. Individuelle Namen, Seriennummern, Eigenschaften und Bilder bleiben erhalten. Ein Kategorienwechsel prüft die vorhandenen Eigenschaften gegen die neue Kategorie.

**Auswahl löschen** zeigt vor dem endgültigen Löschen Anzahl und Namen. Es löscht nur die ausgewählten Assets. Nicht ausgewählte enthaltene oder übergeordnete Assets bleiben erhalten und werden getrennt. Historische Verknüpfungen eines gelöschten Assets werden entsprechend ihrer fachlichen Regeln aufgelöst; ein dadurch nicht mehr erfüllter Wunsch wird wieder als fehlend angezeigt.

Bearbeitungsrechte werden für jedes Asset geprüft. Bei fehlenden Rechten, ungültigen Angaben, blockierenden Verweisen oder zwischenzeitlichen Änderungen wird die gesamte Aktion zurückgesetzt. Nach einem Versionskonflikt den Dialog schließen, die Seite neu laden und die Auswahl prüfen. Ein Exportrecht ist für diese Aktionen nicht erforderlich.

## Lager- und Platzplanung

Die **3D-Ansicht** öffnet den berechneten Packvorschlag direkt im Arbeitsbereich, auch vor dem Speichern. Kameraansichten, Drehen und die Auswahl einzelner Einräumschritte lassen sich per Tastatur bedienen. Escape schließt die Ansicht und kehrt zum auslösenden Button zurück. Die Packliste bleibt die verbindliche textliche Darstellung des heuristischen Vorschlags.

Unter **Gespeicherte Pläne** entfernt **Löschen** nach Bestätigung ausschließlich den Plan und sein Berechnungsergebnis. Die inventarisierten Assets bleiben erhalten. Planersteller und Administratoren können auch Pläne entfernen, deren damalige Assets inzwischen gelöscht wurden. Bestehende Zugriffsbeschränkungen für noch vorhandene Assets gelten weiterhin.
