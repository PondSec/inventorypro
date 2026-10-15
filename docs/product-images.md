# Produktbilder: gemeinsamer serverseitiger Speicher

Produktmodelle, Zuordnungen und Bildherkunft liegen in der Instanzdatenbank.
Hochgeladene Bilder werden auf dem Server geprüft, neu kodiert und als WebP in
`INVENTORY_UPLOADS_DIR/product-media/<Präfix>/<SHA-256>/` gespeichert. Es gibt
Vollansicht, Detailbild und Tabellenminiatur. Im Docker-Schnellstart ist das
`/data/uploads/product-media` im persistenten Volume `inventorypro-data`.

Jeder berechtigte Client lädt dieselben Dateien über authentifizierte
`/media/inventory/…` bzw. `/media/catalog/…`-URLs. Die Anzeige hängt weder vom
Browser des Hochladenden noch von dessen lokalem Speicher ab. Ohne Anmeldung
oder ohne das passende Inventarrecht werden die Dateien nicht ausgeliefert.
Eigene Objektfotos haben Vorrang vor dem Katalogbild; fehlt ein verwendbares
Bild, erscheint das gemeinsame Typ-Symbol.

Beim Container-Update bleibt das Datenvolume eingebunden. Eine vollständige
Datensicherung muss **Datenbank und Upload-Verzeichnis** enthalten. Der Datenexport
mit aktivierter Option für Uploads enthält die Bilddateien; eine reine
Datenbanksicherung enthält nur ihre Zuordnungen. Keine Volumes löschen oder beim
Update durch ein leeres Volume ersetzen.

Automatisierte Prüfungen: Upload und erneuter Abruf in einer unabhängigen
Browsersitzung; unveränderte Dateien und Zuordnungen nach Datenbankinitialisierung;
Anmeldung, Rechte, ETag und verweigerter Zugriff nach Ausblenden eines Bildes.
