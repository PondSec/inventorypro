# Known Issues

## Environment-specific verification limitations

- Docker is not available in the current execution environment (`docker: command not found`). The Dockerfile and Compose configuration were inspected and guarded with regression tests where possible, but Docker build, Compose start and container healthcheck must be re-run on a host with Docker installed.
- Browser/mobile Playwright tests cannot currently be executed in this environment because the package index/proxy blocks fetching `playwright==1.61.0` with `Tunnel connection failed: 403 Forbidden`.

## Production configuration reminders

- `docker-compose.yml` now includes a stable fallback `APP_SECRET_KEY` so a local Compose deployment starts reliably. For production, set a unique persistent `APP_SECRET_KEY` in `.env` before first use and keep it unchanged across restarts; changing it invalidates existing sessions and CSRF tokens.
- If Inventory Pro is served behind TLS or a reverse proxy, set `INVENTORY_PUBLIC_ORIGIN` to the browser-facing origin (for example `https://inventory.example.com`). Also configure `INVENTORY_TRUSTED_PROXY_NETWORKS` for trusted proxy CIDRs when relying on `X-Forwarded-*` headers.
