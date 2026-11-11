# Threat model

## Assets and trust boundaries

Assets include account credentials, session cookies, TOTP/recovery codes, LDAP
bind credentials, SMTP credentials, inventory-link secrets and cookies, uploaded
files, backups, database records, update signing keys and Docker host control.
Trust boundaries are the browser/proxy boundary, authenticated user boundary,
filesystem/backup boundary, external network boundary and updater/Docker socket
boundary.

## Threats and controls

| Threat | Current exposure | Required control and verification |
| --- | --- | --- |
| Session forgery after restart | A random fallback application key invalidates sessions and is not persistent | Production startup must require `APP_SECRET_KEY`; test missing/present keys and key rotation procedure |
| CSRF | Origin/Sec-Fetch checks do not prove user intent for every browser write | Per-session CSRF tokens for forms and fetch; negative tests for missing, mismatched and cross-origin tokens |
| Credential disclosure | Inventory-link plaintext fallback is enabled by default | Valid encryption key required for secret writes; encrypted migration and rotation tests; never log values |
| SSRF | Inventory links, health checks and terminal HTTP checks make outbound calls | Canonical URL parsing, DNS/IP validation before connect and redirect validation; default deny internal ranges; test redirects and DNS changes |
| Proxy header spoofing | Forwarded headers affect origin and secure transport decisions | Trust forwarded headers only from configured proxy addresses; test direct spoofed headers |
| Malicious upload/import | Filename/type/archive validation exists but needs consistent limits and ownership checks | Size limits, server-side names, archive traversal/expansion tests, content policy and safe download headers |
| Authorization bypass | Many routes carry per-route decorators | Route inventory, deny tests for every sensitive write and object ownership tests |
| Brute force / session abuse | Mixed in-memory and database throttling | Bounded, shared-capable limiter abstraction and tests for login, MFA, reset and proxy paths |
| Scheduler duplication | Scheduler starts in web runtime | Explicit scheduler process ownership and idempotent jobs; multi-worker tests/documentation |
| Backup theft/tampering | Backups can be plaintext; restore path is not uniformly verified | Encryption policy, checksum/manifest, restore drill and least-privilege directories |
| Supply-chain update compromise | Updater has Docker socket access | Signed digest manifest, HTTPS host allowlist, rollback health test, restricted updater deployment and audited socket exposure |

## Risk decisions

The Docker socket is a critical host-control capability. It must only be mounted
for the optional updater profile, never exposed through the application, and
must run from a reviewed image. Inventory links may require private networks in
some installations; that is an explicit high-risk opt-in with audit logging,
not a default. TLS verification remains enabled by default.

## Security event logging

Security logs record actor, action, outcome, object identifier and correlation
metadata. They must redact credential values, authorization headers, tokens,
cookies and encryption material. Error responses must identify configuration
problems without returning secrets or decrypted data.

## Review cadence

Threat-model review is required for authentication, proxy, import/upload,
backup/restore, migration and update changes. Dependency review runs in CI and
release review confirms secret configuration, proxy policy and restore evidence.
