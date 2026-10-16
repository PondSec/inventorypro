# Produktbilder

[English](../en/product-images.md) · [Dokumentation](../INDEX.md)

Der Produktkatalog speichert Hersteller, Modell, Identifikatoren, Bildherkunft und Lizenz in der Instanzdatenbank. Ein lizenziertes MacBook-Air-M4-Modellbild ist enthalten. Ein Modellbild zeigt eine Produktfamilie, nicht das individuelle inventarisierte Exemplar.

## Automatische Zuordnung

Ein Administrator kann die öffentliche Bildquelle im Produktkatalog aktivieren und **Fehlende Produktbilder suchen** starten. Wikidata liefert Modellinformationen; geeignete Bilder werden aus Wikimedia Commons abgerufen. Existiert das Foto nur auf Commons, wird zusätzlich nach einem vollständigen, eindeutigen Modellnamen im Dateititel gesucht. Vergleichsbilder und abweichende Generationen werden ausgeschlossen. Nur Hersteller und öffentliche Modellangaben werden gesucht. Persönliche Zuweisungen, Standorte, Seriennummern und interne Inventarnamen werden nicht übermittelt.

Hersteller und vollständiges Modell müssen passen. Eindeutige Produktnamen wie „Apple AirPods 4 ANC“ werden auch ohne separate Hersteller- und Modellfelder erkannt. Die Namenserkennung verwendet begrenzte Produktmuster; unbekannte Freitexte und persönliche Namenszusätze werden nicht als Suchbegriffe übertragen. Bei anderen Produkten Hersteller und vollständiges Modell in den Eigenschaften hinterlegen. Beim Öffnen des Inventars prüft ein Hintergrundprozess vorhandene Einträge schrittweise nach; die Liste wartet nicht auf externe Bildabrufe. Mehrdeutige Treffer oder ungeeignete Lizenzen erhalten keine automatische Bildzuordnung. Die Quellenverwaltung zeigt Jobs, Fehltreffer und Fehler. Es gibt keine vollständige öffentliche Datenbank für alle inventarisierbaren Dinge. Ohne geeignetes Bild erscheint ein gemeinsames Typ-Symbol.

## Eigene Fotos und Persistenz

Jedes berechtigte Objekt kann ein eigenes Foto erhalten. Dieses hat Vorrang vor dem Katalogbild. Der Server prüft und kodiert Uploads neu; WebP-Dateien einschließlich Miniaturen liegen unter `INVENTORY_UPLOADS_DIR/product-media/`, im Standardcontainer unter `/data/uploads/product-media/`. Alle berechtigten Clients laden dieselben Dateien über authentifizierte Medien-URLs. Es handelt sich nicht um lokalen Browserspeicher.

Nach Abschalten der öffentlichen Quelle bleiben bereits zwischengespeicherte Dateien verfügbar. Für Updates und Wiederherstellungen Datenbank **und** Uploadverzeichnis erhalten. Ein Export mit eingeschlossenen Uploads kann Bilder transportieren; ein reiner Datenbankexport enthält nur Zuordnungen. Kollidierende Dateien werden beim Import nicht still überschrieben.

[Bildlizenz und Urheber des Starterbildes](../../inventorypro/data/product_images/LICENSE.md). Jede Bildquelle behält ihre eigene Lizenz; die Anwendungslizenz ersetzt sie nicht.
