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

Die öffentliche Quelle wird im Produktkatalog durch einen Administrator aktiviert.
„Fehlende Produktbilder suchen“ stellt geeignete öffentliche Modellinformationen
in eine Hintergrundwarteschlange. Es werden keine persönlichen Zuordnungen,
Standorte, Seriennummern oder internen Inventarbezeichnungen gesendet. Ergebnisse
werden auf Hersteller und vollständiges Modell geprüft; mehrdeutige Modelle oder
nicht freigegebene Bildlizenzen bleiben ohne automatische Bildzuordnung.

Die Quellenverwaltung zeigt laufende Jobs, Fehltreffer und Fehler. Nach Abschalten
werden keine neuen Bilder abgerufen; bereits lokal gespeicherte Dateien bleiben
für berechtigte Clients verfügbar. Ein Offlinebetrieb benötigt daher für vorhandene
Bilder keine Verbindung zu Wikidata oder Wikimedia Commons. Der öffentliche Dienst
bietet keine vollständige Abdeckung aller inventarisierbaren Dinge; eigene Fotos
und die einheitlichen Typ-Symbole sind weiterhin für jedes Objekt verfügbar.

Portable JSON-, CSV- und Excel-Exporte enthalten auch Asset-Inhalte, Tags,
Katalogmodelle, Bildkennungen, Bildlizenzen und individuelle Bildzuordnungen.
Mit aktivierter Upload-Option lassen sich die erzeugten ZIP-Archive wieder
importieren, einschließlich der JSON-, SQLite- oder Excel-Datei im Archiv.
Vorhandene Dateien mit abweichendem Inhalt werden dabei nicht überschrieben.
Zusammenführen aktualisiert Datensätze ohne deren abhängige Einträge zu löschen.

Für eine vollständige Instanzwiederherstellung weiterhin Datenbank und Datenvolume
sichern: Portable Inventarexporte enthalten keine Konten, Rollen, Tickets, Secrets
oder Instanzeinstellungen. Verweise auf nicht vorhandene Benutzer oder unabhängige
Vorgänge führen zu einem zurückgerollten Import. JSON/SQLite sind für typgetreue
Archivierung vorzuziehen; Tabellenformate unterscheiden leere Zellen und NULL nicht.
