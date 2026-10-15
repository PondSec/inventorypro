# Inventory Pro

Enterprise-Inventarisierung und Service-Management für Teams, die Assets, Standorte, Beschaffung und Supportvorgänge in einem nachvollziehbaren System steuern wollen.

![Inventory Pro Dashboard](docs/images/inventory-pro-dashboard.png)

> Die Abbildung zeigt eine isolierte Demo-Instanz mit synthetischen Daten. Sie enthält keine Daten einer produktiven Installation.

## Was Inventory Pro verbindet

- **Inventar und Lebenszyklus:** Ein gemeinsamer Assetbestand mit Asset-Kategorien, Standorten, Zuweisungen, verschachtelten Assets und Mengen sowie Garantie- und Beschaffungsdaten. Bestehende Geräte werden beim Update mit privater Sicherung übernommen.
- **Service Desk:** Tickets mit SLA, Prioritäten, Anhängen, Watchern, Kommentaren, Aktivitäten und nachvollziehbaren Statuswechseln.
- **Wissensgestützte Bearbeitung:** Direkt im Ticket erscheinen passende Wissensartikel und vergleichbare, bereits gelöste Fälle – immer innerhalb der jeweiligen Berechtigung.
- **Kontrollierte Änderungen:** Zu jedem Change wird ein Review geführt. Ein Change kann erst gelöst oder geschlossen werden, wenn das zugehörige Review abgenommen wurde.
- **Operative Übersicht:** Der Bestand zeigt fehlende Angaben, Zuweisungen und anstehende Wartungen mit direkt gefilterten Arbeitslisten.
- **Standortbezogene Arbeit:** Ein Standort führt direkt zu der auf ihn gefilterten Assetansicht.
- **Sichere Instanzverknüpfung:** Verknüpfte Inventory-Pro-Instanzen bleiben getrennt. Die Zielinstanz liefert nur die Daten, für die der angemeldete Benutzer dort berechtigt ist.

## Produktbilder

Der [Produktkatalog](docs/product-images.md) ordnet geprüfte Modellbilder zu, enthält ein lizenziertes MacBook-Air-M4-Starterbild und kann nach Aktivierung passende Bilder aus Wikidata/Wikimedia Commons lokal zwischenspeichern. Eigene Fotos werden serverseitig gespeichert und sind auf allen berechtigten Clients sichtbar. Ohne passenden Treffer erscheinen einheitliche Typ-Symbole.

## Sicherheitsmodell

- Rollen und fein abgestufte Berechtigungen für Daten und Aktionen
- Passwort-Hashing, optionale TOTP-Zwei-Faktor-Authentifizierung und sichere Passwort-Resets
- Auditierbare Ticket- und Änderungsverläufe
- Verschlüsselte, serverseitige Verknüpfungsgeheimnisse; keine Zugangsdaten im Browser speichern
- Zwei explizite Verbindungsarten für andere Instanzen:
  - **Internet:** ausschließlich HTTPS mit geprüfter Zertifikatskette; private und lokale Zielnetze werden abgewiesen.
  - **Lokales Netzwerk:** ausschließlich private LAN-Adressen; öffentliche, Loopback- und Metadaten-Ziele werden abgewiesen.
- Release- und Update-Metadaten enthalten keine Inventar- oder Kundendaten.

## Schnellstart für Entwicklung

Voraussetzung: Python 3.12 oder neuer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Danach ist die Anwendung standardmäßig unter `http://localhost:5000` verfügbar. Für reale Umgebungen müssen insbesondere `APP_SECRET_KEY`, der Datenpfad und die Uploads als geschützte Infrastruktur-Konfiguration gesetzt werden – keine Geheimnisse in Git ablegen.

## Betrieb mit Docker

Der [Compose-Schnellstart](docs/installation.md) erzeugt sichere persistente Secrets und zufällige Erstzugangsdaten ohne Standardpasswort.

```bash
docker compose up -d --build app
```

