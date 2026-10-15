"""Canonical asset mutations and nested composition with legacy access boundaries."""
from contextlib import contextmanager
from datetime import date
import json
import math
import sqlite3

from inventorypro.domains.catalog.matching import sync_object
from .objects import specs_object


class AssetError(ValueError):
    def __init__(self,message,status=400,fields=None):super().__init__(message);self.status=status;self.fields=fields or {}


def unified(db):
    return bool(db.execute('SELECT unified_assets FROM inventory_model_state WHERE id=1').fetchone()[0])


def permission_scope(db,identifier):
    row=db.execute('''SELECT coalesce(s.scope,CASE WHEN m.device_id IS NOT NULL THEN 'devices' ELSE 'assets' END)
        FROM assets a LEFT JOIN asset_permission_scope s ON s.asset_id=a.id
        LEFT JOIN asset_legacy_devices m ON m.asset_id=a.id WHERE a.id=?''',(identifier,)).fetchone()
    if not row:raise AssetError('Asset nicht gefunden.',404)
    return row[0]


def can_access(db,can,identifier,*,write=False):
    scope=permission_scope(db,identifier)
    return can(scope+'.manage') or (not write and can(scope+'.view'))


def require(db,can,identifier,*,write=False):
    if not can_access(db,can,identifier,write=write):raise AssetError('Keine Berechtigung für dieses Asset.',403)


def scope_predicate(can,*,write=False,alias='a'):
    scopes=[scope for scope in ['devices','assets'] if can(scope+'.manage') or (not write and can(scope+'.view'))]
    expression=f"coalesce((SELECT scope FROM asset_permission_scope s WHERE s.asset_id={alias}.id),CASE WHEN EXISTS(SELECT 1 FROM asset_legacy_devices m WHERE m.asset_id={alias}.id) THEN 'devices' ELSE 'assets' END)"
    return expression+' IN ('+','.join('?' for _ in scopes)+')' if scopes else '0',scopes


def version(db,identifier):
    row=db.execute('SELECT revision FROM asset_edit_versions WHERE asset_id=?',(identifier,)).fetchone()
    if not row:raise AssetError('Asset nicht gefunden.',404)
    return row[0]


def _check_revision(db,identifier,expected):
    if isinstance(expected,bool) or not isinstance(expected,int) or expected!=version(db,identifier):
        raise AssetError('Das Asset wurde inzwischen geändert. Bitte neu laden und die Änderungen prüfen.',409)


@contextmanager
def mutation(db):
    if not db.in_transaction:db.execute('BEGIN IMMEDIATE')
    db.execute('SAVEPOINT asset_mutation')
    try:yield;db.execute('RELEASE SAVEPOINT asset_mutation')
    except BaseException:
        db.execute('ROLLBACK TO SAVEPOINT asset_mutation');db.execute('RELEASE SAVEPOINT asset_mutation');raise


def _text(value,label,maximum=240):
    if value is None:return ''
    if not isinstance(value,str) or len(value)>maximum:raise AssetError(f'{label}: Bitte gültigen Text mit höchstens {maximum} Zeichen eingeben.')
    return value.strip()


def _foreign(db,value,table,label):
    if value in (None,''):return None
    if isinstance(value,bool) or not isinstance(value,int) or not db.execute(f'SELECT 1 FROM {table} WHERE id=?',(value,)).fetchone():
        raise AssetError(f'{label} wurde nicht gefunden. Bitte neu auswählen.')
    return value


