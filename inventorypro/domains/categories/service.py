"""Category removal never removes inventory or silently discards its taxonomy."""
from __future__ import annotations

import json


class CategoryRemovalError(ValueError):
    def __init__(self, message, code, status=409, **details):
        super().__init__(message)
        self.payload = {"error": message, "code": code, **details}
        self.status = status


def remove_category(db, kind, category_id, target_id=None):
    """Lock, validate, reassign and remove in the caller's single transaction.

    Object IDs, dynamic specs, assignments, notes and lifecycle data are retained.
    Packing configurations must be updated explicitly because their field mappings
    cannot safely be applied to an arbitrary replacement category.
    """
    table, objects = {"device": ("categories", "devices"),
                      "asset": ("asset_categories", "assets")}[kind]
    if not db.in_transaction:
        db.execute("BEGIN IMMEDIATE")
    if not db.execute(f"SELECT id FROM {table} WHERE id = ?", (category_id,)).fetchone():
        raise CategoryRemovalError("Kategorie nicht gefunden.", "category_not_found", 404)
    count = db.execute(f"SELECT COUNT(*) FROM {objects} WHERE category_id = ?", (category_id,)).fetchone()[0]
    references = {objects: count}
    if kind == "asset":
        planners = []
        for row in db.execute("SELECT id, name, binpacking_config FROM asset_categories"):
            try:
                config = json.loads(row["binpacking_config"] or "{}")
            except (TypeError, ValueError):
                continue
            if isinstance(config, dict) and config.get("enabled") and str(config.get("content_category_id")) == str(category_id):
                planners.append({"id": row["id"], "name": row["name"]})
        if planners:
            raise CategoryRemovalError(
                "Die Kategorie wird in der Lager- und Platzplanung verwendet. Bitte zuerst die Planung anpassen.",
                "category_used_in_planning", references=references, planningCategories=planners)
    legacy_categories=[]
    if kind=='asset' and db.execute("SELECT unified_assets FROM inventory_model_state WHERE id=1").fetchone()[0]:
        legacy_categories=[row[0] for row in db.execute('SELECT category_id FROM asset_legacy_categories WHERE asset_category_id=?',(category_id,))]
        if legacy_categories:
            legacy_count=db.execute('SELECT count(*) FROM devices WHERE category_id IN ('+','.join('?' for _ in legacy_categories)+')',legacy_categories).fetchone()[0]
            references['legacyDevices']=legacy_count
            if legacy_count and target_id is None:
                raise CategoryRemovalError('Die Kategorie hat noch historische Inventarverweise. Bitte eine Zielkategorie wählen.','category_in_use',references=references)
    if target_id is not None:
        if isinstance(target_id, bool) or not isinstance(target_id, int) or target_id <= 0 or target_id == category_id:
            raise CategoryRemovalError("Bitte eine andere gültige Zielkategorie wählen.", "invalid_target_category", 400)
        if not db.execute(f"SELECT id FROM {table} WHERE id = ?", (target_id,)).fetchone():
            raise CategoryRemovalError("Die Zielkategorie existiert nicht mehr.", "invalid_target_category", 400)
    if count and target_id is None:
        raise CategoryRemovalError(
            f"Die Kategorie enthält {count} Inventareinträge. Wählen Sie eine Zielkategorie, um diese zu erhalten.",
            "category_in_use", references=references)
    if count:
        db.execute(f"UPDATE {objects} SET category_id = ? WHERE category_id = ?", (target_id, category_id))
    if legacy_categories:
        if target_id is not None:
            db.execute('UPDATE asset_legacy_categories SET asset_category_id=? WHERE asset_category_id=?',(target_id,category_id))
        else:
            db.execute('DELETE FROM asset_legacy_categories WHERE asset_category_id=?',(category_id,))
            for legacy_id in legacy_categories:db.execute('DELETE FROM categories WHERE id=?',(legacy_id,))
    db.execute(f"DELETE FROM {table} WHERE id = ?", (category_id,))
    return {"status": "deleted", "reassigned": count, "target_category_id": target_id}
