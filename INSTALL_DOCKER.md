# Inventory Pro mit Docker installieren

Diese Anleitung installiert Inventory Pro aus GitHub Container Registry. Das Image enthaelt keine produktive Datenbank, keine Uploads und keine Passwoerter.

## Voraussetzungen

- Docker
- Docker Compose Plugin (`docker compose`)
- Freier TCP-Port, standardmaessig `5000`

```bash
docker --version
docker compose version
```

## 1. Installationsordner erstellen

```bash
sudo mkdir -p /opt/inventorypro
cd /opt/inventorypro
```

Legen Sie in diesem Ordner die Dateien `docker-compose.ghcr.yml` und `.env` an. Sie finden `docker-compose.ghcr.yml` und `.env.example` im GitHub Release.

```bash
cp .env.example .env
```

## 2. Secrets setzen

Bearbeiten Sie `.env` und setzen Sie mindestens:

- `APP_SECRET_KEY`
- `INVENTORY_INITIAL_ADMIN_USERNAME`
- `INVENTORY_INITIAL_ADMIN_PASSWORD`
- `BACKUP_ENCRYPTION_KEY`, falls verschluesselte Backups genutzt werden
- `INVENTORY_LINKS_ENCRYPTION_KEY`, falls Inventory Links mit Secrets genutzt werden

`APP_SECRET_KEY` erzeugen:

```bash
openssl rand -hex 32
```

Fernet-Schluessel erzeugen:

```bash
docker run --rm --entrypoint python ghcr.io/pondsec/inventorypro:v0.1.3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Nutzen Sie fuer `BACKUP_ENCRYPTION_KEY` und `INVENTORY_LINKS_ENCRYPTION_KEY` unterschiedliche Werte und bewahren Sie diese sicher auf.

## 3. Image laden und starten

```bash
docker pull ghcr.io/pondsec/inventorypro:v0.1.3
docker compose -f docker-compose.ghcr.yml up -d
docker compose -f docker-compose.ghcr.yml ps
```

Die Anwendung ist danach unter `http://SERVER-IP:5000` erreichbar. Falls `INVENTORY_HTTP_PORT` geaendert wurde, verwenden Sie den dort gesetzten Port.

## 4. Erstlogin

Melden Sie sich mit den in `.env` gesetzten Werten an:

- Benutzer: `INVENTORY_INITIAL_ADMIN_USERNAME`
- Passwort: `INVENTORY_INITIAL_ADMIN_PASSWORD`

Aendern Sie das Startpasswort nach dem ersten Login.

Der initiale Admin wird nur beim ersten Start einer leeren Datenbank erzeugt. Wenn das Volume bereits existiert, aendern Werte in `.env` keinen bestehenden Benutzer.

## 5. Datenhaltung

Persistente Daten liegen im Docker-Volume `inventorypro-data`.

- Datenbank: `/data/inventory.db`
- Uploads: `/data/uploads`
- Laufzeitkonfiguration: `/data/instance`

## 6. Betrieb

Logs:

```bash
docker compose -f docker-compose.ghcr.yml logs -f inventorypro
```

Neustart:

```bash
docker compose -f docker-compose.ghcr.yml restart inventorypro
```

Stoppen:

```bash
docker compose -f docker-compose.ghcr.yml down
```

Alle Daten entfernen:

```bash
docker compose -f docker-compose.ghcr.yml down -v
```

`down -v` loescht das Volume und damit Datenbank, Uploads und Laufzeitkonfiguration.

## 7. Backup vor Updates

```bash
docker compose -f docker-compose.ghcr.yml stop inventorypro
docker run --rm -v inventorypro-data:/data -v "$PWD:/backup" busybox tar czf /backup/inventorypro-data-backup.tgz -C /data .
docker compose -f docker-compose.ghcr.yml start inventorypro
```

## 8. Update

```bash
docker pull ghcr.io/pondsec/inventorypro:v0.1.3
docker compose -f docker-compose.ghcr.yml up -d
```

Bei einem neuen Release setzen Sie `INVENTORYPRO_VERSION` in `.env` auf den neuen Tag.
