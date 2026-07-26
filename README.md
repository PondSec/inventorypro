# Inventory Pro

Flask-basierte Inventarisierung und Service-Management für Teams, die Geräte, Assets, Standorte, Beschaffung und Supportvorgänge nachvollziehbar verwalten.

![Inventory Pro Dashboard](docs/images/inventory-pro-dashboard.png)

> Die Abbildung zeigt eine isolierte Demo-Instanz mit synthetischen Daten. Sie enthält keine Daten einer produktiven Installation.

## Was Inventory Pro verbindet

- **Inventar und Lifecycle:** Geräte, Asset-Einträge, Kategorien, Standorte, Zuweisungen, Komponenten, Garantie- und Beschaffungsdaten.
- **Service Desk:** Tickets mit SLA, Prioritäten, Anhängen, Watchern, Kommentaren, Aktivitäten und nachvollziehbaren Statuswechseln.
- **Wissensgestützte Bearbeitung:** Direkt im Ticket erscheinen passende Wissensartikel und vergleichbare, bereits gelöste Fälle – immer innerhalb der jeweiligen Berechtigung.
- **Kontrollierte Änderungen:** Zu jedem Change wird ein Review geführt. Ein Change kann erst gelöst oder geschlossen werden, wenn das zugehörige Review abgenommen wurde.
- **Operative Übersicht:** Das Workflow-Cockpit macht fehlende Beziehungen, Service-Risiken, Lifecycle-Lücken und nächste Arbeitszüge sichtbar.
- **Standortbezogene Arbeit:** Ein Standort führt direkt zu der auf ihn gefilterten Geräteansicht.
- **Sichere Instanzverknüpfung:** Verknüpfte Inventory-Pro-Instanzen bleiben getrennt. Die Zielinstanz liefert nur die Daten, für die der angemeldete Benutzer dort berechtigt ist.

## Sicherheitsmodell

- Rollen und fein abgestufte Berechtigungen für Daten und Aktionen
- Passwort-Hashing, optionale TOTP-Zwei-Faktor-Authentifizierung und sichere Passwort-Resets
- Auditierbare Ticket- und Änderungsverläufe
- Verschlüsselte, serverseitige Verknüpfungsgeheimnisse; keine Zugangsdaten im Browser speichern
- Zwei explizite Verbindungsarten für andere Instanzen:
  - **Internet:** ausschließlich HTTPS mit geprüfter Zertifikatskette; private und lokale Zielnetze werden abgewiesen.
  - **Lokales Netzwerk:** ausschließlich private LAN-Adressen; öffentliche, Loopback- und Metadaten-Ziele werden abgewiesen.
- Release- und Update-Metadaten enthalten keine Inventar- oder Kundendaten.

## Entwicklung

Voraussetzung: Python 3.12 oder neuer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.lock
python -m playwright install firefox
python -m pytest
python app.py
```

Danach ist die Anwendung standardmäßig unter `http://localhost:5000` verfügbar. Ohne `APP_SECRET_KEY` erzeugt der Entwicklungsmodus einen sichtbaren, nicht-persistenten Schlüssel. Das ist ausdrücklich kein Produktionsmodus.

## Produktionsbetrieb

