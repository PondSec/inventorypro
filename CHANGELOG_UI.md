# UI Changelog

## Phase 1 Plan & Dateien
### Plan (kurz)
1. Audit & Tokenisierung (Farben, Spacing, Typo, Radius, Shadow).
2. Neues App-Shell Layout (Sidebar + Topbar + Content).
3. Komponentenbibliothek (Buttons, Inputs, Cards, Panels, Tables, Modals).
4. Alle Views auf neue Layout- und Komponenten-Styles umstellen.
5. Dokumentation in DESIGN_SYSTEM.md + UI_PATTERNS.md.

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
- `DESIGN_SYSTEM.md`
- `UI_PATTERNS.md`
- `CHANGELOG_UI.md`

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
