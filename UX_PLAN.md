# Inventory Pro – UX-Plan (Phase 1)

**Tech/Stack:** Server-rendered HTML (Flask/Jinja) + Alpine.js + Tailwind via CDN + custom CSS.

---

## 1) Geräte-Liste (Inventory-Übersicht)
**A) Top-Tasks**
1. Gerät schnell finden (Suche/Filter).
2. Neues Gerät anlegen.
3. Gerät öffnen und Details prüfen.
4. Geräte nach Kategorie/Standort/Owner filtern.
5. Export/Reporting anstoßen.

**B) Aktuelle UI-Probleme**
- „Hero“-Bereich mit zu vielen CTA-Buttons (Button-Wand) lenkt ab.
- Filter sind verstreut und mischen sich mit Insights/Quick-Actions.
- Asset- und Geräte-Listen wirken wie zwei getrennte Seiten ohne klare Priorität.
- Row-Actions zu sichtbar/zu viel (Edit/Delete/Details gleichzeitig).

**C) NEW LAYOUT (Wireframe)**
```
Page Header: Titel + Status + Primary Action rechts
Breadcrumb: Inventory > Geräte
Filterbar: Suche | Filterchips | Sort | Saved Views
Main (Tabs): [Geräte | Assets]
- Geräte-Tab: Tabelle mit Row-Overflow
- Assets-Tab: kompakte Tabelle
Right Panel: Insights | Aktivität | Wartungen
```

**D) Änderungen**
- Hero entfernt → kompakter Header + Filterbar.
- Quick Actions in Overflow-Menü (Header).
- Geräte/Assets in Tabs zusammengeführt.
- Row-Actions in Overflow pro Zeile.

**E) Actions**
- Primary: „Neues Gerät“
- Secondary: „Import/Export“, „Kategorie anlegen“
- Danger (Overflow): „Gerät löschen“, „Kategorie löschen“

---

## 2) Gerät-Detail
**A) Top-Tasks**
1. Kerninfos prüfen (Kategorie, Standort, Owner, Status).
2. Specs & Notizen ergänzen.
3. Wartung planen/abhaken.
4. Tags verwalten.
5. Aktionen (Bearbeiten, Archivieren/Löschen).

**B) Aktuelle UI-Probleme**
- Modal wirkt wie lange Liste ohne klare Sektionen.
- Aktionen (Edit/Delete) sind nicht eindeutig gruppiert.
- Notizen/Tags/Wartung konkurrieren visuell.

**C) NEW LAYOUT (Wireframe)**
```
Detail Drawer/Modal
Header: Gerätname + Status + Primary Action
Tabs: Overview | Specs | Wartung | Historie
Main: Überblick (KPI + Kernfelder)
Sidepanel: Tags + Quick Actions
```

**D) Änderungen**
- Inhalte in Tabs gruppiert.
- Actions in Header + Overflow.

**E) Actions**
- Primary: „Bearbeiten“
- Secondary: „Ticket erstellen“
- Danger: „Löschen“

---

## 3) Asset-Liste
**A) Top-Tasks**
1. Asset finden und öffnen.
2. Neues Asset anlegen.
3. Komponenten sehen.
4. Notizen prüfen.
5. Export/Verknüpfungen.

**B) Probleme**
- Asset-Liste untergeordnet, ohne eigenen Fokus.
- Actions zu prominent.

**C) NEW LAYOUT**
```
Tab: Assets
Filterbar: Suche | Status | Typ
Main: Tabelle (Asset, Komponenten, Notizen, Status)
Right Panel: Asset-Insights
```

**D) Änderungen**
- Assets als gleichwertiger Tab.
- Row-Actions im Overflow.

**E) Actions**
- Primary: „Neues Asset“
- Secondary: „Relation hinzufügen“
- Danger: „Asset löschen“

---

## 4) Asset-Detail
**A) Top-Tasks**
1. Komponenten prüfen.
2. Lebenszyklus-Infos sehen.
3. Notizen bearbeiten.
4. Beziehungen verstehen.
5. Offene Tickets prüfen.

**B) Probleme**
- Lange Scroll-Liste ohne Navigationsstruktur.

**C) NEW LAYOUT**
```
Header: Asset-Name + Status + Primary Action
Tabs: Overview | Lifecycle | Relations | Tickets
Sidepanel: Komponenten + Quick Actions
```

**D) Änderungen**
- Tabs + Sidepanel.

**E) Actions**
- Primary: „Bearbeiten“
- Secondary: „Ticket erstellen“
- Danger: „Löschen“

---

## 5) Ticket-Liste
**A) Top-Tasks**
1. Ticket finden/filtern.
2. Neues Ticket erstellen.
3. SLA/Status prüfen.
4. Bulk-Aktionen.
5. Priorisieren.

**B) Probleme**
- Hero nimmt zu viel Platz.
- Filter/Status und Tabellenactions vermischt.

**C) NEW LAYOUT**
```
Header: Tickets + Primary Action
Filterbar: Suche | Status | Priorität | SLA | Assignee
Main: Tabelle mit Bulk-Checkbox + Row-Overflow
Sidepanel: SLA-Übersicht + Status
```

**D) Änderungen**
- Hero entfernt.
- Bulk-Action Bar eingeführt.

**E) Actions**
- Primary: „Neues Ticket“
- Secondary: „Export“
- Danger: „Ticket schließen/löschen“ (Overflow)

---

## 6) Ticket-Detail
**A) Top-Tasks**
1. Status/Priorität aktualisieren.
2. Kommentar hinzufügen.
3. SLA/Deadline prüfen.
4. Zuweisung ändern.
5. Verknüpfungen sehen.

