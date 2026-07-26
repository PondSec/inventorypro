# ADR 0001: Adopt a modular monolith

## Status

Accepted.

## Context

Inventory Pro is a single Flask deployment, but the historical `app.py` combines
all infrastructure and domain responsibilities. A microservice split would add
operational complexity without a demonstrated scaling need.

## Decision

Keep one deployable Flask application. Extract configuration, security,
migrations, jobs and domains into packages and blueprints incrementally behind
route-compatible adapters.

## Consequences

Deployments remain simple and SQLite stays supported. Refactoring must preserve
imports/routes during transition, so temporary compatibility code is expected.
