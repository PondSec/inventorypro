# Releaseprüfung 0.4.0

[English](../en/quality.md) · [Dokumentation](../INDEX.md)

Geprüft am 16. Oktober 2026.

- Vollständige lokale Regression: 714 Tests und 46 Unterprüfungen bestanden; Python 3.14, Chromium und Firefox.
- Zusätzliche Linux-Docker-Prüfung mit Python 3.12: 94 Backendtests bestanden. Beide Läufe melden zwei bestehende Deprecation-Warnungen aus der LDAP-Abhängigkeit.
- Neue Abläufe: private und geteilte Wünsche, Teilmengen, Übernahme als echte Assets, vorhandene Assets, Projektzusammenstellung, Berechtigungen und atomare Mehrfachaktionen.
- Lagerplanung: 3D-Ansicht im Arbeitsbereich, sichtbare Platzierungen, Tastatur, Light/Dark, mobile Dialoge, Löschen und Fehlerbehandlung.
- Deutsch und Englisch sowie unveränderte Nutzerdaten sind durch Browsertests geprüft. Vorhandene visuelle Baselines wurden verglichen; neue Lageransichten zusätzlich als Screenshots kontrolliert.
- Neue Commits wurden auf Zugangsdaten geprüft; keine Funde. Private Betriebsunterlagen gehören nicht zu den Release-Artefakten.

## Signierte Artefakte

- Die signierende Linux-Pipeline besteht 704 Tests und 46 Unterprüfungen. Zehn ausschließlich für macOS hinterlegte Pixelvergleiche werden unter Linux ausgelassen; die funktionalen Chromium-/Firefox-Prüfungen bleiben aktiv.
- Das endgültige signierte Image besteht Neuinstallation, Erstzugang mit Passwortwechsel und Neustart mit unverändertem persistentem Schlüssel. Pythonmodule, Migrationen und Starterbilder sind enthalten.
- Der echte alte Updater installiert 0.4.0 über das kompatible Manifest. Der neue Updater stellt bei absichtlich abgelehntem Healthcheck das vorherige Schema und Image wieder her; die Wiederherstellung wurde auch in einem Docker-Datenvolume geprüft.
- Ein separater direkter Upgradecheck von 0.3.1 erhält Assets, enthaltene Bestandteile, Rechte, Ticketverknüpfungen und serverseitig hochgeladene Bilder. Ein zuvor absichtlich fehlgeschlagener Upgradeversuch stellte Schema und Datensätze exakt wieder her.
- Beide Manifeste werden mit dem bereits ausgelieferten Ed25519-Schlüssel akzeptiert. AMD64- und ARM64-Images sind aus beiden Registries anonym unter demselben Digest abrufbar.
- Im separaten GitLab-Lauf wurden drei Synchronisierungsfehler älterer Browsertests sichtbar. Die Prüfungen warten nun auf Dokumentbereitschaft, Dialogfokus und abgeschlossene Speichernavigationen. Ihre fachlichen Aussagen bleiben erhalten; alle 18 betroffenen Tests und zwei Unterprüfungen bestehen gemeinsam.

Das signierte Laufzeitimage stammt aus Commit `88c8da3`; spätere Änderungen betreffen ausschließlich Tests und diesen Bericht. Windows und Safari wurden nicht ausgeführt. Die öffentliche Bildquelle garantiert keine vollständige Produktabdeckung.

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
