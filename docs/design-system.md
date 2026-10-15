# Inventory Pro – gemeinsames Designsystem

Stand 15.10.2026. Die Anwendung bleibt Flask/Jinja mit vorhandenem Alpine und
JavaScript. Neue Oberflächen nutzen gemeinsame Komponenten; fachliche Modelle
werden durch gemeinsame Arbeitsabläufe verbunden.

## Verbindliche Quellen

- `inventorypro/domains/customization/defaults.json`: gemeinsame Vorgaben für
  Backendvalidierung und Browser. `_design_tokens.html` liefert dieselben Werte
  vor dem ersten Theme-Skript in App- und Auth-Shell aus. Keine getrennte
  JavaScript-Kopie der Konfiguration.
- `static/style.css`: semantische Farbtokens, Light/Dark und bestehende Komponenten.
- `static/enterprise.css`: bestehende fachliche Komponenten und Planungsassistent.
- `static/design-system.css`: verbindliche kompakte Shell, Navigation, Seitenkopf,
  Kontrollgrößen, Tabellen- und Objektkomponenten des visuellen Relaunchs.
- `templates/_ui.html`: gemeinsame Jinja-Primitiven für Seitenkopf, Status,
  Produktbild/Icon, Objektkopf, Eigenschaften und Accordions.
- `static/theme.js`: vorhandene Instanz-/Browseranpassungen, Themewechsel und Cache.
  Explizit gespeicherte Kundenanpassungen werden weiter angewendet.

## Sprache und Hierarchie

Eine Hauptaufgabe pro Seite. Titel und Breadcrumbs im gemeinsamen Seitenkopf; die 56-px-Topbar enthält
Suche und Kontosteuerung. Die gruppierte Navigation ist standardmäßig 240 px breit. Keine zweite Navigation zur selben Funktion, kein dekorativer
Startbereich. Objektbezeichnungen bleiben Links zur eigenen Detailseite.

Systemschrift mit Inter/Segoe-UI-Fallback, Grundschrift 14 px, Tabellen 13 px,
Metadaten 11–13 px, Seitentitel 26 px. Abstandsskala 4/8/12/16/20/24/32/40/48/64 px.
Standardradien: 4/6/8 px; Buttons und Eingaben 6 px, Panels und Dialoge 8 px.
Akzent Blau kennzeichnet Auswahl/primäre Aktion; Status immer zusätzlich als Text.
Flächen, Text, Rahmen und Fokus beziehen ihre Farben aus semantischen Tokens,
keine neue lokale Palette in einzelnen Modulen.

## Shell und Komponenten

Angemeldete Seiten erben `base_app.html`; `_app_shell.html` rendert Sidebar und
Topbar. Ticketqueues bleiben eine fachliche zweite Navigation innerhalb dieser
Shell. Authentifizierung erbt `base_auth.html`. Sidebarangebote richten sich nach
Rollen; Backendprüfungen bleiben unabhängig davon verpflichtend.

- `.btn` mit Primary/Secondary/Danger für echte Aktionen. Pro Arbeitsbereich eine
  erkennbare Hauptaktion. Deaktivierte und laufende Speicherung klar anzeigen.
- `.workspace-panel`, `.list-toolbar`, `.data-table-scroll`, `.data-table` und
  `.list-pagination` für neue Listen. Sortierung als Link mit aria-sort;
  serverseitige Suche/Filter/Pagination im URL-Zustand.
- Eigene Detailseiten mit `.object-summary`, `.detail-tabs`, `.detail-panel`.
  Fachlich optionale Informationen in nativen details/summary-Bereichen.
- `.object-panel`: natives dialog mit tatsächlichen Objektdaten, Produktkopf,
  Reitern und Accordions. Ab 1280 px als 424-px-Split-View unter der Topbar;
  die Arbeitsliste bleibt erreichbar. Schmal als modaler Drawer mit Fokusbegrenzung.
  Escape, Fokus-Rückgabe, Browserhistorie und tabgenaue Links bleiben erhalten.
  Objektdaten werden manuell beim Öffnen geladen, nicht für jede Tabellenzeile.
- `[role=tablist]`: `static/components.js` bietet Pfeiltasten, Pos1/Ende und genau
  einen Tabstop. Zugehörige tabpanels über aria-controls/aria-labelledby verbinden.
- Große Zuordnungen durchsuchen und paginieren; ausgewählte Einträge bleiben als
  entfernbare Chips sichtbar, auch wenn der aktuelle Suchfilter sie nicht enthält.

## Zugänglichkeit und Fehler

Sichtbare Labels, Hilfe und Fehlermeldung gehören zur Eingabe. Placeholder ersetzt
kein Label. Fokus ist sichtbar, Hauptinhalt per Skip-Link erreichbar. Kein Status
allein über Farbe; reduzierte Bewegung beachten. Tabellen dürfen innerhalb ihres
benannten Containers horizontal scrollen, die gesamte Seite soll nicht überlaufen.

Speicherfehler erhalten Eingaben, Meldungen erscheinen am Formular, doppelte
Speicherung wird verhindert. Ungespeicherte Geräte-/Komponentenänderungen werden
vor Verwerfen geschützt. Umfangreiche Bearbeitung gehört auf eine Detailseite;
Legacy-Managementdialoge bleiben während der inkrementellen Migration erreichbar.

Tatsächliche Prüfungen und Grenzen stehen in `docs/enterprise/QUALITY.md`;
keine pauschale WCAG-Zertifizierung aus diesen Gestaltungsregeln ableiten.
