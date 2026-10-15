# Releaseabnahme 0.3.0

Quellstand: `7a939d2c1cfcfadefcffe1bcea1a3553f6637c66`, 15.10.2026.
Die Prüfungen verwenden isolierte synthetische Instanzen und persistente Docker-Testvolumes.

## Öffentliche Freigabe

Am 15.10.2026 um 20:41 UTC als Stable veröffentlicht:
[GitLab v0.3.0](https://gitlab.pondsec.com/PondSec/inventorypro/-/releases/v0.3.0)
und [GitHub-Kompatibilitätsrelease](https://github.com/PondSec/inventorypro/releases/tag/v0.3.0).
Regulärer GitLab-Merge [!193](https://gitlab.pondsec.com/PondSec/inventorypro/-/merge_requests/193),
Mergecommit `a9892e963ad91f4767ac7f810fd21b752ae03999`; main anschließend ohne Force-Push nach GitHub gespiegelt.

Beide aktiven Latest-Endpunkte wurden mit dem tatsächlichen alten bzw. aktuellen
Downloader und Validator abgerufen. Signaturen, Version 0.3.0, Digestgleichheit und
Übereinstimmung mit den abgenommenen Artefakten bestanden. Konfigurierte automatische
Updates beachten weiterhin Aktivierung, Intervall und Wartungsfenster.

Die ausdrücklich autorisierte Betreiberinstanz wurde anschließend durch ihren
Updater sofort aktualisiert. App gesund, Version 0.3.0, sämtliche ursprünglichen
Geschäftszeilen und Uploads unverändert erhalten; automatische Assetübernahme und
SQLite-/Fremdschlüsselintegrität geprüft. Dies war ein gesondertes Betriebsupdate,
keine Verwendung der Instanz als Testdatenquelle. Die ursprüngliche Updatepolicy blieb erhalten.

## Regression und Darstellung

- [GitLab-Pipeline 113](https://gitlab.pondsec.com/PondSec/inventorypro/-/pipelines/113): erfolgreich, Python 3.12, Chromium und Firefox; 576 Tests bestanden, zwei macOS-spezifische Pixeltests unter Linux ausdrücklich übersprungen, keine Fehler. Authentifizierter synthetischer Registryupload und anonymer Digestdownload bestanden.
- [Release-Pipeline 38800559476](https://github.com/PondSec/inventorypro/actions/runs/38800559476): erfolgreich; 576 Tests und 46 Unterfälle bestanden, zwei Plattform-Skips, zwei bekannte ldap3-Warnungen. JUnit: 624 Fälle, null Fehler/Fehlschläge. Anschließend Multiarch-Build und Signierung mit dem bereits ausgelieferten Originalschlüssel.
- macOS: vollständiger früherer Lauf mit 573 Tests und 46 Unterfällen sowie gezielte Prüfungen der letzten Korrekturen. Beide tatsächlichen Chromium-/Firefox-Pixelvergleiche gegen acht freigegebene Baselines bestanden.
- 360 finale Seitenansichten plus Anmeldung und 60 ergänzende Themeansichten, fünf Bildschirmbreiten und beide Themes: keine JS-Fehler, Seitenüberläufe oder unerwarteten HTTP-Fehler. Testbestand: 1.020 Assets, darunter 400 lizenzierte Katalogbilder und 620 Fallbacks.

## Unveränderliche Images und Signaturen

Gemeinsamer OCI-Index für `linux/amd64` und `linux/arm64`:

`sha256:1eec3e4992902a744c1230230236f083a549cc46186123b223ad0311175ca12a`

Das vollständige Image einschließlich Provenienzmanifesten wurde mit erhaltenen Digests von GHCR nach GitLab kopiert. Tatsächlicher anonymer Abruf bei GitLab und Vergleich beider Plattformen bestanden. Der echte alte Validator aus `900b489` akzeptiert das Legacy-Manifest; der aktuelle Validator akzeptiert das GitLab-Manifest. Beide verwenden denselben bereits ausgelieferten öffentlichen Schlüssel und binden dieselbe Version an denselben Digest.

Die öffentlich vorbereiteten GitLab-Paketdownloads wurden vollständig erneut heruntergeladen und mit den signierten Artefakten verglichen:

- Modernes Manifest SHA-256: `0307c64edc9e48a3944bec4b5a75a024d2a2678854e71da45dab4b51ae63dd07`.
- Quellarchiv SHA-256: `2cf5fbdc1ce8bc76ecc5bf7b72c2ef386b0853246b4868cd30429e103b0dad4a`.

## Tatsächliche Installation und Übernahme des finalen Images

- Frische Composeinstallation auf Linux AMD64 und macOS/Docker ARM64: vollständiges Pythonpaket einschließlich Backups, Katalog und Migrationen, Assetmodus, Starterfoto, SQLiteintegrität, private zufällige Erstzugangsdaten und erzwungener Passwortwechsel bestanden. Secret bleibt nach Neustart unverändert; HTTP-Login funktioniert.
- Veröffentlichtes 0.2.0 → signiertes 0.3.0: 20 Geräte, zwei bestehende Sets, Mengen, Zuordnungsnotizen, dynamische Eigenschaften, Benutzer/Rollen, Tickets, Uploads, Policy und Secret erhalten. Neustart erzeugt keine Duplikate. Produktfoto und paginierte Asset-API über HTTP geprüft; Ticket mit Roadmapverweis erfolgreich gelöscht.
- Wiederherstellung der Vorabsicherung und Start des tatsächlichen alten 0.2.0-Images: sämtliche ursprünglichen Geschäftszeilen erhalten, SQLite integer.
- Der echte alte Updatercode hat das signierte GHCR-Image installiert, Migrationen ausgeführt und Anhänge/Felder erhalten. Nur die defekte historische Testbasis erhielt vorab das fehlende Runtimepaket; diese Hilfsmounts wurden vor der Aktualisierung entfernt. Das Release liefert sein Paket selbst aus.
- Der neue Updater bezog das tatsächliche GitLab-Image. Ein absichtlich negativer Healthcheck führte zur Wiederherstellung der ursprünglichen Datenbank einschließlich Schema und zum gesunden vorherigen Image.
- Wiederherstellung zusätzlich innerhalb eines echten Docker-Named-Volumes mit anschließender gesunder App geprüft.

Wiederholbare Programme: `scripts/check_release_install.py`, `scripts/check_asset_image_upgrade.py`, `scripts/check_release_upgrade.py`, `scripts/check_release_volume_rollback.py`.

## Grenzen

Keine Windows-/Safari-Installationsabnahme und keine vollständige WCAG-Zertifizierung. Linux-Pixelbaselines sind nicht freigegeben; die funktionalen Browser-, Theme- und Geometrieprüfungen laufen dort. Gemischte Host-/Guest-SQLitezugriffe auf macOS-Bindmounts sind nicht als produktive Datenhaltung freigegeben. Ein nicht eingerichteter Updater startet nicht allein durch das Update. Bestehende Updateabschaltungen und Wartungsfenster bleiben wirksam. Alte Sidecars erhalten die Version weiterhin über den dauerhaft notwendigen GitHub-/GHCR-Spiegel und werden nicht durch die App ausgetauscht.
