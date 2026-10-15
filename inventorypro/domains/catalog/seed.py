"""Reviewed offline starter models; never replace existing or user-edited entries."""
import json
from pathlib import Path
from .matching import compact, manufacturer_key, sync_inventory
from .media import store_image
from .service import create_model, add_model_image

DATA=Path(__file__).resolve().parents[2]/'data'/'product_images'


def initialize_catalog(db,uploads):
    added=0
    for item in json.loads((DATA/'credits.json').read_text(encoding='utf-8')):
        if db.execute('SELECT 1 FROM product_catalog_seed_history WHERE seed_key=?',(item['key'],)).fetchone():continue
        existing=db.execute('SELECT id FROM product_models WHERE manufacturer_key=? AND model_key=?',
            (manufacturer_key(item['manufacturer']),compact(item['name']))).fetchone()
        if existing is None:
            model=create_model(db,{**item,'source_url':item['model_source_url']},source_kind='builtin',source_ref=item['key'])
            with (DATA/item['filename']).open('rb') as source:media=store_image(db,uploads,source,mime_type='image/png')
            metadata={**item,'source_kind':'builtin','source_ref':item['key']}
            add_model_image(db,model['id'],media,metadata,model['updated_at'])
            added+=1
        db.execute('INSERT INTO product_catalog_seed_history(seed_key) VALUES (?)',(item['key'],))
    if added:sync_inventory(db)
    return added
