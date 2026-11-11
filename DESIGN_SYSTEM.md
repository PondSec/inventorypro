# Inventory Pro Design System

## UI/UX Audit (Phase 1)
### Hauptprobleme
- Zu viele voneinander abweichende Styles (viele Tailwind-Utilities pro Seite), wodurch Konsistenz und Wiedererkennbarkeit leiden.
- Unterschiedliche Abstände, Radii und Button-Stile erzeugen visuelles Rauschen.
- Tabellen, Filterbars und Sidepanels sind uneinheitlich strukturiert.
- Fehlende klar definierte Typografie-Hierarchie für Überschriften, Metadaten und Hilfetexte.
- Interaktions-States (Hover/Focus/Active) sind nicht überall sauber ersichtlich.

### Ziele für das neue System
- Ruhige, klare Oberfläche mit klarer Hierarchie und gutem „scannable“ Layout.
- Einheitliche Komponenten und konsistente Abstände.
- Starker Fokus auf schnelle Bedienbarkeit (klare Action-Cluster, Filterbars, Toolbars).
- Zugänglichkeit (Kontraste, Fokus-Ringe, klare Labels, gut erkennbare States).

## Design Tokens
### Typografie
- Font: `Inter`, `Segoe UI`, System UI
- Base: 15px
- Titles: 1.8rem
- Section title: 1.1rem
- Meta/Labels: 0.7–0.85rem

### Spacing Scale (px)
`4, 8, 12, 16, 20, 24, 32, 40, 48, 64`

### Radius
- `sm`: 8px
- `md`: 12px
- `lg`: 18px
- `pill`: 999px

### Shadows
- `xs`: subtile Card-Schattierung
- `sm`: leichte Elevation
- `md`: Modals/Overlays
- `lg`: hero/cta

### Color System
- Background: `#f6f7fb`
- Surface: `#ffffff`
- Surface muted: `#f1f3f7`
- Text: `#0f172a`
- Muted text: `#6b7280`
- Border: `#e5e7eb`
- Accent: `#2563eb`
- Success: `#16a34a`
- Warning: `#f59e0b`
- Danger: `#dc2626`

## Komponenten-Regeln
### Buttons
- `.btn` Basis mit zwei Größen (Standard + Icon).
- Variants: `.btn-primary`, `.btn-secondary`, `.btn-ghost`, `.btn-outline`, `.btn-danger`.
- Fokus: klarer Fokus-Ring.

### Form Controls
- `.input`, `.select`, `.textarea` mit gleicher Höhe und klarer Label-Struktur.
- Labels sind immer oberhalb.
- Hilfe-/Validierungs-Text unterhalb.

### Cards & Panels
- `.card` für kompakten Inhalt.
- `.panel` für größere Abschnitte (Listen, Tabellen, Graphen).
- Always: Border + leichter Shadow.

### Tabellen
- `.table-wrapper` + `.table`.
- Sticky header.
- Hover-Zeilen.
- Toolbars + Filterbar als Standardpattern.

### Navigation
- `.app-shell` mit Sidebar + Topbar.
- Sidebar mit Sections und `nav-link` States.
- Active: Accent-Hintergrund.

### Empty/Loading
- `.empty-state` für leere Listen.

## Layout Grundgerüst
- **App-Shell:** Sidebar + Topbar + Content.
- **Page Layout:** `page-header` + `panel` mit Tools + Content.
- **Filterbars:** Eine Zeile, klar gruppiert.
- **Detail Panels:** Rechts oder unterhalb als Panel.
