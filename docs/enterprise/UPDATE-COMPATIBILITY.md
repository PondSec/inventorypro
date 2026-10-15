# GitLab-Updates ohne Neuinstallation vorhandener Instanzen

## Vertrag mit bereits ausgelieferten Updatern

Der Updater aus `900b489` liest ein signiertes Schema-1-Manifest unter
`https://github.com/PondSec/inventorypro/releases/latest/download/update-manifest.json`.
Er erlaubt ausschließlich `ghcr.io/pondsec/inventorypro@sha256:…` und prüft mit dem
bereits ausgelieferten Ed25519-Public-Key. Er tauscht ausschließlich den App-Service.
Weder zusätzliche JSON-Felder noch ein neues App-Image können seinen laufenden
Pythonprozess oder dessen Manifest-URL ändern. Das Image benötigt einen RepoDigest;
rein lokal gebaute Installationen unterstützt bereits dieser alte Updater nicht.

**Ohne Arbeit beim Anwender:** GitLab ist die führende Quell-/Releaseinstanz.
Jeder freigegebene Release erhält zusätzlich ein signiertes kompatibles Manifest
am bisherigen GitHub-Endpunkt und ein identisches App-Image im GHCR-Repository.
Dieser Spiegel muss für alte Sidecars dauerhaft weitergeführt werden. Kein
Anwender muss dafür neu installieren oder seinen Sidecar manuell ersetzen.
Neue Sidecars fragen das Manifest direkt bei GitLab ab. Die behauptete automatische
Selbstmigration alter Sidecars wäre technisch falsch und wird nicht versprochen.

## Vorbereiten und prüfen

`scripts/prepare_update_bridge.py` erzeugt beide signierten Manifeste aus derselben
Version. Es prüft den Signierschlüssel gegen den ausgelieferten Public-Key; es
veröffentlicht und installiert nichts. Der private Schlüssel wird ausschließlich
über die geschützte Variable INVENTORY_UPDATE_SIGNING_KEY übergeben.

```
python scripts/prepare_update_bridge.py --version 1.2.3 \
  --gitlab-image gitlab.pondsec.com/pondsec/inventorypro@sha256:<digest> \
  --legacy-image ghcr.io/pondsec/inventorypro@sha256:<digest> \
  --output-dir release-artifacts
```

Die tatsächliche GitLab-Registry muss vor der ersten Veröffentlichung gegen die
Serverkonfiguration geprüft werden; eine abweichende Registry benötigt dieselbe
explizite Freigabe im Updater und im Freigabeprozess. Kein Registry-/Releasebetrieb
wurde allein durch eine erfolgreiche Git-Übertragung als funktionsfähig gewertet.

GitLab: `update-manifest.json` als permanenter Release-Assetpfad
`/update-manifest.json` für den API-Permalink
`/api/v4/projects/PondSec%2Finventorypro/releases/permalink/latest/downloads/update-manifest.json`.
Das Asset selbst muss unter einem GitLab-API-Paketdownload liegen, damit keine
Weiterleitung auf eine durch Browserprüfungen blockierte Webroute erfolgt.
GitHub: `legacy-update-manifest.json` unter dem Assetnamen `update-manifest.json`
veröffentlichen. Beide Images müssen denselben getesteten Quellstand enthalten.
Keine GitLab-Redirects am alten Endpunkt einsetzen: alte Hostfreigaben lehnen sie ab.
Der bisherige private Signierschlüssel und Veröffentlichungsrechte für GitHub/GHCR
sind operative Voraussetzungen; sie werden nicht neu erfunden oder umgangen.

## Sicherheit und Verhalten

Signatur, HTTPS-Hostfreigabe, Digestbindung und Stable-Kanal bleiben verpflichtend.
Das vorherige GHCR-Image wird vom neuen Updater als Rollbackziel akzeptiert, nicht
als beliebige neue Quelle. Der neue Ablauf hält die Anwendung vor Migrationen an,
sichert die ruhende SQLite-Datenbank und stellt bei fehlgeschlagenem Healthcheck
auch deren Schema und Daten wieder her, bevor das vorherige Image gestartet wird.

Der Schalter `updates.autoUpdateEnabled` liegt in der persistenten Updatepolicy.
Bei `false` findet keine Release-Abfrage statt. Aktivierung ersetzt weder
Signaturprüfung noch Wartungsfenster. Keine Releaseveröffentlichung oder
Produktionsinstallation wurde während dieser Entwicklungsarbeit ausgelöst.

## Tatsächlich geprüft

Automatischer Kompatibilitätstest lädt den echten alten Validator aus `900b489`:
Er akzeptiert das Legacy-Manifest; der neue Validator akzeptiert das GitLab-Manifest.
Manipulierte Signaturen und unpassende Signierschlüssel werden abgelehnt.
SQLite-Rollbacktest prüft Wiederherstellung nach einer simulierten Schemamigration.
Öffentliche Releaseendpunkte und produktive Signierschlüssel sind noch nicht geprüft.
