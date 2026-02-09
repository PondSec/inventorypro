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
- **Asset-Zuweisung & Checkout** inkl. Historie, Verantwortlichkeit und Rückgaben.
- **Wartungsplanung** für Geräte inklusive Status-Tracking.
- **Anhänge & Dokumente** an Assets, Tickets und Wartungsaufgaben.

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

## Troubleshooting
### npm ERESOLVE bei Docker/Node-Builds (optional)
Dieses Repository enthält **keinen** Node-/Docker-Build. Falls Sie jedoch in Ihrer Umgebung einen separaten Frontend-Container bauen und dabei `npm install` mit einem ERESOLVE-Fehler abbrechen sehen (z. B. Konflikte zwischen `xterm` und `xterm-addon-fit`), prüfen Sie die Versionen in `package.json` und `package-lock.json` auf Konsistenz. Ein typischer Workaround ist, die Peer-Dependencies explizit zu harmonisieren oder beim Build `npm install --legacy-peer-deps` zu verwenden. Damit bleibt der Python/Flask-Startpfad oben unverändert.

## Konfiguration
### Wichtige Umgebungsvariablen
| Variable | Zweck | Default |
| --- | --- | --- |
| `DATABASE_URL` | Postgres-Backup via `pg_dump` | – |
| `INVENTORY_UPLOADS_DIR` | Pfad für Uploads | `uploads/` |
| `INVENTORY_MAX_IMPORT_BYTES` | Max. Importgröße | `52428800` |
| `INVENTORY_MAX_UPLOAD_BYTES` | Max. Uploadgröße für Anhänge | `INVENTORY_MAX_IMPORT_BYTES` |
| `BACKUP_ENCRYPTION_KEY` | Schlüssel für Backup-Verschlüsselung | – |
| `INVENTORY_ANTIVIRUS_COMMAND` | Optionaler AV-Check beim Import | – |
| `APP_VERSION` | Anzeige in der UI/Diagnostics | `unbekannt` |
| `FLASK_ENV` | Environment Label | `production` |
| `INVENTORY_LINKS_ENCRYPTION_KEY` | Verschlüsselungsschlüssel für Linked Inventory Secrets | – |
| `INVENTORY_LINKS_ALLOW_PRIVATE_NETWORKS` | RFC1918-Private Netzwerke erlauben (`1`/`0`) | `1` |
| `INVENTORY_LINK_PROXY_TIMEOUT_SECONDS` | Proxy Timeout für Linked Inventory | `20` |
| `INVENTORY_LINK_PROXY_RATE_LIMIT_MAX_REQUESTS` | Proxy Requests pro Minute | `120` |

### PondSec AI – Ollama (kostenlos, lokal/remote)
PondSec AI nutzt Ollama als Standard-LLM. Es werden **keine** API-Keys benötigt.

**Vorbereitung:**
```bash
ollama pull mistral
```

**Option A (Ollama auf dem Host):**
```bash
export PONDSEC_AI_LLM_PROVIDER=ollama
export PONDSEC_AI_OLLAMA_URL=http://host.docker.internal:11434
export PONDSEC_AI_OLLAMA_MODEL=mistral
```

**Option B (Ollama als Container via Docker Compose):**
```yaml
services:
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama:/root/.ollama
```
```bash
export PONDSEC_AI_LLM_PROVIDER=ollama
export PONDSEC_AI_OLLAMA_URL=http://ollama:11434
export PONDSEC_AI_OLLAMA_MODEL=mistral
```

**Zusätzliche Optionen:**
```bash
export PONDSEC_AI_LLM_TIMEOUT_SECONDS=30
export PONDSEC_AI_LLM_MAX_TOKENS=256
```

**Hinweis:** Wenn Ollama nicht erreichbar ist, nutzt PondSec AI eine deterministische Fallback-Logik.

### Neue Berechtigungen (Auszug)
| Permission | Zweck |
| --- | --- |
| `asset.assign` | Asset an Benutzer/Team zuweisen |
| `asset.checkout` | Asset ausgeben (Checkout) |
| `asset.checkin` | Asset zurücknehmen (Check-in) |
| `asset.view_history` | Zuweisungs-/Checkout-Historie einsehen |
| `attachment.upload` | Anhänge hochladen |
| `attachment.download` | Anhänge herunterladen |
| `attachment.delete` | Anhänge löschen |

### Server-Einstellungen (UI)
Im Admin-Bereich können u. a. Backup-Strategien, Import/Export-Optionen, Sicherheitsrichtlinien, MFA-Pflicht und IP-Whitelists verwaltet werden.

## Linked Inventory Pros (Multi-Instance Federation)
Linked Inventory Pros werden im Bereich **Einstellungen → Linked Inventory Pros** gepflegt. Die Cloud-UI zeigt sie im Sidebar-Abschnitt **Inventory Links**. Die Inhalte werden serverseitig über den Proxy geladen (kein CORS, keine Secrets im Browser).

### Beispiel: Public HTTPS über Cloudflare (inv.pondsec.com)
1. Öffne **Einstellungen → Linked Inventory Pros**.
2. Display Name: `PondSec HQ`
3. Base URL: `https://inv.pondsec.com`
4. Auth Mode: `API Key` oder `Bearer Token` (empfohlen).
5. Secret: Deinen Key/Token eintragen.
6. TLS prüfen aktiviert lassen.
7. Verbindung testen → speichern.

### Beispiel: LAN Host:Port (192.168.20.10:5001)
1. Display Name: `Werkstatt`
2. Base URL: `http://192.168.20.10:5001`
3. Auth Mode: `API Key`/`Bearer Token` (empfohlen).
4. Secret eintragen.
5. Private Netzwerke zulassen aktivieren (Standard).
6. Verbindung testen → speichern.

**Hinweise**
- Secrets werden serverseitig verschlüsselt gespeichert (`INVENTORY_LINKS_ENCRYPTION_KEY` erforderlich).
- Alternativ ist `Login` möglich: Secret im Format `Benutzername:Passwort`, die Session wird serverseitig verwaltet.
- Cookie-basierte Logins werden in v1 nicht geteilt; nutze Header-Auth für zuverlässige Verbindungen.

## Betrieb & Wartung
- Für Produktionsumgebungen empfiehlt sich ein WSGI-Server (z. B. Gunicorn) hinter einem Reverse-Proxy.
- Backups sollten vor Updates erzwungen und regelmäßig getestet werden.
- Die optionalen Module **Health** und **Terminal** können im Server-Settings-Panel aktiviert bzw. deaktiviert werden.

## Lizenz
AGPL-3.0 – siehe [LICENSE](LICENSE).
