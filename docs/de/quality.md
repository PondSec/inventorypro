# Releaseprüfung 0.3.1

[English](../en/quality.md) · [Dokumentation](../INDEX.md)

Geprüft am 16. Oktober 2026 mit synthetischen Daten und getrennten Testvolumes.

## Ergebnis

- Signierter Linux-Pipeline-Lauf: 611 Tests und 46 Unterprüfungen erfolgreich, zwei plattformspezifische visuelle Baselines übersprungen. Keine Fehler. Chromium und Firefox wurden ausgeführt.
- Lokale vollständige Regression vor der letzten zusätzlichen Übersetzungsprüfung: 612 Tests und 46 Unterprüfungen erfolgreich. Abschließende fokussierte Prüfungen decken Übersetzungs-Fallbacks, unveränderte Inventarwerte, Sprachwechsel und die Speicherbestätigung ab.
- Das endgültige Docker-Image besteht Neuinstallation, Erstzugang mit erzwungenem Passwortwechsel, Neustart mit persistentem Schlüssel und Prüfung der vollständigen Pythonmodule sowie Lizenzdateien.
- Upgrades von 0.2.0 und 0.3.0 erhalten Bestandsdaten, Mengen, Rechte, Tickets, Anhänge und Updatepolicy. Der direkte Patch-Upgrade wurde mit dem endgültigen signierten Image ausgeführt. Produktbilder und Ticketlöschung wurden über HTTP geprüft.
- Der echte alte Updater installiert das signierte Image auf nativem Linux. Der neue Updater stellt nach absichtlich fehlgeschlagenem Healthcheck vorherige Datenbank, Schema und Image wieder her. Auch lokal gebaute Ausgangsimages und Docker-Datenvolumes wurden geprüft.
- Beide Manifestformate akzeptieren den ursprünglichen Ed25519-Schlüssel und verweisen auf denselben Digest. AMD64- und ARM64-Manifeste sind anonym aus der GitLab-Registry abrufbar.
- Deutsch und Englisch wurden in 14 Arbeitsbereichen sowie bei Assetanlage, direkter Bearbeitung und Auswahldialogen geprüft. Die Sprachwahl wird gespeichert und gilt auch für die Anmeldung. Nutzerdaten bleiben unverändert. Light- und Dark-Ansichten wurden zusätzlich visuell kontrolliert.

## Grenzen der Prüfung

Ein älterer Test, der gleichzeitig mit Host-SQLite und Containern auf ein macOS-Bind-Mount zugreift, zeigte Datenbank-I/O-Fehler. Dieser Ablauf gilt nicht als bestanden. Die nativen Linux-Abläufe und die Docker-Prüfungen mit benannten Datenvolumes bestehen. Der Compose-Schnellstart verwendet ein benanntes Volume.

Windows/PowerShell und Safari wurden für diesen Release nicht ausgeführt. Linux lässt zwei ausschließlich für macOS hinterlegte visuelle Baselines aus; funktionale Browsertests bleiben aktiv. Öffentliche Bildquellen bieten keine garantierte Modellabdeckung. Zwei Deprecation-Warnungen stammen aus der LDAP-Abhängigkeit.
