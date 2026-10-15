# Lager- und Platzplanung

Der neue Bereich `/inventory/planning` führt durch Lagerplatzwahl, Innenmaße,
Gegenstandsauswahl mit Mengen, Rotation/Abstände und die überprüfbare Packliste.
Bestehende Inventarmodelle, Kategorie-Konfigurationen und Beziehungen bleiben erhalten.

Erkennbare Breite/Höhe/Tiefe-Felder werden nur bei eindeutiger Namenszuordnung
automatisch übernommen. mm, cm, m und Zoll werden in Millimeter umgerechnet;
unbekannte Einheiten werden gemeldet. Ohne gespeicherte Einheit sind anfängliche
Millimeterwerte ausdrücklich zu bestätigen. Feldmapping ist eine optionale Alternative.

Die vorhandene mehrstrategische Best-Fit-Decreasing-Berechnung bleibt bestehen.
Wandabstand und Abstand zwischen Gegenständen werden geometrisch berücksichtigt.
Nicht platzierte Stücke gelten nicht als mathematischer Unmöglichkeitsnachweis.
Tragfähigkeit, Gewicht, Schwerpunkt und Handhabung sind keine Bestandteile des
vorhandenen Algorithmus. Die Oberfläche nennt diese Grenzen ausdrücklich.

Vor jeder Berechnung prüft der Server endliche positive Maße, bekannte Einheiten,
Rotationstyp, gültige unterschiedliche Inventareinträge, Selbstreferenzen und
positive ganze Mengen. Maximal 200 Stück pro Planung begrenzen den Rechenaufwand.
Reine Vorschauen ändern weder Stammdaten noch Zuordnungen oder Kategorie-Mappings.

Explizit gespeicherte Pläne sind versionierte Eingabe-/Ergebnissnapshots in
`storage_plans` (Migration 004), einschließlich Urheber und Aktivitätsprotokoll.
Löschen eines Plans entfernt kein Inventar. Lesen benötigt Inventarleserechte,
Speichern/Löschen `assets.manage`. Bereits gespeicherte Snapshots bleiben auch nach
späteren Stammdatenänderungen nachvollziehbar.

Die zweidimensionale Ebenenvorschau und tabellarische Packliste sind primär;
gespeicherte Pläne öffnen optional die unveränderte vorhandene 3D-Oberfläche.
Dort werden dieselben berechneten Platzierungen angezeigt.
