# Refactoring plan

## Guardrails

Before moving a concern, add or identify route and behaviour tests for it.
Retain endpoint names and payloads through compatibility wrappers. No pull
request combines unrelated domains, a schema redesign and a new product feature.

## Ordered work packages

1. Architecture/security documentation and regression baseline.
2. Test tooling, coverage and CI skeleton.
3. Production secret-key policy.
4. Inventory-link encryption, plaintext migration and rotation.
5. CSRF, security headers and trusted-proxy handling.
6. Upload/import hardening.
7. Application factory and configuration boundary.
8. Authentication and settings extraction.
9. Versioned database migrations.
10. Asset, ticket and remaining domain extraction.
11. Cache, scheduler and background-job ownership.
12. Federation/proxy security, backup/restore and updater hardening.
13. Locked dependencies, quality gates, release automation and open-source
    governance documentation.

## Migration and rollback policy

Each schema migration has an identifier, description, preflight requirements,
transaction behaviour, backup instruction and tested downgrade or restore path.
Feature extraction pull requests are reversible by redeploying the preceding
release while the schema remains forward compatible. Destructive migrations are
split into expand, migrate, validate and contract releases.

## Pull-request template requirements

Every pull request documents goal, baseline, change, security impact, database
impact, compatibility, tests, manual review, rollback and known limits. It is
validated against the existing suite before and after the focused changes.
