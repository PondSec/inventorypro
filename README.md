# Inventory Pro

[Deutsch](#deutsch) · [English](#english) · [Dokumentation / Documentation](docs/INDEX.md)

![Inventory Pro](docs/images/inventory-pro-dashboard.png)

Die Abbildung zeigt ausschließlich synthetische Daten. / The screenshot contains synthetic data only.

## Deutsch

Inventory Pro verwaltet Assets, Standorte, enthaltene Komponenten, Beschaffung und Supporttickets. Dazu gehören Zuweisungen, Wartung, eine Wissensbasis, Roadmaps und Auswertungen. Rollen begrenzen den Zugriff auf Daten und Aktionen.

### Installation mit Docker

1. Docker Engine mit Compose installieren oder Docker Desktop starten. Git muss verfügbar sein.
2. Repository herunterladen:

   ```sh
   git clone --branch main https://gitlab.pondsec.com/PondSec/inventorypro.git
   cd inventorypro
   ```

3. Anwendung bauen und starten:

   ```sh
   docker compose up --detach --build --wait app
   ```

4. Einmalige Zugangsdaten lokal auslesen:

   ```sh
   docker compose exec app cat /data/instance/initial_admin_credentials.txt
   ```

5. [http://127.0.0.1:5000](http://127.0.0.1:5000) öffnen, anmelden und das Passwort ändern. Es gibt kein gemeinsames Standardpasswort.
6. Einen Standort und ein erstes Asset anlegen. Danach Rollen vergeben, Zwei-Faktor-Authentifizierung einrichten und eine Sicherung prüfen.

Die Anwendung ist zunächst nur lokal erreichbar. Für Netzwerkbetrieb HTTPS und die Bind-Adresse bewusst konfigurieren. Datenbank, Uploads und Instanzschlüssel liegen im persistenten Docker-Volume. Dieses Volume bei Updates behalten.

Optional prüft `python3 scripts/setup.py --start` Docker und freie Ports und erzeugt eine private `.env` mit persistenten Zufallsschlüsseln. Unter Windows kann `py scripts/setup.py --start` verwendet werden. [Installation, Sicherung und Betrieb](docs/de/installation.md).

### Bestehende Installationen

Keine Neuinstallation vornehmen. Konfigurierte alte Updater erhalten weiterhin signierte Updates über GitHub/GHCR; neue Updater verwenden GitLab. In **Einstellungen → Server → Updates** lassen sich automatische Updates ein- und ausschalten. Ohne laufenden Updater installiert der Schalter keinen Dienst. [Updateverfahren](docs/de/updates.md).

Produktbilder kommen aus einem lokalen Modellkatalog oder nach ausdrücklicher Aktivierung aus Wikidata/Wikimedia Commons. Eigene Fotos werden auf dem Server gespeichert. Ohne Treffer erscheint ein passendes Symbol. [Produktbilder](docs/de/product-images.md).

### Lizenz

© 2025–2026 Joshua Pond. Kostenlose Nutzung und Veränderung, auch intern in Unternehmen, sind erlaubt. Namensnennung bleibt Pflicht. Verkauf, kostenpflichtige Softwarezugänge und bezahlte SaaS-Angebote sind ohne schriftliche Erlaubnis untersagt. Maßgeblich sind [LICENSE](LICENSE) und [NOTICE](NOTICE). Die Community-Lizenz ist wegen des Verkaufsverbots keine OSI-anerkannte Open-Source-Lizenz. Frühere, unter AGPL veröffentlichte Versionen behalten ihre damaligen Rechte.

## English

Inventory Pro manages assets, locations, nested components, procurement and support tickets. It includes assignments, maintenance, a knowledge base, roadmaps and reports. Roles control access to records and actions.

### Docker installation

1. Install Docker Engine with Compose, or start Docker Desktop. Git is also required.
2. Download the repository:

   ```sh
   git clone --branch main https://gitlab.pondsec.com/PondSec/inventorypro.git
   cd inventorypro
   ```

3. Build and start the application:

   ```sh
   docker compose up --detach --build --wait app
   ```

4. Read the one-time credentials locally:

   ```sh
   docker compose exec app cat /data/instance/initial_admin_credentials.txt
   ```

5. Open [http://127.0.0.1:5000](http://127.0.0.1:5000), sign in and change the password. There is no shared default password.
6. Add a location and your first asset. Then assign roles, enable two-factor authentication and verify a backup.

The application initially accepts local connections only. Configure HTTPS and the bind address before enabling network access. The persistent Docker volume holds the database, uploads and instance keys. Retain this volume during updates.

The optional `python3 scripts/setup.py --start` helper checks Docker and ports and creates a private `.env` with persistent random keys. On Windows, use `py scripts/setup.py --start`. See [installation, backup and operation](docs/en/installation.md).

### Existing installations

Do not reinstall. Configured older updaters continue to receive signed updates through GitHub/GHCR; new updaters use GitLab. Automatic updates can be enabled or disabled under **Settings → Server → Updates**. The switch does not install a missing updater service. See [updates](docs/en/updates.md).

Product pictures use a local model catalog or, when explicitly enabled, Wikidata/Wikimedia Commons. Uploaded photos are stored on the server. A type icon appears when no image matches. See [product images](docs/en/product-images.md).

### License

© 2025–2026 Joshua Pond. Free use and modification, including internal business use, are permitted. Attribution is required. Sale, paid software access and paid SaaS require written permission. [LICENSE](LICENSE) and [NOTICE](NOTICE) govern use. The Community License is not an OSI-approved open-source license because it prohibits sale. Earlier AGPL releases retain their original license rights.
