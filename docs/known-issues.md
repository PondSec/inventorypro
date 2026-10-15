# Verifizierte Einschränkungen

Stand 15.10.2026. Die tatsächlich ausgeführten Prüfungen und Umgebungen stehen im

- Release 0.2.0 ist auf GitLab und im kompatiblen GitHub-Feed veröffentlicht.
  Anonyme Registry-/Paketdownloads und beide aktiven Signaturen sind geprüft.
- Linux-/macOS-Dockerinstallation geprüft; keine Windows-/Safari-Abnahme,
  vollständige WCAG-Zertifizierung oder freigegebene Pixelbaseline behauptet.
- Gemischter Host-/Guest-SQLite-Zugriff auf Mac-Bindmounts ist nicht freigegeben.
  Reguläre Compose-Datenvolumes und Rollback innerhalb Docker sind geprüft.
- Alte Sidecars tauschen sich nicht selbst aus; der dauerhaft gepflegte Legacy-
  Feed liefert ihnen weiterhin dieselben freigegebenen GitLab-Versionen.
- Ein nie gestarteter/nicht eingerichteter Updater kann kein Update automatisch
  abholen. Ausgeschaltete Auto-Updates und Wartungsfenster werden respektiert.
- Neue Updater unterstützen auch lokale Docker-Image-IDs als sichere Rückfallziele.
  Bereits ausgelieferte alte Sidecars besitzen diese zusätzliche Unterstützung nicht.
- Einzelne umfangreiche Legacy-Verwaltungsdialoge bleiben für bestehende Funktionen
  erreichbar; eine vollständige Ablösung sämtlicher Dialoge wird nicht behauptet.
