# Release policy

Only a successful CI run for `main` can invoke the release workflow. Maintainers
update `VERSION`, review migrations and changelog entries, verify the coverage
report and confirm a restore drill before merging a release change.

The workflow builds an immutable GHCR image, signs the update manifest with the
repository's protected Ed25519 signing key and publishes a GitHub release. The
update sidecar accepts only the signed digest manifest. A failed health check
must result in rollback evidence before the release is considered operational.

Releases are stopped if CI, manifest signing, image build, migration preflight or
restore validation fails. A rollback deploys the preceding immutable image and
restores the documented data snapshot when the schema is not forward compatible.
