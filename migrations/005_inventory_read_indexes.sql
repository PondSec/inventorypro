-- Accelerate reverse links and latest-object metadata without changing business data.
CREATE INDEX IF NOT EXISTS idx_inventory_asset_devices_device ON asset_devices(device_id, asset_id);
CREATE INDEX IF NOT EXISTS idx_inventory_assignment_latest ON asset_assignment_history(asset_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_inventory_activity_modified ON activity_log(entity_type, entity_id, created_at);
CREATE INDEX IF NOT EXISTS idx_inventory_activity_history ON activity_log(entity_type, entity_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_inventory_maintenance_due ON maintenance_tasks(status, due_date, device_id);
CREATE INDEX IF NOT EXISTS idx_inventory_maintenance_device ON maintenance_tasks(device_id, due_date, id);
CREATE INDEX IF NOT EXISTS idx_inventory_ticket_assets_asset ON ticket_assets(asset_id, ticket_id);
