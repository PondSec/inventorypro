# Terminal Module (Maintenance Console)

## Überblick
Das Terminal-Modul bietet eine **gesicherte Maintenance Console** mit vordefinierten Recipes für Diagnose, Services, Logs und eine eingeschränkte DB-Console. Es gibt **keinen freien Shell-Zugriff**. Alle Aktionen werden audit-logged, Ausgaben redacted und begrenzt.

## Feature Flag / Deaktivierung
Das Terminal kann über die Server Settings komplett deaktiviert werden:

* **Settings → Terminal Modul → Terminal aktivieren** (default: OFF)

Wenn deaktiviert, werden alle API-Endpunkte mit `403` geblockt.

## Berechtigungen (RBAC)
Neue Permissions:

* `terminal.view` – Terminal-Tab anzeigen (read-only UI).
* `terminal.use` – Terminal-Recipes ausführen.
* `terminal.db_write` – Schreibende DB-Aktionen (zusätzlich zu `terminal.use`).

> Hinweis: `terminal.db_write` wirkt nur, wenn zusätzlich **Terminal Modul → DB-Write erlauben** aktiv ist.

## Sicherheitsmodell (Defense in Depth)

* **Admin-only (RBAC):** Zugriff auf UI und API über `terminal.view` / `terminal.use`.
* **Feature Flag:** Terminal standardmäßig deaktiviert.
* **Optional IP-Allowlist:** Separate Allowlist nur für Terminal-Endpunkte.
* **Re-Auth:** Vor Session-Start Passwort + optional OTP (falls MFA eingerichtet).
* **Rate Limiting:** per User / Minute.
* **Timeouts & Output Limits:** Commands laufen mit Timeouts, Ausgabe ist auf 200 KB begrenzt.
* **Redaction:** Tokens/Secrets/Passwörter im Output werden maskiert.
* **Whitelist-Only Recipes:** kein freier Shell-Execute.
* **Audit Logging:** jede Aktion wird protokolliert (User, Zeit, Params, Status, Duration).

## Terminal Sessions
`terminal_sessions` speichert Sessions mit TTL (Default: 15 Minuten):

* `id`, `user_id`, `created_at`, `expires_at`, `mode`, `ip`, `user_agent`, `last_activity`, `active`

## Audit Logs
`terminal_audit_logs` speichert pro Aktion:

* `user_id`, `session_id`, `action_type`, `params_json`, `status`, `duration_ms`, `output_preview`, `created_at`

Sensible Daten werden vor dem Speichern redacted.

## Recipes (Whitelist)
### Diagnostics
* `ping` – Ping Host (max 4 Pings)
* `dns_lookup` – DNS Resolve
* `tcp_check` – TCP Port Check
* `http_check` – HTTP GET/HEAD Check

### Services
* `services_list` – Allowlist Services anzeigen
* `service_status` – systemctl is-active (Allowlist)
* `service_restart` – optional, nur wenn **AllowServiceRestart** aktiviert

### Logs
* `logs_tail` – Tail für Allowlist Logquellen
* `logs_search` – Suche in den letzten N Zeilen

### Environment
* `environment_snapshot` – Build/Env/Uptime/DB-Latency/Disk

### Database Console
* `/api/terminal/db/query` – Read-only SQL (SELECT/EXPLAIN)
* `/api/terminal/db/execute` – Write SQL (nur mit `terminal.db_write` + EXECUTE + optional Break-Glass)

## Command Console (UI)
Im Terminal-Tab gibt es zusätzlich eine **Command Console**. Diese ist **kein Shell**, sondern mappt kurze Kommandos auf die vorhandenen Recipes.

Beispiele:

* `ping example.com 4`
* `dns example.com`
* `tcp host 443`
* `http https://example.com GET`
* `service status nginx`
* `service restart nginx`
* `logs tail app 50`
* `logs search app error 100`
* `env`
* `db.query SELECT * FROM assets LIMIT 5`
* `db.exec EXECUTE UPDATE assets SET status='retired' WHERE id=1`

## Adding New Recipes
1. Implementiere einen Handler in `app.py` (z. B. `run_custom_recipe`).
2. Registriere ihn im `TERMINAL_RECIPES`-Registry.
3. UI: füge ein Formular im Terminal-Tab hinzu und rufe `/api/terminal/run` mit `recipe_id` + `params`.
4. Achte auf: Validierung, Timeouts, Redaction, Allowlist.

## Disable/Break-Glass
* **Disable:** Terminal Modul → deaktivieren.
* **Break-Glass Mode:** ermöglicht gefährliche DB-Queries – nur im Notfall aktivieren.

## Hinweise
Dieses Modul ist sicherheitskritisch. Änderungen sollten immer einen Security-Review durchlaufen.
