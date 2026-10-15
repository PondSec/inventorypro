-- Old integrations retain their IDs; assets are the canonical inventory.
ALTER TABLE asset_legacy_categories RENAME TO asset_legacy_categories_previous;
CREATE TABLE asset_legacy_categories (
    category_id INTEGER PRIMARY KEY REFERENCES categories(id) ON DELETE RESTRICT,
    asset_category_id INTEGER NOT NULL REFERENCES asset_categories(id) ON DELETE RESTRICT
);
INSERT INTO asset_legacy_categories SELECT * FROM asset_legacy_categories_previous;
DROP TABLE asset_legacy_categories_previous;
CREATE INDEX idx_asset_legacy_category_target ON asset_legacy_categories(asset_category_id);
CREATE TABLE inventory_compat_sync(id INTEGER PRIMARY KEY CHECK(id=1),busy INTEGER NOT NULL DEFAULT 0 CHECK(busy IN (0,1)));
INSERT INTO inventory_compat_sync(id) VALUES(1);

CREATE TRIGGER compat_category_create AFTER INSERT ON categories
WHEN (SELECT unified_assets FROM inventory_model_state WHERE id=1)=1
 AND (SELECT busy FROM inventory_compat_sync WHERE id=1)=0 AND (1)
BEGIN
 UPDATE inventory_compat_sync SET busy=1 WHERE id=1;
 INSERT INTO asset_categories(name,fields,icon,description,created_at)
 SELECT CASE WHEN EXISTS(SELECT 1 FROM asset_categories WHERE name=NEW.name)
 THEN NEW.name||' (Legacy '||NEW.id||')' ELSE NEW.name END,NEW.fields,NEW.icon,NEW.description,NEW.created_at;
 INSERT INTO asset_legacy_categories(category_id,asset_category_id) VALUES(NEW.id,last_insert_rowid());
 UPDATE inventory_compat_sync SET busy=0 WHERE id=1;
END;

CREATE TRIGGER compat_device_create AFTER INSERT ON devices
WHEN (SELECT unified_assets FROM inventory_model_state WHERE id=1)=1
 AND (SELECT busy FROM inventory_compat_sync WHERE id=1)=0 AND (1)
BEGIN
 UPDATE inventory_compat_sync SET busy=1 WHERE id=1;
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM asset_legacy_categories WHERE category_id=NEW.category_id) THEN RAISE(ABORT,'asset_category_mapping_missing') END;
 INSERT INTO assets(name,category_id,serial_number,location_id,specs,created_at)
 SELECT NEW.name,m.asset_category_id,coalesce(NEW.serial_number,''),NEW.location_id,NEW.specs,NEW.created_at
 FROM asset_legacy_categories m WHERE m.category_id=NEW.category_id;
 INSERT INTO asset_legacy_devices(device_id,asset_id) VALUES(NEW.id,last_insert_rowid());
 UPDATE inventory_compat_sync SET busy=0 WHERE id=1;
END;

CREATE TRIGGER compat_device_change AFTER UPDATE ON devices
WHEN (SELECT unified_assets FROM inventory_model_state WHERE id=1)=1
 AND (SELECT busy FROM inventory_compat_sync WHERE id=1)=0 AND (1)
BEGIN
 UPDATE inventory_compat_sync SET busy=1 WHERE id=1;
 UPDATE assets SET name=NEW.name,serial_number=coalesce(NEW.serial_number,''),specs=NEW.specs,location_id=NEW.location_id,
 category_id=CASE WHEN NEW.category_id IS NOT OLD.category_id THEN (SELECT asset_category_id FROM asset_legacy_categories WHERE category_id=NEW.category_id) ELSE category_id END
 WHERE id=(SELECT asset_id FROM asset_legacy_devices WHERE device_id=NEW.id);
 UPDATE inventory_compat_sync SET busy=0 WHERE id=1;
END;

CREATE TRIGGER compat_asset_change AFTER UPDATE ON assets
WHEN (SELECT unified_assets FROM inventory_model_state WHERE id=1)=1
 AND (SELECT busy FROM inventory_compat_sync WHERE id=1)=0 AND (1)
BEGIN
 UPDATE inventory_compat_sync SET busy=1 WHERE id=1;
 UPDATE devices SET name=NEW.name,serial_number=NEW.serial_number,specs=NEW.specs,location_id=NEW.location_id,
 category_id=coalesce((SELECT min(category_id) FROM asset_legacy_categories WHERE asset_category_id=NEW.category_id),category_id)
 WHERE id=(SELECT device_id FROM asset_legacy_devices WHERE asset_id=NEW.id);
 UPDATE inventory_compat_sync SET busy=0 WHERE id=1;
END;

CREATE TRIGGER compat_legacy_contents_insert AFTER INSERT ON asset_devices
WHEN (SELECT unified_assets FROM inventory_model_state WHERE id=1)=1
 AND (SELECT busy FROM inventory_compat_sync WHERE id=1)=0 AND (1)
BEGIN
 UPDATE inventory_compat_sync SET busy=1 WHERE id=1;
 INSERT INTO asset_components(parent_asset_id,child_asset_id,quantity,notes,created_at)
 SELECT NEW.asset_id,m.asset_id,sum(coalesce(ad.quantity,1)),coalesce(group_concat(nullif(ad.notes,''),char(10)),''),min(ad.created_at)
 FROM asset_devices ad JOIN asset_legacy_devices m ON m.device_id=ad.device_id
 WHERE ad.asset_id=NEW.asset_id AND ad.device_id=NEW.device_id GROUP BY m.asset_id
 ON CONFLICT(parent_asset_id,child_asset_id) DO UPDATE SET quantity=excluded.quantity,notes=excluded.notes;
 UPDATE inventory_compat_sync SET busy=0 WHERE id=1;
