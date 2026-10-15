# Verifizierte Einschränkungen

Stand 2026-10-15: Python- und Browserprüfungen sowie Docker-Build und isolierter
Compose-Start wurden ausgeführt; aktuelle Zahlen stehen in
[PROGRESS.md](docs/enterprise/PROGRESS.md).

- Windows/PowerShell, Linux-Host und weitere Browserplattformen noch nicht geprüft.
- Keine vollständige WCAG-2.2-AA-Abnahme und keine freigegebene Pixelbaseline.
- Signierte Releaseveröffentlichung, tatsächliche GitLab-Registry und dauerhafter
  GitHub/GHCR-Kompatibilitätsspiegel erfordern geschützte Infrastrukturvariablen.
  Es wurde kein Release veröffentlicht und kein Produktionsdeployment ausgeführt.
- Ausgelieferte alte Sidecars tauschen sich nicht selbst aus. Bestandskunden können
  ohne Handarbeit weiter aktualisieren, sofern der kompatible Feed gepflegt wird.
- Im ursprünglichen Workspace sind Dateien durch iCloud ausgelagert. Aktiver
  Checkout: /Users/pond/.codex/workspaces/inventorypro-enterprise, Branch dev.
