# Automatische Übernahme in den gemeinsamen Assetbestand

Neue Installationen verwenden unmittelbar Assets und Asset-Kategorien. Beim
ersten Start dieser Version wird ein vorhandener Bestand automatisch übernommen;
eine Neuinstallation oder ein manueller Datenbankschalter ist nicht erforderlich.

Vor Änderungen an einer bestehenden Inventardatenbank erstellt die Anwendung
eine SQLite-Sicherung unter `backups/pre-asset-conversion/` neben der Datenbank.
Im Standardcontainer liegt sie somit unter `/data/backups/pre-asset-conversion/`.
Verzeichnis und Datei sind mit 0700/0600 geschützt, die Sicherung wird auf
SQLite-Integrität geprüft. Eine fehlgeschlagene Sicherung verhindert die Übernahme.

Nach den versionierten Schemamigrationen übernimmt ein transaktionaler Dienst die
bisherigen Geräte und Kategorien als Assets. Alte IDs und Geschäftsdaten bleiben
für Integrationen, Historie und Rechte erhalten. Mengen mehrerer Inhaltszeilen
werden addiert, deren Notizen gemeinsam übernommen; Originalzeilen bleiben stehen.
Eigene Fotos referenzieren dieselben persistenten Serverdateien.

Ungültige Mengen, Zyklen oder Fremdschlüssel verhindern eine teilweise Übernahme.
Ein bereits übernommener Bestand wird beim Neustart nicht nochmals angelegt.
Gelöschte leere Standardkategorien und Standorte werden nicht wieder ausgesät.
Anmeldung und bisherige Startadresse führen in den gemeinsamen Bestand.
Die bestehende Einstellung für automatische Updates und deren Wartungsfenster
werden durch diese Übernahme nicht geändert.

Die Vorabkopie enthält die Datenbank, keine Bilddateien. Für ein vollständiges
Rollback zusätzlich das vorhandene Datenvolume einschließlich Uploads erhalten
und das Update-/Rollbackverfahren des Updaters verwenden. Eine Rückkehr auf die
alte Anwendung erfordert deren passende Datenbankkopie; die additive SQL-Down-
Migration allein ersetzt nach erfolgter Übernahme keine Instanzwiederherstellung.

Die historische Test-Suite kann intern den alten Ausgangszustand gezielt laden.
Die Produktionsvoreinstellung benötigt diese Testkonfiguration nicht.
