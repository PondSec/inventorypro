# Module und Arbeitsabläufe

[English](../en/modules.md) · [Dokumentation](../INDEX.md)

## Service Desk

Queues, Suche, Filter und gespeicherte Ansichten strukturieren Tickets. Sammelaktionen berücksichtigen die Berechtigung jedes ausgewählten Tickets. Priorität, Fälligkeit, SLA-Risiko und Eskalation sind getrennte Merkmale. Ticketverknüpfungen zeigen nur sichtbare Assets. Wissensvorschläge und ähnliche Fälle halten dieselben Zugriffsgrenzen ein. Ein Change benötigt vor Abschluss ein erfolgreich abgenommenes Review.

## Beschaffung und Wissen

Beschaffung führt Lieferanten, Verträge, Bestellungen und Bestellpositionen zusammen. Bestellungen können auf Assets verweisen. Die Wissensbasis bietet Artikel, Kategorien und Suche; Roadmaps strukturieren Vorhaben, Meilensteine und Verantwortlichkeiten. Standorte öffnen ihren gefilterten Assetbestand. Auswertungen und Abhängigkeiten verwenden die jeweils zugänglichen Daten. Die Zeitmaschine zeigt historische oder geplante Zustände innerhalb ihres Funktionsumfangs.

## Lager- und Platzplanung

1. Lagerplatz oder Behälter auswählen.
2. Breite, Höhe, Tiefe und gemeinsame Maßeinheit prüfen. Geeignete vorhandene Zahlenfelder können übernommen werden; Feldmapping ist eine erweiterte Option.
3. Gegenstände und Mengen auswählen. Fehlende oder ungültige Abmessungen korrigieren.
4. Rotation, Abstände und Wandabstände festlegen.
5. Packliste, nicht platzierte Gegenstände und Vorschau prüfen; anschließend den Plan speichern.

Die Packliste bleibt ohne 3D-Darstellung nutzbar. Berechnete Vorschläge sind algorithmische Näherungslösungen; sie garantieren keine optimale Packung. Platzierungsprobleme und fehlende Maße müssen vor der praktischen Verwendung geprüft werden.

## Health und Wartungskonsole

Healthprüfungen benötigen passende Rechte; Netzwerkziele und erlaubte Prüfarten werden administrativ begrenzt. Die Wartungskonsole ist standardmäßig deaktiviert und bietet freigegebene Diagnose-Rezepte, keinen freien Shellzugang. `terminal.view`, `terminal.use` und `terminal.db_write` sind getrennte Rechte. Schreibende Datenbankaktionen benötigen zusätzlich die aktivierte Serveroption und erneute Authentifizierung. Sitzungen laufen ab; Ausgaben werden begrenzt und sensible Werte maskiert.