END;

CREATE TRIGGER compat_legacy_contents_update AFTER UPDATE ON asset_devices
WHEN (SELECT unified_assets FROM inventory_model_state WHERE id=1)=1
 AND (SELECT busy FROM inventory_compat_sync WHERE id=1)=0 AND (1)
BEGIN
 UPDATE inventory_compat_sync SET busy=1 WHERE id=1;
 SELECT CASE WHEN NEW.asset_id<>OLD.asset_id OR NEW.device_id<>OLD.device_id THEN RAISE(ABORT,'asset_link_identity_immutable') END;

 INSERT INTO asset_components(parent_asset_id,child_asset_id,quantity,notes,created_at)
 SELECT NEW.asset_id,m.asset_id,sum(coalesce(ad.quantity,1)),coalesce(group_concat(nullif(ad.notes,''),char(10)),''),min(ad.created_at)
 FROM asset_devices ad JOIN asset_legacy_devices m ON m.device_id=ad.device_id
 WHERE ad.asset_id=NEW.asset_id AND ad.device_id=NEW.device_id GROUP BY m.asset_id
 ON CONFLICT(parent_asset_id,child_asset_id) DO UPDATE SET quantity=excluded.quantity,notes=excluded.notes;
 UPDATE inventory_compat_sync SET busy=0 WHERE id=1;
END;

CREATE TRIGGER compat_legacy_contents_delete AFTER DELETE ON asset_devices
WHEN (SELECT unified_assets FROM inventory_model_state WHERE id=1)=1
 AND (SELECT busy FROM inventory_compat_sync WHERE id=1)=0 AND (1)
BEGIN
 UPDATE inventory_compat_sync SET busy=1 WHERE id=1;
 DELETE FROM asset_components WHERE parent_asset_id=OLD.asset_id AND child_asset_id=(SELECT asset_id FROM asset_legacy_devices WHERE device_id=OLD.device_id)
 AND NOT EXISTS(SELECT 1 FROM asset_devices WHERE asset_id=OLD.asset_id AND device_id=OLD.device_id);
 UPDATE asset_components SET quantity=(SELECT sum(coalesce(quantity,1)) FROM asset_devices WHERE asset_id=OLD.asset_id AND device_id=OLD.device_id),
 notes=coalesce((SELECT group_concat(nullif(notes,''),char(10)) FROM asset_devices WHERE asset_id=OLD.asset_id AND device_id=OLD.device_id),'')
 WHERE parent_asset_id=OLD.asset_id AND child_asset_id=(SELECT asset_id FROM asset_legacy_devices WHERE device_id=OLD.device_id)
 AND EXISTS(SELECT 1 FROM asset_devices WHERE asset_id=OLD.asset_id AND device_id=OLD.device_id);
 UPDATE inventory_compat_sync SET busy=0 WHERE id=1;
END;

CREATE TRIGGER compat_contents_insert AFTER INSERT ON asset_components
WHEN (SELECT unified_assets FROM inventory_model_state WHERE id=1)=1
 AND (SELECT busy FROM inventory_compat_sync WHERE id=1)=0 AND (1)
BEGIN
 UPDATE inventory_compat_sync SET busy=1 WHERE id=1;
 DELETE FROM asset_devices WHERE asset_id=NEW.parent_asset_id AND device_id=(SELECT device_id FROM asset_legacy_devices WHERE asset_id=NEW.child_asset_id);
 INSERT INTO asset_devices(asset_id,device_id,quantity,notes,created_at)
 SELECT NEW.parent_asset_id,m.device_id,NEW.quantity,NEW.notes,NEW.created_at FROM asset_legacy_devices m WHERE m.asset_id=NEW.child_asset_id;
 UPDATE inventory_compat_sync SET busy=0 WHERE id=1;
END;

CREATE TRIGGER compat_contents_update AFTER UPDATE ON asset_components
WHEN (SELECT unified_assets FROM inventory_model_state WHERE id=1)=1
 AND (SELECT busy FROM inventory_compat_sync WHERE id=1)=0 AND (1)
BEGIN
 UPDATE inventory_compat_sync SET busy=1 WHERE id=1;
 SELECT CASE WHEN NEW.parent_asset_id<>OLD.parent_asset_id OR NEW.child_asset_id<>OLD.child_asset_id THEN RAISE(ABORT,'asset_link_identity_immutable') END;

 DELETE FROM asset_devices WHERE asset_id=NEW.parent_asset_id AND device_id=(SELECT device_id FROM asset_legacy_devices WHERE asset_id=NEW.child_asset_id);
 INSERT INTO asset_devices(asset_id,device_id,quantity,notes,created_at)
 SELECT NEW.parent_asset_id,m.device_id,NEW.quantity,NEW.notes,NEW.created_at FROM asset_legacy_devices m WHERE m.asset_id=NEW.child_asset_id;
 UPDATE inventory_compat_sync SET busy=0 WHERE id=1;
END;

CREATE TRIGGER compat_contents_delete AFTER DELETE ON asset_components
WHEN (SELECT unified_assets FROM inventory_model_state WHERE id=1)=1
 AND (SELECT busy FROM inventory_compat_sync WHERE id=1)=0 AND (1)
BEGIN
 UPDATE inventory_compat_sync SET busy=1 WHERE id=1;
 DELETE FROM asset_devices WHERE asset_id=OLD.parent_asset_id AND device_id=(SELECT device_id FROM asset_legacy_devices WHERE asset_id=OLD.child_asset_id);
 UPDATE inventory_compat_sync SET busy=0 WHERE id=1;
END;
