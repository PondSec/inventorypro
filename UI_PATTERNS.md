# Inventory Pro UI Patterns

## List → Detail
- Links: Tabelle oder Card-Grid.
- Rechts: Detailpanel (`panel`) mit Kontextaktionen.
- Für mobile: Detail im selben Flow (Accordion/Modal).

## Filterbar
- `.filter-bar` direkt unter `page-header`.
- Links: Suche + Filter.
- Rechts: Primary Action (z. B. „Neu erstellen“).

## Table
- `.table-wrapper` + `.table`.
- Sticky header.
- Actions in letzter Spalte als `inline-actions`.
- Bulk Actions: Optional in einer `toolbar` oberhalb.

## Modal
- `.modal` Overlay + `.modal-content`.
- Header mit Titel + Close.
- Actions im Footer als `toolbar`.

## Empty State
- `.empty-state` mit Titel, Erklärung, CTA.

## Cards / KPIs
- `.card` für KPIs oder kleinere Inhalte.
- Mehrere Cards in `.grid`.

## Graph / Timeline
- Toolbar oben, Controls gruppiert.
- Detailpanel für Node/State Informationen.
- Compare-Ansicht: Nebeneinander mit klaren Differenz-Highlights.
