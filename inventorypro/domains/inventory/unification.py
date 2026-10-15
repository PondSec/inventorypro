"""Transactional conversion into assets, retaining legacy IDs for dependent modules.

Startup calls this after checksummed schema migrations and a private backup.
Old business rows are never deleted here.
"""
from collections import defaultdict


class UnificationError(ValueError):pass


def _category_name(db,name):
    candidate=name;index=2
    while db.execute('SELECT 1 FROM asset_categories WHERE name=?',(candidate,)).fetchone():
        candidate=f'{name} ({index})';index+=1
    return candidate


def convert_inventory(db):
    """Caller owns outer commit/backup; one savepoint prevents partial conversion."""
    result={'categories':0,'assets':0,'components':0,'pictures':0}
    db.execute('SAVEPOINT inventory_asset_conversion')
    try:
        # Physical inventory can legitimately contain several items with the
        # same display name. Stable IDs and serial numbers identify the objects.
        db.execute('DROP INDEX IF EXISTS idx_assets_category_name')
        for row in db.execute('''SELECT c.* FROM categories c LEFT JOIN asset_legacy_categories m ON m.category_id=c.id
                WHERE m.category_id IS NULL ORDER BY c.id''').fetchall():
            category=db.execute('''INSERT INTO asset_categories(name,icon,description,fields,created_at)
                VALUES (?,?,?,?,?)''',(_category_name(db,row['name']),row['icon'],row['description'],row['fields'],row['created_at'])).lastrowid
            db.execute('INSERT INTO asset_legacy_categories(category_id,asset_category_id) VALUES (?,?)',(row['id'],category))
            db.execute("INSERT INTO asset_category_scope(category_id,scope) VALUES (?,'devices')",(category,))
            result['categories']+=1
        for row in db.execute('''SELECT d.*,m.asset_category_id FROM devices d
                LEFT JOIN asset_legacy_devices existing ON existing.device_id=d.id
                LEFT JOIN asset_legacy_categories m ON m.category_id=d.category_id
                WHERE existing.device_id IS NULL ORDER BY d.id''').fetchall():
            asset=db.execute('''INSERT INTO assets(name,category_id,specs,serial_number,location_id,created_at)
                VALUES (?,?,?,?,?,?)''',(row['name'],row['asset_category_id'],row['specs'],row['serial_number'] or '',row['location_id'],row['created_at'])).lastrowid
            db.execute('INSERT INTO asset_legacy_devices(device_id,asset_id) VALUES (?,?)',(row['id'],asset));result['assets']+=1
        # Aggregate duplicate legacy links by quantity without changing or
        # discarding their original notes/rows in the compatibility tables.
        links=defaultdict(list)
        for row in db.execute('''SELECT ad.*,m.asset_id AS child FROM asset_devices ad
                JOIN asset_legacy_devices m ON m.device_id=ad.device_id ORDER BY ad.id'''):
            links[(row['asset_id'],row['child'])].append(dict(row))
        for (parent,child),rows in links.items():
            quantities=[1 if row['quantity'] is None else row['quantity'] for row in rows]
            if any(not isinstance(value,int) or value<1 for value in quantities) or sum(quantities)>1000000:
                raise UnificationError('Eine bestehende Inhaltszuordnung hat eine ungültige Menge. Die Umstellung wurde vollständig zurückgenommen.')
            changed=db.execute('''INSERT INTO asset_components(parent_asset_id,child_asset_id,quantity,notes,created_at)
                VALUES (?,?,?,?,?) ON CONFLICT(parent_asset_id,child_asset_id) DO NOTHING''',
                (parent,child,sum(quantities),'\n'.join(row['notes'] for row in rows if row['notes']),rows[0]['created_at'])).rowcount
            result['components']+=changed
        # Identical media files are referenced, never copied or discarded.
        fields=['product_id','override_hash','suppress_image','match_method','fingerprint','confirmed_by_user_id','updated_at',
                'override_source_url','override_license_code','override_attribution','override_reviewed_at','override_reviewed_by_user_id']
        result['pictures']=db.execute('INSERT INTO asset_product_media(asset_id,'+','.join(fields)+') SELECT m.asset_id,'+','.join('dp.'+field for field in fields)+''' FROM device_product_media dp
            JOIN asset_legacy_devices m ON m.device_id=dp.device_id
            WHERE NOT EXISTS (SELECT 1 FROM asset_product_media ap WHERE ap.asset_id=m.asset_id)''').rowcount
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise UnificationError('Die vorhandenen Daten enthalten ungültige Verweise. Die Umstellung wurde vollständig zurückgenommen.')
        db.execute("UPDATE inventory_model_state SET unified_assets=1,converted_at=coalesce(converted_at,CURRENT_TIMESTAMP) WHERE id=1")
        db.execute('RELEASE SAVEPOINT inventory_asset_conversion')
        return result
    except BaseException:
        db.execute('ROLLBACK TO SAVEPOINT inventory_asset_conversion');db.execute('RELEASE SAVEPOINT inventory_asset_conversion');raise