def _values(db,payload,existing,*,parse_fields,validate_specs):
    if not isinstance(payload,dict):raise AssetError('Bitte gültige Assetdaten eingeben.')
    source={**(existing or {}),**payload}
    result={}
    for key,label,maximum in [('name','Name',240),('serial_number','Inventar-/Seriennummer',240),('notes','Beschreibung',20000),
            ('cost_center','Kostenstelle',240),('invoice_number','Rechnung',240),('retirement_reason','Ausmusterungsgrund',2000),('currency','Währung',3)]:
        result[key]=_text(source.get(key),label,maximum)
    if not result['name']:raise AssetError('Bitte einen Namen eingeben.',fields={'name':'Name ist erforderlich.'})
    for key,table,label in [('category_id','asset_categories','Kategorie'),('location_id','locations','Standort'),('vendor_id','vendors','Lieferant'),('purchase_order_id','purchase_orders','Bestellung')]:
        result[key]=_foreign(db,source.get(key),table,label)
    for key in ['acquisition_date','commissioning_date','warranty_end','retirement_date']:
        value=source.get(key) or None
        if value:
            try:value=date.fromisoformat(value).isoformat()
            except (ValueError,TypeError):raise AssetError('Bitte ein gültiges Datum eingeben.',fields={key:'Gültiges Datum erforderlich.'})
        result[key]=value
    for key in ['purchase_cost','depreciation_months']:
        value=source.get(key)
        if value in (None,''):result[key]=None;continue
        try:
            if isinstance(value,bool):raise ValueError
            number=float(value)
            if not math.isfinite(number) or number<0 or (key=='depreciation_months' and (number!=int(number) or number>1200)):raise ValueError
        except (ValueError,TypeError,OverflowError):raise AssetError('Bitte einen gültigen nicht negativen Wert eingeben.',fields={key:'Ungültiger Wert.'})
        result[key]=int(number) if key=='depreciation_months' else number
    fields={}
    if result['category_id']:
        fields=parse_fields(db.execute('SELECT fields FROM asset_categories WHERE id=?',(result['category_id'],)).fetchone()[0])
    raw=source.get('specs',{})
    # Existing extra/dynamic properties survive partial edits and category changes.
    specs=specs_object(existing.get('specs')) if existing else {}
    if not isinstance(raw,dict):
        if 'specs' in payload:raise AssetError('Eigenschaften müssen als Objekt übergeben werden.')
        raw=specs
    specs.update(raw)
    normalized,errors=validate_specs(specs,fields)
    if errors:raise AssetError('Bitte die markierten Eigenschaften prüfen.',fields=errors)
    if len(json.dumps(normalized,ensure_ascii=False))>65536:raise AssetError('Die Eigenschaften sind zu umfangreich.')
    result['specs']=json.dumps(normalized,ensure_ascii=False)
    return result


def get_asset(db,can,identifier):
    require(db,can,identifier)
    row=dict(db.execute('''SELECT a.*,c.name AS category,l.name AS location FROM assets a
        LEFT JOIN asset_categories c ON c.id=a.category_id LEFT JOIN locations l ON l.id=a.location_id WHERE a.id=?''',(identifier,)).fetchone())
    row['specs']=specs_object(row['specs']);row['revision']=version(db,identifier)
    row['can_edit']=can_access(db,can,identifier,write=True)
    predicate,args=scope_predicate(can)
    def linked(parent):
        return [dict(item) for item in db.execute(f'''SELECT a.id,a.name,a.serial_number,c.quantity,c.notes FROM asset_components c
            JOIN assets a ON a.id=c.{'child_asset_id' if parent else 'parent_asset_id'}
            WHERE c.{'parent_asset_id' if parent else 'child_asset_id'}=? AND {predicate} ORDER BY a.name,a.id''',[identifier,*args])]
    row['components']=linked(True);row['used_in']=linked(False)
    return row


def create_asset(db,can,payload,*,parse_fields,validate_specs):
    scope='assets' if can('assets.manage') else 'devices' if can('devices.manage') else None
    if not scope:raise AssetError('Keine Berechtigung zum Erfassen von Assets.',403)
    with mutation(db):
        values=_values(db,payload,None,parse_fields=parse_fields,validate_specs=validate_specs)
        identifier=db.execute('INSERT INTO assets('+','.join(values)+') VALUES ('+','.join('?' for _ in values)+')',list(values.values())).lastrowid
        db.execute('INSERT INTO asset_permission_scope(asset_id,scope) VALUES (?,?)',(identifier,scope))
        sync_object(db,'asset',identifier)
        return get_asset(db,can,identifier)


