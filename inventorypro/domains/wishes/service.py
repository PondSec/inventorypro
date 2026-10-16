"""Owner-scoped research, acquisition and assembly transactions.

Money is stored as integer minor units. Each acquired unit is a real asset;
research never creates inventory implicitly. Callers own the commit boundary.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from urllib.parse import urlsplit

from inventorypro.domains.inventory import assets


class WishError(assets.AssetError):
    pass


def text(value, label, maximum=240):
    return assets._text(value, label, maximum)


def money(value):
    if value in (None, ''):
        return None
    try:
        if isinstance(value, bool):
            raise ValueError
        amount = Decimal(str(value).replace(',', '.'))
        if not amount.is_finite() or amount < 0 or amount > 100000000 or amount * 100 != (amount * 100).to_integral_value():
            raise ValueError
        return int(amount * 100)
    except (ValueError, InvalidOperation, TypeError):
        raise WishError('Bitte einen Preis mit höchstens zwei Nachkommastellen eingeben.')


def integer(value, maximum=10000):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise WishError('Bitte eine gültige ganze Menge eingeben.')
    return value


def currency(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Z]{3}', value):
        raise WishError('Bitte einen dreistelligen Währungscode eingeben.')
    return value


def permission(can, write=False):
    if not (can('wishes.manage') or not write and can('wishes.view')):
        raise WishError('Keine Berechtigung für Wünsche und Projekte.', 403)


def visible(alias='w', project=False):
    if project:
        return f"({alias}.owner_id=? OR {alias}.visibility='team')"
    return f"((p.id IS NOT NULL AND (p.owner_id=? OR p.visibility='team')) OR (p.id IS NULL AND ({alias}.owner_id=? OR {alias}.visibility='team')))"


def project(db, can, actor, identifier, write=False):
    permission(can, write)
    row = db.execute(f'SELECT * FROM wish_projects p WHERE p.id=? AND {visible("p", True)}', (identifier, actor)).fetchone()
    if not row:
        raise WishError('Projekt nicht gefunden.', 404)
    return dict(row)


def wish(db, can, actor, identifier, write=False):
    permission(can, write)
    row = db.execute(f'''SELECT w.*,p.name AS project_name,p.asset_id AS project_asset_id,
        coalesce(p.visibility,w.visibility) AS effective_visibility
        FROM wishes w LEFT JOIN wish_projects p ON p.id=w.project_id
        WHERE w.id=? AND {visible()}''', (identifier, actor, actor)).fetchone()
    if not row:
        raise WishError('Wunsch nicht gefunden.', 404)
    result = dict(row)
    result['acquisitions'] = []
    for record in db.execute('SELECT * FROM wish_acquisitions WHERE wish_id=? ORDER BY id', (identifier,)):
        item = dict(record)
        if item['asset_id'] and not assets.can_access(db, can, item['asset_id']):
            item['asset_id'] = None
            item['asset_name'] = None
            item['restricted'] = True
        result['acquisitions'].append(item)
    result['owned'] = db.execute('SELECT count(*) FROM wish_acquisitions WHERE wish_id=? AND asset_id IS NOT NULL', (identifier,)).fetchone()[0]
    result['missing'] = max(0, result['quantity'] - result['owned'])
    return result


def revision(row, payload):
    if isinstance(payload.get('expectedRevision'), bool) or payload.get('expectedRevision') != row['revision']:
        raise WishError('Der Plan wurde inzwischen geändert. Bitte neu laden und die Änderungen prüfen.', 409)


def save_project(db, can, actor, payload, identifier=None):
    permission(can, True)
    if not isinstance(payload, dict):
        raise WishError('Bitte gültige Plandaten eingeben.')
    with assets.mutation(db):
        existing = project(db, can, actor, identifier, True) if identifier else {}
        if existing:
            revision(existing, payload)
        source = {**existing, **payload}
        name = text(source.get('name'), 'Name')
        if not name:
            raise WishError('Bitte einen Namen eingeben.')
        visibility = source.get('visibility', 'private')
        if visibility not in {'private', 'team'}:
            raise WishError('Bitte die Sichtbarkeit auswählen.')
        if existing and visibility != existing['visibility'] and existing['owner_id'] != actor:
            raise WishError('Nur die erstellende Person kann die Sichtbarkeit ändern.', 403)
        unit = currency(source.get('currency', 'EUR'))
        if existing and unit != existing['currency'] and db.execute('SELECT 1 FROM wishes WHERE project_id=?', (identifier,)).fetchone():
            raise WishError('Die Währung eines Projekts mit Bestandteilen kann nicht geändert werden.', 409)
        target = source.get('target_date') or None
        if target:
            try:
                target = date.fromisoformat(target).isoformat()
            except (TypeError, ValueError):
                raise WishError('Bitte ein gültiges Datum eingeben.')
        values = dict(name=name, description=text(source.get('description'), 'Beschreibung', 20000), visibility=visibility,
                      currency=unit, budget_cents=money(payload.get('budget')) if 'budget' in payload else existing.get('budget_cents'), target_date=target)
        if existing:
            db.execute('UPDATE wish_projects SET ' + ','.join(k+'=?' for k in values) + ',revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?', [*values.values(), identifier])
        else:
            identifier = db.execute('INSERT INTO wish_projects(owner_id,'+','.join(values)+') VALUES (?,'+','.join('?' for _ in values)+')', [actor, *values.values()]).lastrowid
        return project(db, can, actor, identifier)


def save_wish(db, can, actor, payload, identifier=None):
    permission(can, True)
    if not isinstance(payload, dict):
        raise WishError('Bitte gültige Plandaten eingeben.')
    with assets.mutation(db):
        existing = wish(db, can, actor, identifier, True) if identifier else {}
        if existing:
            revision(existing, payload)
        source = {**existing, **payload}
        name = text(source.get('name'), 'Name')
        if not name:
            raise WishError('Bitte einen Namen eingeben.')
        parent_id = source.get('project_id')
        if parent_id is not None:
            integer(parent_id, 2147483647)
        parent = project(db, can, actor, parent_id, True) if parent_id else None
        if (parent and parent['asset_id']) or existing.get('project_asset_id'):
            raise WishError('Dieses Projekt ist bereits im Bestand. Bitte die Zusammenstellung am Asset bearbeiten.', 409)
        visibility = source.get('visibility', 'private')
        if visibility not in {'private', 'team'}:
            raise WishError('Bitte die Sichtbarkeit auswählen.')
        if existing and existing['owner_id'] != actor and (parent_id != existing['project_id'] or visibility != existing['visibility']):
            raise WishError('Nur die erstellende Person kann den Wunsch verschieben oder seine Sichtbarkeit ändern.', 403)
        amount = integer(source.get('quantity', 1))
        if amount < existing.get('owned', 0):
            raise WishError('Die Wunschmenge darf nicht kleiner als die vorhandene Menge sein.', 409)
        unit = currency(source.get('currency', parent['currency'] if parent else 'EUR'))
        if parent and unit != parent['currency']:
            raise WishError('Alle Bestandteile müssen dieselbe Währung wie das Projekt verwenden.')
        if existing.get('acquisitions') and unit != existing['currency']:
            raise WishError('Die Währung eines bereits übernommenen Wunschs kann nicht geändert werden.', 409)
        category = source.get('category_id')
        if category is not None:
            integer(category, 2147483647)
            if not db.execute('SELECT 1 FROM asset_categories WHERE id=?', (category,)).fetchone():
                raise WishError('Kategorie nicht gefunden.')
        url = text(source.get('url'), 'Quelle', 2048)
        if url:
            try:
                parsed = urlsplit(url)
                if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password:
                    raise ValueError
            except ValueError:
                raise WishError('Bitte einen gültigen HTTP- oder HTTPS-Link ohne Zugangsdaten eingeben.')
        priority = source.get('priority', 'normal')
        if priority not in {'low', 'normal', 'high'}:
            raise WishError('Bitte eine gültige Priorität auswählen.')
        archived = source.get('archived', False)
        if archived not in (0, 1, False, True):
            raise WishError('Ungültiger Archivstatus.')
        values = dict(name=name, notes=text(source.get('notes'), 'Notizen', 20000), project_id=parent_id,
                      visibility=visibility, quantity=amount, category_id=category,
                      manufacturer=text(source.get('manufacturer'), 'Hersteller'), model=text(source.get('model'), 'Modell'),
                      unit_price_cents=money(payload.get('unit_price')) if 'unit_price' in payload else existing.get('unit_price_cents'),
                      currency=unit, url=url, priority=priority, archived=int(archived))
        if existing:
            db.execute('UPDATE wishes SET '+','.join(k+'=?' for k in values)+',revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?', [*values.values(), identifier])
        else:
            identifier = db.execute('INSERT INTO wishes(owner_id,'+','.join(values)+') VALUES (?,'+','.join('?' for _ in values)+')', [actor, *values.values()]).lastrowid
        return wish(db, can, actor, identifier)


def acquire(db, can, actor, identifier, payload, *, parse_fields, validate_specs):
    """Idempotently acquire individual physical units or link one owned asset."""
    permission(can, True)
    with assets.mutation(db):
        row = wish(db, can, actor, identifier, True)
        key = payload.get('requestKey')
        if not isinstance(key, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}', key):
            raise WishError('Bitte die Übernahme erneut öffnen und versuchen.')
        previous = db.execute('SELECT wish_id FROM wish_acquisitions WHERE actor_id=? AND request_key=?', (actor, key)).fetchone()
        if previous:
            if previous[0] != identifier:
                raise WishError('Diese Übernahme wurde bereits für einen anderen Wunsch verwendet.', 409)
            return row
        revision(row, payload)
        if row['archived'] or row.get('project_asset_id'):
            raise WishError('Dieser Plan ist abgeschlossen oder archiviert.', 409)
        amount = integer(payload.get('quantity', 1), 50)
        if amount > row['missing']:
            raise WishError('Die Menge ist größer als die noch fehlende Menge.', 409)
        existing = payload.get('asset_id')
        if existing is not None:
            integer(existing, 2147483647)
            assets.require(db, can, existing, write=True)
            if amount != 1 or db.execute('SELECT 1 FROM wish_acquisitions WHERE asset_id=?', (existing,)).fetchone():
                raise WishError('Dieses Asset wurde bereits einem Wunsch zugeordnet oder die Menge ist nicht eins.', 409)
            if db.execute('SELECT 1 FROM asset_components WHERE child_asset_id=?', (existing,)).fetchone():
                raise WishError('Dieses Asset ist bereits in einer Zusammenstellung enthalten.', 409)
        cost = money(payload.get('unit_cost')) if 'unit_cost' in payload else row['unit_price_cents']
        specs = payload.get('specs', {})
        if not isinstance(specs, dict):
            raise WishError('Eigenschaften müssen als Objekt übergeben werden.')
        specs = {**specs}
        if row['manufacturer']:
            specs.setdefault('Hersteller', row['manufacturer'])
        if row['model']:
            specs.setdefault('Modell', row['model'])
        for _ in range(amount):
            owned = assets.get_asset(db, can, existing) if existing else assets.create_asset(db, can,
                dict(name=row['name'], category_id=row['category_id'], location_id=payload.get('location_id'),
                     serial_number=text(payload.get('serial_number'), 'Inventar-/Seriennummer'),
                     notes=row['notes'] + ('\n'+row['url'] if row['url'] else ''), specs=specs,
                     acquisition_date=date.today().isoformat(), currency=row['currency'],
                     purchase_cost=cost / 100 if cost is not None else None), parse_fields=parse_fields, validate_specs=validate_specs)
            if amount > 1 and payload.get('serial_number'):
                raise WishError('Individuelle Seriennummern bitte jeweils einzeln erfassen.')
            db.execute('''INSERT INTO wish_acquisitions(wish_id,asset_id,asset_name,unit_cost_cents,currency,actor_id,request_key)
                VALUES (?,?,?,?,?,?,?)''', (identifier, owned['id'], owned['name'], cost, row['currency'], actor, key))
        db.execute('UPDATE wishes SET revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?', (identifier,))
        return wish(db, can, actor, identifier)


def assemble(db, can, actor, identifier, payload, *, parse_fields, validate_specs):
    with assets.mutation(db):
        row = project(db, can, actor, identifier, True)
        if row['asset_id']:
            assets.require(db, can, row['asset_id'])
            return row
        revision(row, payload)
        parts = db.execute('SELECT id FROM wishes WHERE project_id=? AND archived=0', (identifier,)).fetchall()
        if not parts:
            raise WishError('Bitte zuerst Bestandteile zum Projekt hinzufügen.')
        children = []
        for part in parts:
            entry = wish(db, can, actor, part[0])
            if entry['missing']:
                raise WishError('Es fehlen noch Bestandteile. Bitte zuerst alle gewünschten Mengen übernehmen.', 409)
            for acquisition in db.execute('SELECT asset_id FROM wish_acquisitions WHERE wish_id=? AND asset_id IS NOT NULL', (part[0],)):
                assets.require(db, can, acquisition[0], write=True)
                if db.execute('SELECT 1 FROM asset_components WHERE child_asset_id=?', (acquisition[0],)).fetchone():
                    raise WishError('Ein Bestandteil wird bereits in einem anderen Asset verwendet.', 409)
                children.append(acquisition[0])
        owned = assets.create_asset(db, can, dict(name=row['name'], notes=row['description'], location_id=payload.get('location_id'),
            category_id=payload.get('category_id'), specs=payload.get('specs', {})), parse_fields=parse_fields, validate_specs=validate_specs)
        for child in children:
            assets.set_component(db, can, owned['id'], child, 1, '', assets.version(db, owned['id']))
        db.execute('UPDATE wish_projects SET asset_id=?,revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE id=?', (owned['id'], identifier))
        return project(db, can, actor, identifier)


def remove(db, can, actor, kind, identifier, payload):
    with assets.mutation(db):
        row = project(db, can, actor, identifier, True) if kind == 'projects' else wish(db, can, actor, identifier, True)
        revision(row, payload)
        if kind == 'projects':
            # Unassigned wishes keep their creator and become private again.
            db.execute("UPDATE wishes SET project_id=NULL,visibility='private',revision=revision+1 WHERE project_id=?", (identifier,))
        db.execute('DELETE FROM '+('wish_projects' if kind == 'projects' else 'wishes')+' WHERE id=?', (identifier,))
