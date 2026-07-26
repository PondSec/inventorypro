# Stabilization report

## Scope

This report records the local stabilization work on the `codex/stabilization-hardening`
branch. It distinguishes implemented controls from remaining work; no control is
claimed solely because it is documented.

## Delivered changes

* Added architecture, security, operations, testing and refactoring baseline
  documents plus three architecture decisions.
* Added a production startup policy that requires `APP_SECRET_KEY`; development
  receives a clearly logged ephemeral key only.
* Added a versioned Inventory-Link Fernet format, keyring rotation support,
  explicit legacy secret migration and plaintext blocking.
* Added session-bound CSRF validation, browser token propagation, security
  headers and trusted-proxy header handling.
* Hardened attachment storage with process-private paths, server-derived MIME
  types and content-signature checks.
* Added a migration ledger with immutable checksums and an initial baseline
  migration; legacy bootstrap remains temporarily for compatibility.
* Added backup manifests, integrity-checked SQLite restoration and an emergency
  pre-restore snapshot.
* Added explicit scheduler ownership, local Inventory-Link administrator checks,
  pinned direct dependencies, lockfiles, CI and CI-gated release automation.
* Added contribution, security, support, versioning, release and issue/PR
  documentation.

## Architecture before and after

Before this work, security policy, crypto, migration state and startup settings
were all embedded in `app.py`. After it, `inventorypro/config.py`, `csrf.py`,
`secrets.py`, `migrations.py` and `factory.py` provide tested seams, while WSGI
uses the compatibility factory. `app.py` still owns most domain routes and SQL;
it remains the primary technical-debt item and must be extracted domain by domain
without a compatibility-breaking rewrite.

## Validation

Local validation completed on the stabilization branch:

* `python -m pytest -q`: 79 passed, 8 subtests passed.
* Targeted security/upload/restore tests: 25 passed.
* `python -m compileall -q app.py updater.py docker_wsgi.py inventorypro scripts`.
* Bundled Node runtime: Tailwind asset build and `node --check static/csrf.js`.
* Ruby YAML parser: CI, release and issue-template workflows.
* `git diff --check`.

The coverage report measured 43.46% overall (3,797 of 8,736 executable lines)
before the final small upload-test addition. The new `inventorypro` infrastructure
modules measured about 89%. The project therefore does **not** meet the requested
80% overall coverage target yet; CI publishes the report rather than claiming a
passing coverage gate.

## Known limitations and risks

* `app.py` is still a large compatibility monolith; authentication, settings,
  assets, tickets, links and jobs require incremental blueprint/service
  extraction.
* Historical inline schema creation is still present beside the new migration
  ledger. New schema changes must use migrations; historical destructive changes
  do not have generated down-migrations.
* SQLite, in-memory rate limits and login caches limit multi-worker and multi-node
  operation. The scheduler is explicitly single-owner but not externally
  coordinated.
* Inventory-Link DNS validation reduces SSRF exposure but does not by itself
  provide a fully pinned DNS-to-connect implementation against every rebinding
  scenario.
* The application CSP retains inline script support for the existing server-side
  UI; converting it to nonce/hash policies requires template and frontend work.
* Local Docker image validation could not run because the Docker daemon was not
  available at `unix:///Users/pond/.docker/run/docker.sock`.

## Recommended next steps

1. Extract authentication/settings, then Inventory Links/backup, then asset and
   ticket domains into blueprints with contract tests before each move.
2. Replace inline schema bootstrap with complete, reversible migration phases.
3. Add coverage in high-risk legacy modules until the measured overall threshold
   reaches 80%, then enforce it in CI.
4. Introduce a shared cache/rate-limit backend and external scheduler owner before
   multi-worker production operation.
5. Add DNS-pinned outbound connection handling and CSP nonces as focused security
   changes.
6. Re-run Docker build/smoke validation on a machine with Docker available.

## Pull-request plan

No remote pull request existed while this report was generated. The local commit
history is intentionally split into reviewable groups: documentation/test basis,
security defaults, migration/backup operations, and CI/open-source governance.
Remote pull requests should preserve those groups rather than squash them into an
unreviewable migration.
