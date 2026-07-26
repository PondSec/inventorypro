# Changelog

All notable released changes are documented here. Versions follow `VERSIONING.md`.

## Unreleased

### Security

* Require a persistent application secret in production.
* Add session-bound CSRF protection, trusted-proxy handling and a versioned
  inventory-link encryption keyring.

### Operations

* Add a SQLite migration ledger, verified backup manifests and controlled restore
  tooling.

### Development

* Add CI, pinned direct dependencies and stabilization documentation.
