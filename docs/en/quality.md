# Release verification 0.4.0

[Deutsch](../de/quality.md) · [Documentation](../INDEX.md)

Checked on 16 October 2026.

- Complete local regression: 714 tests and 46 subtests passed on Python 3.14 with Chromium and Firefox.
- Additional Linux Docker run on Python 3.12: 94 backend tests passed. Both runs report two existing LDAP dependency deprecation warnings.
- New workflows cover private and shared wishes, partial quantities, acquisition as real assets, existing inventory links, project assembly, permissions and atomic bulk actions.
- Storage planning covers its in-place 3D view, visible placements, keyboard interaction, Light/Dark themes, mobile dialogs, deletion and failure handling.
- Browser tests cover German and English interfaces and unchanged user content. Existing visual baselines were compared; new storage views were also inspected as screenshots.
- New commits were scanned for credentials with no findings. Private operational documents are excluded from release artifacts.

## Signed artifacts

- The signing Linux pipeline passes 704 tests and 46 subtests. Ten pixel comparisons with macOS-only baselines are skipped on Linux; functional Chromium/Firefox checks remain active.
- The final signed image passes fresh installation, first login with password change and restart with an unchanged persistent key. Python packages, migrations and starter pictures are included.
- The real old updater installs 0.4.0 using the compatible manifest. The new updater restores the previous schema and image after an intentionally rejected health check; restoration was also exercised inside a Docker data volume.
- A separate direct upgrade from 0.3.1 retains assets, contained components, permissions, ticket links and server-uploaded photos. An earlier deliberately failed upgrade attempt restored the exact schema and records.
- Both manifest formats validate with the previously shipped Ed25519 key. AMD64 and ARM64 images are anonymously available from both registries under the same digest.
- A separate GitLab run exposed three synchronization problems in older browser tests. They now wait for document readiness, dialog focus and completed save navigation. Their functional assertions are retained; all 18 affected tests and two subtests pass together.

The signed runtime image comes from commit `88c8da3`; later changes affect only tests and this report. Windows and Safari were not run. The public image source does not guarantee complete product coverage.

## Earlier verification: 0.3.1

[Deutsch](../de/quality.md) · [Documentation](../INDEX.md)

Verified on 16 October 2026 using synthetic records and isolated test volumes.

## Results

- Signed Linux pipeline: 611 tests and 46 subtests passed, with two platform-specific visual baselines skipped. No failures. Chromium and Firefox were executed.
- The complete local regression before the final additional translation case passed 612 tests and 46 subtests. Final focused checks cover translation fallbacks, unchanged inventory values, language switching and save confirmation.
- The final Docker image passes fresh installation, initial login with forced password change, restart with a persistent key, and complete Python-package and license-file checks.
- Upgrades from 0.2.0 and 0.3.0 preserve inventory data, quantities, permissions, tickets, attachments and update policy. The direct patch upgrade used the final signed image. Product pictures and ticket deletion were verified over HTTP.
- The actual older updater installs the signed image on native Linux. After an intentionally rejected health check, the new updater restores the previous database, schema and image. Locally built baseline images and Docker data volumes were also tested.
- Both manifest formats accept the original Ed25519 key and reference the same digest. AMD64 and ARM64 manifests are anonymously accessible from the GitLab registry.
- German and English were checked across 14 workspaces, asset creation, inline editing and selection dialogs. The language setting persists and applies to login. User-entered data stays unchanged. Light and dark views were also inspected visually.

## Limitations

An older test that accesses a macOS bind mount concurrently through host SQLite and containers encountered database I/O errors. This path is not reported as passed. Native Linux workflows and Docker named-volume checks pass. The Compose quick start uses a named volume.

Windows/PowerShell and Safari were not executed for this release. Linux skips two visual baselines maintained for macOS only; functional browser tests remain enabled. Public image sources cannot guarantee coverage of every model. Two deprecation warnings originate in the LDAP dependency.