def update_asset(db,can,identifier,payload,*,parse_fields,validate_specs):
    with mutation(db):
        require(db,can,identifier,write=True);_check_revision(db,identifier,payload.get('expectedRevision'))
        existing=dict(db.execute('SELECT * FROM assets WHERE id=?',(identifier,)).fetchone())
        values=_values(db,payload,existing,parse_fields=parse_fields,validate_specs=validate_specs)
        db.execute('UPDATE assets SET '+','.join(key+'=?' for key in values)+' WHERE id=?',[*values.values(),identifier])
        sync_object(db,'asset',identifier)
        return get_asset(db,can,identifier)


def set_component(db,can,parent,child,quantity,notes,expected):
    with mutation(db):
        require(db,can,parent,write=True);require(db,can,child);_check_revision(db,parent,expected)
        if parent==child:raise AssetError('Ein Asset kann sich nicht selbst enthalten.')
        if isinstance(quantity,bool) or not isinstance(quantity,int) or not 1<=quantity<=1000000:raise AssetError('Die Menge muss eine ganze Zahl zwischen 1 und 1.000.000 sein.')
        notes=_text(notes,'Zuordnungsnotiz',6000)
        try:
            db.execute('''INSERT INTO asset_components(parent_asset_id,child_asset_id,quantity,notes) VALUES (?,?,?,?)
                ON CONFLICT(parent_asset_id,child_asset_id) DO UPDATE SET quantity=excluded.quantity,notes=excluded.notes''',(parent,child,quantity,notes))
        except sqlite3.IntegrityError as error:
            if 'asset_composition_cycle' in str(error):raise AssetError('Diese Zuordnung würde einen Kreis erzeugen. Ein enthaltenes Asset darf seinen übergeordneten Eintrag nicht wiederum enthalten.',409) from error
            raise
        return get_asset(db,can,parent)


def remove_component(db,can,parent,child,expected):
    with mutation(db):
        require(db,can,parent,write=True);require(db,can,child);_check_revision(db,parent,expected)
        if not db.execute('DELETE FROM asset_components WHERE parent_asset_id=? AND child_asset_id=?',(parent,child)).rowcount:raise AssetError('Die Zuordnung existiert nicht mehr.',404)
        return get_asset(db,can,parent)


def delete_asset(db,can,identifier,expected):
    with mutation(db):
        require(db,can,identifier,write=True);_check_revision(db,identifier,expected)
        if db.execute('SELECT 1 FROM asset_components WHERE child_asset_id=?',(identifier,)).fetchone():
            raise AssetError('Das Asset wird noch in anderen Assets verwendet. Bitte zuerst die Inhaltszuordnungen lösen oder das Asset ausmustern.',409)
        # Independent history/tickets/plans must be deliberately handled, never
        # silently removed by generic object deletion. Legacy backing rows stay.
        if db.execute('SELECT 1 FROM asset_legacy_devices WHERE asset_id=?',(identifier,)).fetchone():
            raise AssetError('Dieser übernommene Eintrag enthält historische Geräteverweise. Bitte zur Datenerhaltung ausmustern.',409)
        db.execute('SAVEPOINT asset_delete')
        try:db.execute('DELETE FROM assets WHERE id=?',(identifier,));db.execute('RELEASE SAVEPOINT asset_delete')
        except sqlite3.IntegrityError as error:
            db.execute('ROLLBACK TO SAVEPOINT asset_delete');db.execute('RELEASE SAVEPOINT asset_delete')
            raise AssetError('Das Asset wird noch von anderen Vorgängen verwendet. Bitte die Verknüpfungen prüfen oder das Asset ausmustern.',409) from error
