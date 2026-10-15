# Health Module (Server Monitoring)

## Phase 1 — UX + Tech Spec

### A) Wichtigste Screens
- **Health Overview Dashboard**: Gesamtstatus, Summary Cards, letzte Events, offene Incidents.
- **Services/Units View**: Tabelle für Services/Units inkl. Status, Uptime, Restart/Exit, Aktionen.
- **Checks Catalog**: Alle Checks gruppiert (System/Network/Infra/Services/Custom) mit Enable/Disable.
- **Check Detail**: Konfiguration, letzte Runs, Metriken/Trends, Events-Timeline.
- **Incidents**: Offene/geschlossene Incidents, Ack/Mute, Ticket-Integration.
- **History/Trends**: 24h/7d Timeline + aggregierte Metriken (CPU/Mem/Disk).

### B) UI-Layout-Pattern
- **Page Header**: Titel + Overall-Status-Badge + Primary Action „Run now“.
- **Summary Cards**: 4–6 KPI-Cards oberhalb der Detailtabs.
- **Tabs**: Overview | Services | Checks | Incidents | History.
- **Sidepanel/Drawer**: Rechts für Details (Check-Detail, Incident-Info) ohne Überladung.
- **Tables**: Sticky Header, Row-Actions via Overflow Menu.

### C) Backend-Architektur
- **Check Interface**: Plugin-Registry (`HEALTH_CHECK_REGISTRY`) mit `register_health_check()`.
- **Scheduler/Jobs**: APScheduler Job alle 60s, führt fällige Checks aus.
- **DB Tables**:
  - `health_check_definitions`
  - `health_check_runs`
  - `health_check_results`
  - `health_events`
  - `health_incidents`
- **Statusmodell**: `OK/WARN/CRIT/UNKNOWN`, mit `severity`, `reason`, `observed_at`.
- **Retention**: Detaildaten 14 Tage (konfigurierbar über Konstante).

## Overview
Das Health-Modul überwacht Systemzustand, Services, Netzwerk- und Infrastrukturprüfungen. Checks laufen im Hintergrund (Scheduler) und werden im UI als Dashboard, Tabellen und Trends sichtbar.

## Permissions
- `health.view`: Dashboard & Leserechte.
- `health.manage`: Checks konfigurieren, Incidents ack/mute, Ticket erstellen.
- `health.run`: Checks manuell ausführen.
- `health.export`: Exporte (geplant).

## Check Types & Config Beispiele

### systemd Unit Status (`service_unit`)
```json
{
  "unit": "nginx.service",
  "incident_open_after_minutes": 5,
  "incident_close_after_minutes": 5
}
```

### Process Check (`process`)
```json
{
  "process_name": "gunicorn",
  "min_count": 1
}
```

### TCP Port (`tcp_port`)
```json
{ "host": "127.0.0.1", "port": 5432 }
```

### HTTP (`http`)
```json
{ "url": "https://example.com/health", "method": "GET", "expect_status": 200, "contains": "ok" }
```

### DNS (`dns`)
```json
{ "hostname": "example.com" }
```

### Internet Reachability (`internet`)
```json
{ "url": "https://example.com" }
```

### CPU Load (`cpu_load`)
```json
{ "warn_load": 4, "crit_load": 8, "per_core": true }
```

### Memory (`memory`)
```json
{ "warn_percent": 80, "crit_percent": 90 }
```

### Disk (`disk`)
```json
{ "path": "/", "warn_percent": 80, "crit_percent": 90, "warn_inodes_percent": 80, "crit_inodes_percent": 90 }
```

### Time Sync (`time_sync`)
```json
{ "max_offset_ms": 100 }
```

### DB Ping (`db_ping`)
```json
{ "db_path": "inventory.db", "warn_ms": 150, "crit_ms": 300 }
```

### Queue Depth (`queue_depth`)
```json
{
  "queue_table": "job_queue",
  "status_column": "status",
  "pending_values": ["pending"],
  "warn_depth": 50,
  "crit_depth": 100,
  "heartbeat_table": "worker_heartbeats",
  "heartbeat_column": "updated_at",
  "max_heartbeat_age_seconds": 300
}
```

### Cache Ping (`cache_ping`)
```json
{ "host": "127.0.0.1", "port": 6379, "type": "redis" }
```

### Log Pattern (`log_pattern`)
```json
{ "path": "/var/log/syslog", "pattern": "ERROR", "max_bytes": 8192, "must_match": false }
```

## Scheduler Details
- Hintergrund-Job alle 60 Sekunden.
- Prüft fällige Checks anhand `interval_seconds`.
- Speichert Run + Resultate + Events, erstellt Incidents bei CRIT-Dauer.
- Retention Cleanup (14 Tage) pro Scheduler-Lauf.

## API Documentation
- `GET /api/health/summary`
- `GET /api/health/services`
- `GET /api/health/checks`
- `GET /api/health/checks/{id}`
- `POST /api/health/checks`
- `PATCH /api/health/checks/{id}`
- `POST /api/health/run`
- `GET /api/health/incidents`
- `POST /api/health/incidents/{id}/ack`
- `POST /api/health/incidents/{id}/mute`
- `POST /api/health/incidents/{id}/ticket`
- `GET /api/health/history?days=1|7`

## How to add new checks
1. Implementiere eine Funktion mit `@register_health_check("type")`.
2. Rückgabeformat: `status`, `severity`, `reason`, `metrics`, `details`.
3. Registriere einen neuen Check in `health_check_definitions` (UI oder DB).
4. UI liest den Check automatisch im Catalog ein.

## Data Safety
- Sensible Felder werden beim API-Output und in Resultaten redacted.
- UI zeigt nur redigierte Konfigurationen.
