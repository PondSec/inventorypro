# Releaseprüfung 0.4.0

[English](../en/quality.md) · [Dokumentation](../INDEX.md)

Geprüft am 16. Oktober 2026.

- Vollständige lokale Regression: 714 Tests und 46 Unterprüfungen bestanden; Python 3.14, Chromium und Firefox.
- Zusätzliche Linux-Docker-Prüfung mit Python 3.12: 94 Backendtests bestanden. Beide Läufe melden zwei bestehende Deprecation-Warnungen aus der LDAP-Abhängigkeit.
- Neue Abläufe: private und geteilte Wünsche, Teilmengen, Übernahme als echte Assets, vorhandene Assets, Projektzusammenstellung, Berechtigungen und atomare Mehrfachaktionen.
- Lagerplanung: 3D-Ansicht im Arbeitsbereich, sichtbare Platzierungen, Tastatur, Light/Dark, mobile Dialoge, Löschen und Fehlerbehandlung.
- Deutsch und Englisch sowie unveränderte Nutzerdaten sind durch Browsertests geprüft. Vorhandene visuelle Baselines wurden verglichen; neue Lageransichten zusätzlich als Screenshots kontrolliert.
- Neue Commits wurden auf Zugangsdaten geprüft; keine Funde. Private Betriebsunterlagen gehören nicht zu den Release-Artefakten.

Die signierten Release-Artefakte durchlaufen zusätzlich die Linux-Releasepipeline sowie Installations-, Upgrade- und Rollbackprüfungen vor Veröffentlichung. Deren Ergebnis wird nach Abschluss ergänzt. Windows und Safari wurden nicht ausgeführt. Die öffentliche Bildquelle garantiert keine vollständige Produktabdeckung.

## Frühere Prüfung: 0.3.1

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