**B) Probleme**
- Details & Kommentare nicht klar getrennt.

**C) NEW LAYOUT**
```
Header: Ticket + Status + Primary Action
Tabs: Overview | Activity | SLA | Links
Sidepanel: Actions + Watcher
```

**D) Änderungen**
- Tabs + Sidepanel.

**E) Actions**
- Primary: „Kommentar hinzufügen“
- Secondary: „Status ändern“
- Danger: „Schließen/Löschen“

---

## 7) Roadmap
**A) Top-Tasks**
1. Status/Milestones sehen.
2. Eintrag anlegen.
3. Board filtern.
4. Abhängigkeiten prüfen.
5. Sync mit Tickets prüfen.

**B) Probleme**
- Hero dominiert, Board zu weit unten.
- Aktionen zu prominent.

**C) NEW LAYOUT**
```
Header + Filterbar (Status, Team, Quartal)
Main: Board
Sidepanel: Milestones + KPI
```

**D) Änderungen**
- Hero entfernt.
- Filterbar über Board.

**E) Actions**
- Primary: „Roadmap erstellen“
- Secondary: „Sprint exportieren“
- Danger: „Archivieren“

---

## 8) Dependency-Graph
**A) Top-Tasks**
1. Graph filtern/zoomen.
2. Impact-Analyse starten.
3. Knoten-Details prüfen.
4. Simulation starten.
5. Export.

**B) Probleme**
- Controls verstreut, Graph nimmt zu wenig Fokus.

**C) NEW LAYOUT**
```
Header
Toolbar: Suche | Filter | Layout | Zoom
Main: Graph Canvas
Sidepanel: Node Details | Impact Summary
```

**D) Änderungen**
- Controls kompakt in Toolbar.
- Details in Sidepanel.

**E) Actions**
- Primary: „Simulation starten“
- Secondary: „Layout ändern“
- Danger: „Links löschen“

---

## 9) Zeitmaschine
**A) Top-Tasks**
1. Zeitpunkt/Branch wählen.
2. Vergleich starten.
3. Änderungen prüfen.
4. Roadmap simulieren.
5. Export.

**B) Probleme**
- Hero dominiert, Controls verteilt.

**C) NEW LAYOUT**
```
Header
Toolbar: Branch | Zeitraum | Compare
Main: Timeline + Diff
Sidepanel: Change List
```

**D) Änderungen**
- Toolbar kompakt.
- Split-View für Compare.

**E) Actions**
- Primary: „Vergleich starten“
- Secondary: „Snapshot speichern“
- Danger: „Branch löschen“

---

## 10) Wissensbasis
**A) Top-Tasks**
1. Suche nach Artikeln.
2. Kategorien browsen.
3. Artikel lesen/bearbeiten.
4. Artikel mit Ticket verknüpfen.
5. Neues KB-Item erstellen.

**B) Probleme**
- Hero überladen, Suche nicht prominent genug.
- Kategorien/Content vermischt.

**C) NEW LAYOUT**
```
Header + Searchbar
Main: 3-Spalten
- Left: Kategorien
- Center: Artikel-Liste
- Right: Artikel-Detail + Link-to-Ticket CTA
```

**D) Änderungen**
- Suche in Header.
- Kategorien links, Content rechts.

**E) Actions**
- Primary: „Neuer Artikel“
- Secondary: „In Ticket verlinken“
- Danger: „Artikel löschen“

---

## 11) Benutzer/Rollen/Rechte
**A) Top-Tasks**
1. Benutzer finden.
2. Rolle zuweisen.
3. Rechte prüfen.
4. Neuen Benutzer erstellen.
5. Benutzer deaktivieren.

**B) Probleme**
- Hero dominiert, Formulare zu lang.
- Rollen/Permissions nicht klar getrennt.

**C) NEW LAYOUT**
```
Header + Filterbar
Main: Tabelle + Sidepanel (User-Details)
Tabs in Sidepanel: Profil | Rollen | Rechte
```

**D) Änderungen**
- Filterbar + Sidepanel.

**E) Actions**
- Primary: „Benutzer anlegen“
- Secondary: „Rolle erstellen“
- Danger: „Deaktivieren“

---

## 12) Statistiken
**A) Top-Tasks**
1. KPI Überblick.
2. Zeitraum/Filter ändern.
3. Reports exportieren.
4. Trendanalyse.

**B) Probleme**
- Hero zu dominant, Charts ohne Filterbar.

**C) NEW LAYOUT**
```
Header + Filterbar (Zeitraum, Kategorie)
Main: KPI Cards + Charts
Sidepanel: Highlights/Insights
```

**D) Änderungen**
- Filterbar + kompaktes KPI-Grid.

**E) Actions**
- Primary: „Report exportieren“
- Secondary: „Dashboard teilen“
- Danger: „Reset Filter“

---

## 13) Standorte
**A) Top-Tasks**
1. Standort finden.
2. Standort anlegen.
3. Gerätezuordnung prüfen.
4. Standort bearbeiten/löschen.

**B) Probleme**
- Hero dominiert.
- Actions zu prominent.

**C) NEW LAYOUT**
```
Header + Filterbar
Main: Standortliste (Table)
Sidepanel: Standort-Details + Quick Actions
```

**D) Änderungen**
- Filterbar + Sidepanel.

**E) Actions**
- Primary: „Standort anlegen“
- Secondary: „Import“
- Danger: „Standort löschen"
