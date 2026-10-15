# Bedienmuster

Die verbindlichen Komponenten und Quellen stehen in [DESIGN_SYSTEM.md](design-system.md).

## Bestand durchsuchen und bearbeiten

`/inventory` verbindet Geräte und Komponenten/Sets als gemeinsame Arbeitsliste,
ohne deren Datenmodelle zusammenzulegen. Suche, Filter und Sortierung bleiben
im Link erhalten. Persönliche Ansichten speichern diese Parameter pro Konto
im aktuellen Browser; das wird in der Oberfläche ausdrücklich erklärt.

Der Objektname öffnet eine vollständige Detailseite. „Vorschau“ öffnet nur die
wichtigsten vorhandenen Listendaten im Drawer. Zurück schließt ihn, Vorwärts
öffnet ihn wieder. Vollständige Details haben normale URLs und eigene Reiter.
Erfassen beginnt mit Name und Vorlage, weitere Eigenschaften sind optional.

## Tickets und Arbeitsaufgaben

Queues, kompakte Tabelle, Bulk-Aktionen, SLA und bestehende Kürzel bleiben erhalten.
Die globale Navigation ist dieselbe wie in allen anderen Modulen. Dashboardzahlen
führen zu passenden Arbeitslisten und berücksichtigen die eigenen Berechtigungen.
Keine aus mehreren Lücken doppelt gezählten Geräte als angebliche Objektzahl.

## Auswahl großer Mengen

Suche und Vorlagenfilter begrenzen die Ergebnismenge, maximal zwanzig Ergebnisse
pro Seite. Sichtbare Auswahlchips und „Nur ausgewählte“ erlauben die Kontrolle
über mehrere Filter hinweg. Speichern erhält alle bestehenden Zuordnungsdaten.

## Lager- und Platzplanung

Behälter/Lagerplatz → Maße/Einheit → Gegenstände/Mengen → Rotation/Abstände →
Packliste und 2D-Vorschau. Erkanntes Feldmapping bleibt kontrollierbar. 3D ist
optional. Heuristiken versprechen keine optimale oder physikalisch garantierte
Lösung. Details: [STORAGE-PLANNING.md](enterprise/STORAGE-PLANNING.md).

## Gefährliche Aktionen und Speichern

Kategorieentfernung nennt verwendende Einträge und fordert bei Bedarf eine
explizite Zielvorlage; keine stillen kaskadierenden Bestandslöschungen.
Fehler bleiben am Formular sichtbar. Speichern hat genau einen laufenden Zustand;
bei Fehlern bleiben Eingaben erhalten. Tastaturdialoge führen den Fokus zurück.
