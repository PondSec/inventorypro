# Updates and releases

[Deutsch](../de/updates.md) · [Documentation](../INDEX.md)

## Existing installations

Running older updaters continue to read the signed GitHub release manifest and install the corresponding GHCR image. New updaters use GitLab. Every stable release must provide both compatible manifests and identical tested images. The original signing key remains necessary. Updating the application does not replace a running older sidecar, so the compatibility mirror is maintained.

Disable automatic updates under **Settings → Server → Updates**. A disabled updater does not fetch releases. The switch does not install a missing sidecar. New installations can enable the optional sidecar with `INVENTORY_UPDATER_ENABLED=1` in `.env` and `docker compose --profile updater up --detach --build --wait`. The updater needs Docker access and the same persistent storage as the application.

A running updater can replace a failed application. If an unhealthy dependency prevented the updater from starting at all, a one-time local intervention is required. Automatic repair is impossible without a running process.

## Verification and rollback

HTTPS host allowlists, stable channel, Ed25519 signatures and image digests are verified. The new updater stops the application before migrations, backs up the quiescent SQLite database and restores the previous database and image after a failed health check. Preserve uploads and instance keys in the existing volume.

For manual updates, back up first. In an unchanged checkout, use `git pull --ff-only` and `docker compose up --detach --build --wait app`. Stop and resolve divergent history or local changes rather than overwriting them. Do not delete the data volume.

## Release procedure

1. Review and test changes on `dev`; commit and push each completed step.
2. Run the full regression and installation, upgrade and rollback checks before approval.
3. Prepare a regular merge into `main`. Explicitly set the release version in `.release/request.json` and mirror the reviewed `dev` revision to GitHub.
4. The existing pipeline checks the authoritative GitLab source revision, tests, builds AMD64/ARM64 images and signs both manifests using the existing protected key. Artifacts initially remain a draft.
5. Verify identical images in both registries and public package downloads. Only then publish both releases.
6. Validate the actual latest manifests with both the old and current validators. Revoke temporary publishing credentials afterward.

A source push alone is not a released update. Private keys and infrastructure credentials stay outside the repository.
