# Inventory Pro

Inventory Pro ist eine professionelle Web-Plattform für Inventarisierung, Helpdesk und Wissensmanagement. Sie bündelt Hardware-Assets, Support-Prozesse und Betriebsinformationen in einer Oberfläche – mit rollenbasierter Zugriffskontrolle, Automatisierungen und optionalen Betriebsmodulen.

## Inhalt
- [Überblick](#überblick)
- [Funktionen](#funktionen)
- [Module](#module)
- [Technischer Stack](#technischer-stack)
- [Schnellstart](#schnellstart)
- [Konfiguration](#konfiguration)
- [Betrieb & Wartung](#betrieb--wartung)
- [Lizenz](#lizenz)

## Überblick
Inventory Pro kombiniert Inventarisierung, Ticketing und Wissensdatenbank. Teams behalten Geräte, Assets und Standorte im Blick, dokumentieren Änderungen im Aktivitätslog und verwalten Tickets über Kategorien, Prioritäten und SLAs. Ergänzend stehen Roadmaps, Abhängigkeitsanalysen und eine „Time Machine“ für historische Ereignisse bereit.

## Funktionen
### Inventar & Assets
- **Dynamische Kategorien** für Geräte mit frei definierbaren Feldern.
- **Geräteverwaltung** mit Seriennummern, Standorten, Tags und Notizen.
- **Asset-Registry** inkl. Lebenszyklusdaten (Anschaffung, Inbetriebnahme, Abschreibung, Ausmusterung).
- **Wartungsplanung** für Geräte inklusive Status-Tracking.

### Helpdesk & Wissen
- **Ticket-System** mit Kategorien, Prioritäten, Status, SLA/Due-Dates und Eskalationsstufen.
- **Kommentare & interne Notizen** sowie Asset-Zuordnungen zu Tickets.
- **Benachrichtigungen per E-Mail** für Ticket-Events.
- **Wissensdatenbank** mit Kategorien, Artikeln und Ticket-Referenzen.

### Planung & Transparenz
- **Roadmaps** mit Meilensteinen und Ticket-Verknüpfung.
- **Abhängigkeits-Graph** zwischen Assets, Tickets, Roadmaps und Organisationseinheiten.
- **Time-Machine-Ansicht** als Zeitstrahl aus dem Aktivitätslog.
- **Analytics/Statistiken** für Tickets, Reporter und Asset-Häufigkeiten.

### Sicherheit & Governance
- **Rollen- und Rechteverwaltung (RBAC)** mit granularen Berechtigungen.
- **Multi-Faktor-Authentifizierung (TOTP)** inkl. QR-Code Setup und Recovery.
- **Audit-Log** für Aktionen und Änderungen im System.

### Daten & Betrieb
- **Export/Import** von Inventardaten (SQLite/JSON/CSV) inkl. optionaler Uploads.
- **Automatisierte Backups** mit Zeitplan, Retention, Kompression und optionaler Verschlüsselung.
- **Server-Einstellungen** für Betrieb, Sicherheit, Sessions und Feature-Flags.

## Module
Inventory Pro bringt optionale Betriebs-Module für IT-Teams mit:

- **Health Monitoring**: Dashboard für System-, Netzwerk- und Service-Checks inkl. Incidents und Trenddaten.
- **Maintenance Console (Terminal)**: gesicherte Diagnose-Recipes (Ping, DNS, HTTP, Logs, DB-Reads) ohne freien Shell-Zugriff.

## Technischer Stack
- **Backend:** Python 3 / Flask
- **Frontend:** HTML, CSS, Vanilla JS, Alpine.js, Tailwind via CDN
- **Datenbank:** SQLite
- **Jobs & Scheduler:** APScheduler
- **Sicherheit:** Werkzeug Password Hashing, TOTP (pyotp), optional Verschlüsselung via Fernet

## Schnellstart
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Die Anwendung läuft anschließend standardmäßig auf `http://localhost:5000`.

## Konfiguration
### Wichtige Umgebungsvariablen
| Variable | Zweck | Default |
| --- | --- | --- |
| `DATABASE_URL` | Postgres-Backup via `pg_dump` | – |
| `INVENTORY_UPLOADS_DIR` | Pfad für Uploads | `uploads/` |
| `INVENTORY_MAX_IMPORT_BYTES` | Max. Importgröße | `52428800` |
| `BACKUP_ENCRYPTION_KEY` | Schlüssel für Backup-Verschlüsselung | – |
| `INVENTORY_ANTIVIRUS_COMMAND` | Optionaler AV-Check beim Import | – |
| `APP_VERSION` | Anzeige in der UI/Diagnostics | `unbekannt` |
| `FLASK_ENV` | Environment Label | `production` |

### Server-Einstellungen (UI)
Im Admin-Bereich können u. a. Backup-Strategien, Import/Export-Optionen, Sicherheitsrichtlinien, MFA-Pflicht und IP-Whitelists verwaltet werden.

## Betrieb & Wartung
- Für Produktionsumgebungen empfiehlt sich ein WSGI-Server (z. B. Gunicorn) hinter einem Reverse-Proxy.
- Backups sollten vor Updates erzwungen und regelmäßig getestet werden.
- Die optionalen Module **Health** und **Terminal** können im Server-Settings-Panel aktiviert bzw. deaktiviert werden.

## Lizenz
AGPL-3.0 – siehe [LICENSE](LICENSE).
