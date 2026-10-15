# UI Changelog

## 2026-10-15 – Enterprise-Arbeitsabläufe auf dev

- Gemeinsame App-/Auth-Shell einschließlich Service Desk, Administration und MFA.
- Aufgaben-Dashboard mit berechtigungsgerechten Kennzahlen und Zielfiltern.
- Gemeinsamer Bestand mit serverseitiger Suche/Pagination, eigenen Detailseiten,
  Kurzansicht und persönlichen gespeicherten Ansichten.
- Geführte Erfassung, geschützte ungespeicherte Eingaben und durchsuchbare Zuordnung.
- Sichere Kategorieentfernung/-umordnung ohne implizite Inventarlöschung.
- Lager- und Platzplanung mit Einheiten, Packliste, 2D und bestehendem 3D.
- Gemeinsame Designvorgaben und Tastaturreiter; funktionierende Einstellungsnavigation.
- Persistente Produktionssecrets, Docker-Schnellstart und Update-Kompatibilitätswerkzeug.
- GitLab-Prüfpipeline und Regressionstests; keine Releaseveröffentlichung.

Prüfungen und Grenzen: docs/enterprise/QUALITY.md und PROGRESS.md.


## Phase 1 Plan & Dateien
### Plan (kurz)
1. Audit & Tokenisierung (Farben, Spacing, Typo, Radius, Shadow).
2. Neues App-Shell Layout (Sidebar + Topbar + Content).
3. Komponentenbibliothek (Buttons, Inputs, Cards, Panels, Tables, Modals).
4. Alle Views auf neue Layout- und Komponenten-Styles umstellen.
5. Dokumentation in design-system.md + ui-patterns.md.

### Betroffene Dateien
- `static/style.css`
- `templates/index.html`
- `templates/tickets.html`
- `templates/stats.html`
- `templates/knowledge.html`
- `templates/roadmap.html`
- `templates/dependencies.html`
- `templates/time_machine.html`
- `templates/users.html`
- `templates/locations.html`
- `templates/login.html`
- `templates/reset_password.html`
- `templates/verify_otp.html`
- `design-system.md`
- `ui-patterns.md`
- `changelog-ui.md`

## Phase 2 Umsetzung
- **App Shell:** Einheitliche Sidebar, Topbar, Content-Abstände (alle App-Seiten).
- **Auth Screens:** Login, Reset, OTP auf ein gemeinsames Auth-Layout vereinheitlicht.
- **Tokens & Komponenten:** Neue Design Tokens, Buttons, Inputs, Panels, Tables.

### Page-Übersicht
- **Dashboard / Inventory (index.html):** Content Layout gestrafft, einheitliche Abstände.
- **Tickets:** Hauptbereich konsolidiert, Content-Abstände harmonisiert.
- **Knowledge Base:** Content Flow vereinheitlicht, einheitliche Panels.
- **Roadmap:** Abschnittsstruktur mit konsistentem Spacing.
- **Dependencies (Graph):** Layout auf App-Content Grid abgestimmt.
- **Time Machine:** Content Layout + App-Spacing aktualisiert.
- **Stats:** App-Content Abstände standardisiert.
- **Users / Locations:** Konsistente App-Content Struktur.
- **Auth:** Moderne, reduzierte Auth-Layouts.