Setze mindestens `INVENTORY_ENV=production` und einen persistenten `APP_SECRET_KEY`; ohne ihn startet der Prozess nicht. Erzeuge einen geeigneten Schlüssel beispielsweise mit `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Nutze Gunicorn oder den Docker-Container hinter einem TLS-terminierenden Reverse Proxy. Lege die öffentliche Origin mit `INVENTORY_PUBLIC_ORIGIN` fest. Werden `X-Forwarded-*`-Header verwendet, müssen die Proxy-IP-Netze in `INVENTORY_TRUSTED_PROXY_NETWORKS` stehen; direkt eingehende Forwarded-Header werden ignoriert. Setze Secure-Cookies bei TLS mit `INVENTORY_SECURE_COOKIES=1`.

Die persistenten Datenpfade sind die Datenbank (`INVENTORY_DATABASE_PATH`), Uploads (`INVENTORY_UPLOADS_DIR`) und Instanzdateien (`INVENTORY_INSTANCE_PATH`). Sichere alle drei auf dauerhaftem Speicher mit restriktiven Dateirechten.

| Variable | Zweck |
| --- | --- |
| `APP_SECRET_KEY` | Persistenter Schlüssel für signierte Flask-Sitzungen; in Produktion zwingend |
| `INVENTORY_ENV` | `development`, `test` oder `production` |
| `INVENTORY_DATABASE_PATH` | SQLite-Datenbankpfad |
| `INVENTORY_UPLOADS_DIR` | Persistenter Uploadspeicher |
| `INVENTORY_INSTANCE_PATH` | Laufzeitkonfiguration, einmalige Admin-Credentials und Update-Policy |
| `INVENTORY_LINKS_ENCRYPTION_KEY` | Primärer Fernet-Schlüssel für neue Inventory-Link-Secrets |
| `INVENTORY_LINKS_ENCRYPTION_KEYS` | Kommagetrennte Rotation-Keyring-Liste, primärer Schlüssel zuerst |
| `BACKUP_ENCRYPTION_KEY` | Optionaler Fernet-Schlüssel für verschlüsselte Backups |
| `INVENTORY_SCHEDULER_ENABLED` | Nur für genau einen Worker auf `1` setzen |
| `INVENTORY_PUBLIC_ORIGIN` | Externe Origin hinter dem Reverse Proxy |
| `INVENTORY_TRUSTED_PROXY_NETWORKS` | CIDR-Liste vertrauenswürdiger Proxies |

Browser-Schreibzugriffe verwenden einen sitzungsgebundenen CSRF-Token. Die Oberfläche sendet ihn automatisch; eigene Clients rufen `GET /api/csrf-token` auf und senden den Wert mit `X-CSRF-Token`.

### Secrets, LDAP und MFA

Inventory-Link-Secrets werden nur mit einem gültigen Schlüssel gespeichert. Bereits vorhandene `plain:`-Werte werden blockiert, bis sie kontrolliert migriert sind:

```bash
INVENTORY_LINKS_ENCRYPTION_KEY='...' python scripts/migrate_inventory_link_secrets.py
```

Für Schlüsselrotation konfiguriere zuerst den neuen Schlüssel als ersten Eintrag von `INVENTORY_LINKS_ENCRYPTION_KEYS`, lasse `--reencrypt-all` laufen und entferne den alten Schlüssel erst nach einem erfolgreichen Backup und Funktionstest. LDAP-Bind-Daten werden in den Servereinstellungen verwaltet; TLS und ein eingeschränktes Bind-Konto sind empfohlen. TOTP-MFA und Recovery-Codes sind pro Benutzer verfügbar; erzwinge MFA erst nach einer getesteten Rollout-Phase.

## Betrieb mit Docker

```bash
docker compose up -d --build app
```

Die Standard-Compose-Datei nutzt ein Docker-Volume für `/data`. Bestehende Installationen mit einem Bind-Mount müssen diesen Mount in ihrer produktionsspezifischen Compose-Override-Datei ausdrücklich beibehalten, bevor sie auf Compose umgestellt werden. Compose setzt Produktionsmodus und startet den eingebetteten Scheduler nur für den App-Container. Verwende bei mehreren Web-Workern oder mehreren Instanzen einen dedizierten Scheduler-Owner und setze `INVENTORY_SCHEDULER_ENABLED=0` für alle anderen Prozesse.

## Signierte automatische Updates

Automatische Updates sind standardmäßig ausgeschaltet. Nach bewusstem Aktivieren in **Einstellungen → Server → Automatische Updates** prüft ein separater Updater nur den stabilen Release-Kanal. Er akzeptiert ausschließlich signierte Release-Manifeste und unveränderliche Container-Digests aus `ghcr.io/pondsec/inventorypro`.

Vor einem Update erstellt der Updater ein lokales SQLite-Backup und prüft dessen Integrität. Nach dem Rollout wartet er auf den Health-Check. Schlägt ein Schritt fehl, bleibt die laufende Version erhalten oder wird auf das vorherige Image zurückgesetzt. Die Instanzdaten verlassen dabei zu keinem Zeitpunkt den Server.

Der Updater wird bewusst separat und nur mit dem Compose-Profil `updater` gestartet:

```bash
docker compose --profile updater up -d
```

Der Sidecar benötigt Zugriff auf den lokalen Docker-Socket, damit er einen geprüften Rollout und gegebenenfalls ein Rollback ausführen kann. Dieser privilegierte Zugriff gehört ausschließlich auf einen abgesicherten Server und ist regelmäßig zu überprüfen.

## Backup, Restore und Upgrades

Ein vollständiger Wiederherstellungspunkt besteht aus Datenbank, Uploads und passenden Schlüsseln. Backups erstellen ein Prüfsummen-Manifest. Wiederherstellung erfolgt nur bei gestoppter Anwendung und legt vor dem Tausch einen Rollback-Snapshot an:

```bash
python scripts/restore_backup.py /secure/backups/inventory_backup_YYYYMMDD.db
```

Verschlüsselte und ZIP-Backups werden unterstützt, wenn der zugehörige `BACKUP_ENCRYPTION_KEY` verfügbar ist. Führe Wiederherstellungen zuerst isoliert aus und befolge [Backup and restore](docs/operations/backup-and-restore.md).

Beim Start führt die Anwendung versionierte SQL-Migrationen aus `migrations/` aus und prüft ihre Prüfsummen. Vor jedem Upgrade müssen ein getestetes Backup und die Migrationshinweise der Release Notes vorliegen. Der Updater nutzt nur signierte, unveränderliche Image-Digests und führt bei einem fehlgeschlagenen Health Check ein Image-Rollback aus.

## Qualitätssicherung

```bash
python -m pytest --cov=app --cov=inventorypro --cov-report=term-missing
```

Die Tests decken unter anderem Rollen- und Sicherheitsgrenzen, Ticket- und Review-Workflows, Wissenskontext, Standortfilter, mobile Bedienung, sichere Instanzverknüpfungen und den Update-Mechanismus ab.

## Skalierungsgrenzen

SQLite bleibt für kleine bis mittlere, einzelne Installationen unterstützt. Es eignet sich nicht als Mehrknoten-Datenbank und konkurrierende Schreiblast bleibt begrenzt. In-Memory-Ratenlimits und Inventory-Link-Login-Caches sind pro Prozess; eine Mehrworker- oder Multi-Node-Installation benötigt vor dem produktiven Einsatz eine gemeinsame Cache-/Scheduler-Strategie. Hintergrundjobs sind nur für einen ausdrücklich bestimmten Scheduler-Worker aktiviert.

## Releases

Ein erfolgreicher CI-Lauf für `main` startet die Release-Pipeline. Sie baut ein unveränderliches GHCR-Image, erstellt ein Ed25519-signiertes Update-Manifest und veröffentlicht ein GitHub Release inklusive Deployment-Archiv. Die Version stammt aus `VERSION`; der private Signaturschlüssel liegt ausschließlich als GitHub-Secret `INVENTORY_UPDATE_SIGNING_KEY` vor. Details stehen in `RELEASE.md`.

## Lizenz und Kontakt

Inventory Pro steht unter der [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.de.html). Für eine kommerzielle Nutzung ohne Offenlegungspflicht kann eine separate Lizenz vereinbart werden.

PondSec · [joshua@pondsec.com](mailto:joshua@pondsec.com)
Stand: Juli 2026
