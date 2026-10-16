"""Atomic, revision-checked actions on an explicitly selected asset page."""
from . import assets


FIELDS = {'category_id', 'location_id', 'cost_center', 'warranty_end',
          'retirement_date', 'retirement_reason'}


def selection(payload, *, revisions=False):
    items = payload.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise assets.AssetError('Bitte zwischen 1 und 100 Assets auswählen.')
    seen = set()
    for item in items:
        if (not isinstance(item, dict) or isinstance(item.get('id'), bool)
                or not isinstance(item.get('id'), int) or item['id'] <= 0
                or item['id'] in seen):
            raise assets.AssetError('Bitte eindeutige gültige Assets auswählen.')
        if revisions and (isinstance(item.get('expectedRevision'), bool)
                          or not isinstance(item.get('expectedRevision'), int)):
            raise assets.AssetError('Bitte die Auswahl neu laden und prüfen.', 409)
        seen.add(item['id'])
    return items


def prepare(db, can, payload):
    items = selection(payload)
    with assets.mutation(db):
        for item in items:
            assets.require(db, can, item['id'], write=True)
        return [assets.get_asset(db, can, item['id']) for item in items]


def apply(db, can, payload, *, parse_fields, validate_specs):
    items = selection(payload, revisions=True)
    action = payload.get('action')
    changes = payload.get('changes')
    if action not in {'update', 'delete'}:
        raise assets.AssetError('Ungültige Mehrfachaktion.')
    if action == 'update' and (not isinstance(changes, dict) or not changes
                               or set(changes) - FIELDS):
        raise assets.AssetError('Bitte mindestens ein gemeinsames Feld auswählen.')
    with assets.mutation(db):
        # Check every original revision before deletion can update a selected
        # parent's revision through composition triggers. Hold the write lock.
        for item in items:
            assets.require(db, can, item['id'], write=True)
            assets._check_revision(db, item['id'], item['expectedRevision'])
        for item in items:
            identifier = item['id']
            revision = assets.version(db, identifier)
            if action == 'delete':
                assets.delete_asset(db, can, identifier, revision)
            else:
                assets.update_asset(db, can, identifier,
                                    {**changes, 'expectedRevision': revision},
                                    parse_fields=parse_fields, validate_specs=validate_specs)
    return [item['id'] for item in items]