Die Standard-Compose-Datei nutzt ein Docker-Volume für `/data`. Bestehende Installationen mit einem Bind-Mount müssen diesen Mount in ihrer produktionsspezifischen Compose-Override-Datei ausdrücklich beibehalten, bevor sie auf Compose umgestellt werden. So bleibt die vorhandene Datenbank unangetastet.

Wichtige Konfigurationen:

| Variable | Zweck |
| --- | --- |
| `APP_SECRET_KEY` | Zufälliger, persistenter Flask-Session-Schlüssel |
| `INVENTORY_DATABASE_PATH` | Pfad zur SQLite-Datenbank innerhalb der Instanz |
| `INVENTORY_UPLOADS_DIR` | Persistenter Speicher für Uploads |
| `INVENTORY_LINKS_ENCRYPTION_KEY` | Schlüssel zum Schutz von Instanzverknüpfungen |
| `INVENTORY_UPDATER_ENABLED` | Schaltet die Update-Einstellungen frei; Standard ist `0` |

## Signierte automatische Updates

Automatische Updates sind standardmäßig ausgeschaltet. Nach bewusstem Aktivieren in **Einstellungen → Server → Updates → Automatische Updates** prüft ein separater Updater nur den stabilen Release-Kanal. Neue Sidecars lesen signierte Release-Manifeste bei GitLab und prüfen unveränderliche Container-Digests. Vorhandene Sidecars bleiben über einen kompatiblen GitHub/GHCR-Spiegel versorgt; siehe [Updatekompatibilität](docs/enterprise/UPDATE-COMPATIBILITY.md).

Vor einem Update erstellt der Updater ein lokales SQLite-Backup und prüft dessen Integrität. Nach dem Rollout wartet er auf den Health-Check. Schlägt ein Schritt fehl, bleibt die laufende Version erhalten oder wird auf das vorherige Image zurückgesetzt. Die Instanzdaten verlassen dabei zu keinem Zeitpunkt den Server.

Der Updater wird bewusst separat und nur mit dem Compose-Profil `updater` gestartet:

```bash
docker compose --profile updater up -d
```

Der Sidecar benötigt Zugriff auf den lokalen Docker-Socket, damit er einen geprüften Rollout und gegebenenfalls ein Rollback ausführen kann. Dieser privilegierte Zugriff gehört ausschließlich auf einen abgesicherten Server und ist regelmäßig zu überprüfen.

## Qualitätssicherung

```bash
python3 -m pip install -r requirements-dev.lock
INVENTORY_ENV=test INVENTORY_SCHEDULER_ENABLED=0 python3 -m pytest -q
```

Die Tests decken unter anderem Rollen- und Sicherheitsgrenzen, Ticket- und Review-Workflows, Wissenskontext, Standortfilter, mobile Bedienung, sichere Instanzverknüpfungen und den Update-Mechanismus ab.

## Releases

Ein ausdrücklich versionierter Releaseauftrag auf `dev` startet die vorhandene Vorbereitungspipeline. Sie prüft den Quellstand gegen GitLab, führt die Regression aus, baut das Multiarch-Image und signiert beide Update-Manifeste mit dem bereits ausgelieferten Schlüssel. Zunächst entsteht ein Entwurf. Nach Image-, Upgrade- und Rollbackabnahme werden GitLab-Stable und der kompatible GitHub-Feed freigegeben. Gewöhnliche Commits und ein Merge nach `main` veröffentlichen kein ungeprüftes Update. Der private Signaturschlüssel bleibt ausschließlich im bestehenden Actions-Secret `INVENTORY_UPDATE_SIGNING_KEY`.

## Lizenz und Kontakt

Inventory Pro steht unter der [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.de.html). Für eine kommerzielle Nutzung ohne Offenlegungspflicht kann eine separate Lizenz vereinbart werden.

PondSec · [joshua@pondsec.com](mailto:joshua@pondsec.com)
Stand: Oktober 2026

Die weitere Projekt- und Betriebsdokumentation steht im [Dokumentationsverzeichnis](docs/INDEX.md).
