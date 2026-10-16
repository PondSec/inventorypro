# Release verification 0.3.1

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
