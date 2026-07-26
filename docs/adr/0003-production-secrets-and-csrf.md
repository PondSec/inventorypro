# ADR 0003: Fail closed for production secrets and browser writes

## Status

Accepted.

## Context

An ephemeral session key and plaintext Inventory-Link fallback are unsafe in
production. Origin checking alone is not a CSRF control.

## Decision

Production startup requires `APP_SECRET_KEY`. Inventory-Link secrets require a
valid Fernet keyring and use a versioned encrypted format. Browser writes require
a per-session CSRF token; trusted proxy headers are accepted only from configured
proxy networks.

## Consequences

Operators must provide secrets before deployment and explicitly migrate legacy
link values. Non-browser clients must obtain/send the CSRF token or use a future
dedicated service-authentication mechanism.
