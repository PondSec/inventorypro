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
Signaturprüfung noch Wartungsfenster. Ein Release wird erst nach Abnahme beider Images/Feeds freigegeben.
Produktionsinstanzen werden nicht direkt durch Tests verändert.

## Tatsächlich geprüft

Automatischer Kompatibilitätstest lädt den echten alten Validator aus `900b489`:
Er akzeptiert das Legacy-Manifest; der neue Validator akzeptiert das GitLab-Manifest.
Manipulierte Signaturen und unpassende Signierschlüssel werden abgelehnt.
SQLite-Rollbacktest prüft Wiederherstellung nach einer simulierten Schemamigration.
Die tatsächlichen 0.2.0-Artefakte wurden mit dem bestehenden Actions-Schlüssel
signiert und mit dem ausgelieferten Public-Key geprüft. GitLab-Registry, öffentliche
Paketdownloads und vollständiger Linux-Upgrade-/Rollbackablauf sind erfolgreich
geprüft; Einzelheiten im [Qualitätsbericht](QUALITY.md).

## Veröffentlichungsablauf

Version in `.release/request.json` auf dev bewusst erhöhen, relevante Tests ausführen,
committen und nach GitLab dev pushen. Danach denselben dev-Stand ohne Force-Push nach
GitHub dev spiegeln. Der Actions-Workflow akzeptiert ausschließlich einen in GitLab
dev enthaltenen Quellcommit, führt die Regression aus, baut beide Plattformen und
erzeugt signierte Entwurfsartefakte mit dem bisherigen Schlüssel. Normale Pushes
ohne geänderten Releaseauftrag veröffentlichen nichts; main bleibt unverändert.

Cloudflare Bot Fight blockiert GitHub-Registryuploads. Deshalb das vollständige
GHCR-OCI-Image mit `skopeo copy --all --preserve-digests` über den geprüften internen
Serverzugang nach GitLab kopieren. Danach anonymen externen Digestabruf prüfen,
GitLab-Pakete über `scripts/upload_release_package.py` mit projektbezogener
Berechtigung hochladen und ihre öffentlichen Downloads prüfen. Beide Entwurfs-
Manifeste und Installations-/Upgrade-/Rollbacktests müssen vor Veröffentlichung
bestanden sein. GitLab-Release mit permanenten Assetpfaden erstellen, dann den
GitHub-Entwurf mit Legacy-Manifest als `update-manifest.json` freigeben. Beide
aktiven öffentlichen Feeds danach mit dem jeweiligen echten Validator prüfen.

Eine alleinige dev-Quelländerung veröffentlicht bewusst noch kein Update. Jeder
freigegebene Release muss diesen Kompatibilitätsspiegel erhalten. Projektbezogene
Publish-Credentials sind kurzlebig und werden nach Veröffentlichung widerrufen.

## Bereits nicht startende Installationen

Das neue App-Image enthält inventorypro und alle gesperrten Runtimeabhängigkeiten.
Ein laufender alter Updater kann damit auch eine ausgefallene App ersetzen. Wenn
Compose wegen `depends_on: service_healthy` den Sidecar beim ersten Start nie
gestartet hat, fehlt ein laufender Prozess, der das Update holen könnte. Dieser
Fall benötigt einen einmaligen lokalen Eingriff, keine Neuinstallation oder
Löschung vorhandener Daten. Dasselbe gilt für Installationen ohne Sidecar.
