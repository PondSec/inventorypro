-- Keep old integrations on the same field definitions after category edits.
CREATE TRIGGER compat_asset_category_change AFTER UPDATE OF name,fields,icon,description ON asset_categories
WHEN (SELECT unified_assets FROM inventory_model_state WHERE id=1)=1
 AND (SELECT busy FROM inventory_compat_sync WHERE id=1)=0 AND (1)
BEGIN
 UPDATE inventory_compat_sync SET busy=1 WHERE id=1;
 UPDATE categories SET
 name=CASE WHEN NEW.name IS OLD.name THEN name
 WHEN id=(SELECT min(category_id) FROM asset_legacy_categories WHERE asset_category_id=NEW.id) THEN NEW.name
 ELSE NEW.name||' (Legacy '||id||')' END,
 fields=NEW.fields,icon=NEW.icon,description=NEW.description
 WHERE id IN (SELECT category_id FROM asset_legacy_categories WHERE asset_category_id=NEW.id);
 UPDATE inventory_compat_sync SET busy=0 WHERE id=1;
END;
CREATE TRIGGER compat_legacy_category_change AFTER UPDATE OF name,fields,icon,description ON categories
WHEN (SELECT unified_assets FROM inventory_model_state WHERE id=1)=1
 AND (SELECT busy FROM inventory_compat_sync WHERE id=1)=0 AND (1)
BEGIN
 UPDATE asset_categories SET name=NEW.name,fields=NEW.fields,icon=NEW.icon,description=NEW.description
 WHERE id=(SELECT asset_category_id FROM asset_legacy_categories WHERE category_id=NEW.id);
END;
