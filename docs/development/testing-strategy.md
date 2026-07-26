# Testing strategy

## Test layers

* Unit tests cover configuration parsing, encryption, validation, URL handling
  and domain services without network access.
* Flask integration tests cover authentication, permissions, session state,
  CSRF, headers, uploads, imports, backups, migrations and API compatibility.
* Contract tests pin current route status codes, payload shapes and ownership
  rules before an endpoint is extracted.
* Browser tests cover mobile core flows with Playwright Firefox. CI installs the
  browser explicitly; local setup uses `python -m playwright install firefox`.
* Updater tests mock manifests, Docker commands and health checks for valid
  update, invalid signature, digest mismatch, downgrade and rollback paths.

## Required negative coverage

Every security-sensitive flow has an explicit denial test: missing production
secret, missing/invalid CSRF token, wrong encryption key, forbidden role,
cross-user object access, unsafe proxy address/redirect, oversized or malformed
upload/import, failed migration, failed backup restore and failed update health
check.

## Commands

Create an isolated environment, install dependencies and run:

```sh
python -m pip install -r requirements-dev.lock
python -m playwright install --with-deps firefox
python -m pytest --cov=app --cov=inventorypro --cov-report=term-missing --cov-report=xml
```

Coverage gates are at least 80% overall and 90% for new/security modules. The
baseline and final report must distinguish unexecuted UI/browser dependencies
from code failures; a missing browser is an environment failure, not a passing
test result.

## Test data rules

Tests create temporary databases and directories, never use `inventory.db`,
production data, real credentials or external network endpoints. Test fixtures
reset global caches/schedulers and use deterministic clocks or mocked clients
where timing matters.
