# ADR 0002: Introduce versioned SQLite migrations

## Status

Accepted.

## Context

The legacy schema is evolved by inline bootstrap statements, which do not create
an auditable history or checksum protection.

## Decision

Record immutable, ordered SQL migrations in `migrations/` and apply them through
the `schema_migrations` ledger. The legacy bootstrap remains temporarily to keep
existing databases compatible while schema creation is extracted.

## Consequences

New migrations have durable identifiers and checksums. The migration framework
does not retroactively make historical inline changes reversible; risky changes
use expand/migrate/contract releases and verified backups.
