# Administration und Sicherheit

[English](../en/administration.md) · [Dokumentation](../INDEX.md)

## Konten und Rechte

Beim ersten Start wird ein zufälliges Administratorkennwort lokal in einer geschützten Datei abgelegt. Die erste Anmeldung erfordert einen Passwortwechsel. Eine öffentliche Setupregistrierung ist nicht verfügbar. Unter **Kontosicherheit** lässt sich TOTP einrichten; Wiederherstellungscodes anschließend privat verwahren.

Rollen begrenzen Ansichten und Änderungen getrennt. Bestehende Geräte- und Assetrechte bleiben bei der gemeinsamen Assetoberfläche erhalten. Das Zusammenführen der Oberfläche erteilt keine zusätzlichen Rechte. Verknüpfte Instanzen verwenden ihre eigenen Konten und Zugriffsentscheidungen.

## Sprache und Darstellung

Unter **Einstellungen → Server → Allgemein → Sprache der Anwendung** zwischen Deutsch und Englisch wählen und speichern. Die Einstellung gilt für die gesamte Instanz einschließlich Anmeldung. Inventarnamen, Notizen, eigene Feldnamen und andere erfasste Inhalte werden nicht übersetzt. Nach dem Speichern lädt die Oberfläche neu; ein Serverneustart ist nicht erforderlich.

Light- und Dark-Theme lassen sich in der Kopfleiste wechseln. Angepasste Markenfarben und Branding ersetzen keine Urheber- oder Lizenzangaben. Die Ansicht **Über Inventory Pro** enthält den Originalautor und die Lizenz.

## Betrieb

Automatische Updates haben einen eigenen Schalter und ein Wartungsfenster. Änderungen an Host oder Port können einen Neustart erfordern; die Oberfläche zeigt dies an. Für Backups, Exporte, Healthziele und Wartungskonsole gelten zusätzliche Rechte und Serveroptionen.

Secrets, `.env`, Datenbanken, Uploads, private Schlüssel, interne Hostnamen und Betriebsprotokolle gehören nicht in das öffentliche Repository. Sicherheitsberichte zunächst ohne personenbezogene oder interne Daten erstellen. Nach bestätigter Offenlegung betroffene Zugangsdaten widerrufen und abhängige Dienste prüfen; persistente Verschlüsselungsschlüssel nicht ohne Migrations- und Wiederherstellungsplan austauschen.
