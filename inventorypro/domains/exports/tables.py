"""Portable inventory data, including composition and locally cached images.

Credentials, provider settings and asynchronous lookup jobs belong to a full
database backup, not to a portable inventory export.
"""
INVENTORY_TABLES=(
    'categories','asset_categories','locations','vendors','contracts','purchase_orders',
    'assets','devices','asset_devices','purchase_order_items','maintenance_tasks',
    'device_tags','device_notes','asset_assignment_history','asset_assignments',
    'asset_relation_types','asset_relations','software','software_installations','attachments',
    'asset_legacy_categories','asset_legacy_devices','asset_permission_scope','asset_category_scope',
    'asset_components','asset_notes','asset_tags','asset_maintenance_tasks',
    'product_models','product_identifiers','product_media_files','product_images',
    'asset_product_media','device_product_media',
)


def available_tables(db,tables=INVENTORY_TABLES):
    existing={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return tuple(table for table in tables if table in existing)


def dependency_order(db,tables):
    pending=list(tables);ordered=[]
    dependencies={table:{row['table'] for row in db.execute(f'PRAGMA foreign_key_list({table})') if row['table'] in pending and row['table']!=table} for table in pending}
    while pending:
        ready=[table for table in pending if not dependencies[table].intersection(pending)]
        if not ready:raise ValueError('Die Importtabellen enthalten zyklische Verweise. Bitte ein vollständiges Datenbank-Backup verwenden.')
        for table in ready:ordered.append(table);pending.remove(table)
    return ordered
