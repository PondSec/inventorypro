# Inventory Pro mit Docker einrichten

Diese Anleitung richtet die Anwendung ohne mitgelieferte Alt-Daten ein. Datenbank, Uploads und Laufzeitkonfiguration liegen in einem Docker-Volume und werden beim ersten Start frisch erzeugt.

## Voraussetzungen

- Docker
- Docker Compose Plugin (`docker compose`)

## 1. Projekt holen

```bash
git clone https://github.com/PondSec/inventorypro.git
cd inventorypro
```

## 2. Umgebung vorbereiten

```bash
cp .env.example .env
```

Passe mindestens diese Werte in `.env` an:

- `APP_SECRET_KEY`: lange zufällige Zeichenfolge für Sessions
- `INVENTORY_INITIAL_ADMIN_PASSWORD`: dein Startpasswort für den ersten Admin

Wenn `INVENTORY_INITIAL_ADMIN_USERNAME` oder `INVENTORY_INITIAL_ADMIN_PASSWORD` leer bleiben, erzeugt Inventory Pro beim ersten Start automatisch ein Admin-Konto und schreibt die Zugangsdaten in die Container-Logs.

## 3. Container bauen und starten

```bash
docker compose up -d --build
```

Danach ist die Anwendung unter [http://localhost:5000](http://localhost:5000) erreichbar.

## 4. Beim ersten Login anmelden

Wenn du Admin-Zugangsdaten in `.env` gesetzt hast, kannst du dich direkt damit anmelden.

Wenn du keine Zugangsdaten gesetzt hast, lies die automatisch erzeugten Daten aus den Logs:

```bash
docker compose logs app | grep -A3 "ADMIN-KONTO ERSTELLT"
```

## 5. Datenhaltung

Die persistenten Daten liegen im Docker-Volume `inventorypro-data`.

- Datenbank: `/data/inventory.db`
- Uploads: `/data/uploads`
- Laufzeitkonfiguration: `/data/instance/runtime_config.json`

Im Git-Repo und im Docker-Build ist keine bestehende `inventory.db` mehr enthalten.

## Nützliche Befehle

Neu bauen nach Updates:

```bash
git pull
docker compose up -d --build
```

Logs ansehen:

```bash
docker compose logs -f app
```

Container stoppen:

```bash
docker compose down
```

Komplett neu starten und alle Daten verwerfen:

```bash
docker compose down -v
```

## Direktes Docker-Image ohne Compose

```bash
docker build -t inventorypro:latest .
docker run -d \
  --name inventorypro \
  -p 5000:5000 \
  -e APP_SECRET_KEY="change-this-long-random-secret" \
  -e INVENTORY_INITIAL_ADMIN_USERNAME="admin" \
  -e INVENTORY_INITIAL_ADMIN_PASSWORD="change-me-now" \
  -v inventorypro-data:/data \
  inventorypro:latest
```

## Optional: Ollama für PondSec AI anbinden

Wenn Ollama auf dem Host läuft, kannst du zusätzlich diese Variablen setzen:

```bash
PONDSEC_AI_LLM_PROVIDER=ollama
PONDSEC_AI_OLLAMA_URL=http://host.docker.internal:11434
PONDSEC_AI_OLLAMA_MODEL=mistral
```

`host.docker.internal` ist im Compose-Setup bereits hinterlegt.
