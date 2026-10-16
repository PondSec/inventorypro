import pytest
import app as inventory_app
from inventorypro.domains.inventory import assets
from inventorypro.domains.inventory.unification import convert_inventory
from inventorypro.domains.wishes import service as wishes


@pytest.fixture
def db(isolated_inventory):
    with isolated_inventory.app_context():
        db = inventory_app.get_db()
        convert_inventory(db)
        db.commit()
        yield db


def can(key):
    return True


def actor(db):
    return db.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]


def save(db, **values):
    return wishes.save_wish(db, can, actor(db), {'name': 'Workbench', **values})


def acquire(db, row, **values):
    return wishes.acquire(db, can, actor(db), row['id'], {'expectedRevision': row['revision'], 'requestKey': 'synthetic-request-001', **values},
                          parse_fields=inventory_app.parse_field_definitions, validate_specs=inventory_app.validate_dynamic_specs)


def test_general_wishes_are_separate_until_acquired_and_retry_is_idempotent(db):
    before = db.execute('SELECT count(*) FROM assets').fetchone()[0]
    row = save(db, name='Garden chair', quantity=3, unit_price='24,95', notes='Weatherproof')
    assert row['missing'] == 3 and row['owned'] == 0
    assert db.execute('SELECT count(*) FROM assets').fetchone()[0] == before
    owned = acquire(db, row, quantity=2)
    assert owned['missing'] == 1 and owned['owned'] == 2
    assert db.execute('SELECT count(*) FROM assets').fetchone()[0] == before + 2
    assert acquire(db, row, quantity=2)['owned'] == 2
    with pytest.raises(wishes.WishError):
        acquire(db, owned, quantity=2, requestKey='synthetic-request-002')
    done = acquire(db, owned, requestKey='synthetic-request-003')
    assert done['missing'] == 0 and done['owned'] == 3


def test_private_records_cannot_be_read_or_written_by_another_manager(db):
    row = save(db)
    other = db.execute("INSERT INTO users(username,password_hash) VALUES ('researcher','synthetic')").lastrowid
    with pytest.raises(wishes.WishError) as problem:
        wishes.wish(db, can, other, row['id'])
    assert problem.value.status == 404
    with pytest.raises(wishes.WishError):
        wishes.save_wish(db, can, other, {'name': 'Changed', 'expectedRevision': row['revision']}, row['id'])
    shared = wishes.save_wish(db, can, actor(db), {'visibility': 'team', 'expectedRevision': row['revision']}, row['id'])
    assert wishes.wish(db, can, other, row['id'])['name'] == 'Workbench'
    with pytest.raises(wishes.WishError):
        wishes.save_wish(db, can, other, {'visibility': 'private', 'expectedRevision': shared['revision']}, row['id'])


def test_project_visibility_is_inherited_and_removal_preserves_wishes(db):
    parent = wishes.save_project(db, can, actor(db), {'name': 'Workshop', 'visibility': 'team'})
    row = save(db, project_id=parent['id'])
    other = db.execute("INSERT INTO users(username,password_hash) VALUES ('colleague','synthetic')").lastrowid
    assert wishes.wish(db, can, other, row['id'])['effective_visibility'] == 'team'
    wishes.remove(db, can, actor(db), 'projects', parent['id'], {'expectedRevision': parent['revision']})
    assert wishes.wish(db, can, actor(db), row['id'])['project_id'] is None
    with pytest.raises(wishes.WishError):
        wishes.wish(db, can, other, row['id'])


@pytest.mark.parametrize('payload', [{'unit_price': '-1'}, {'unit_price': 'NaN'}, {'unit_price': 'Infinity'}, {'unit_price': '0.001'},
    {'quantity': True}, {'quantity': 0}, {'quantity': 1.5}, {'url': 'javascript:alert(1)'}, {'url': 'https://user:secret@example.com'},
    {'currency': 'eur'}, {'priority': 'invalid'}, {'name': ''}])
def test_invalid_research_is_rejected_without_partial_rows(db, payload):
    with pytest.raises(assets.AssetError):
        save(db, **payload)
    assert db.execute('SELECT count(*) FROM wishes').fetchone()[0] == 0


def test_acquisition_rolls_back_all_units_on_invalid_serial_numbers(db):
    row = save(db, quantity=2)
    before = db.execute('SELECT count(*) FROM assets').fetchone()[0]
    with pytest.raises(wishes.WishError):
        acquire(db, row, quantity=2, serial_number='UNIQUE-SERIAL')
    assert db.execute('SELECT count(*) FROM assets').fetchone()[0] == before
    assert wishes.wish(db, can, actor(db), row['id'])['owned'] == 0


def test_inventory_permission_is_separate_from_research_permission(db):
    row = save(db)
    limited = lambda key: key in {'wishes.view', 'wishes.manage'}
    with pytest.raises(assets.AssetError) as problem:
        wishes.acquire(db, limited, actor(db), row['id'], {'expectedRevision': row['revision'], 'requestKey': 'synthetic-request-004'},
            parse_fields=inventory_app.parse_field_definitions, validate_specs=inventory_app.validate_dynamic_specs)
    assert problem.value.status == 403


def test_project_assembly_is_atomic_real_composition_and_idempotent(db):
    parent = wishes.save_project(db, can, actor(db), {'name': 'Workshop', 'budget': '400.00'})
    row = save(db, project_id=parent['id'], quantity=2, name='Workbench')
    arguments = dict(parse_fields=inventory_app.parse_field_definitions, validate_specs=inventory_app.validate_dynamic_specs)
    with pytest.raises(wishes.WishError):
        wishes.assemble(db, can, actor(db), parent['id'], {'expectedRevision': parent['revision']}, **arguments)
    row = acquire(db, row, quantity=2)
    assembled = wishes.assemble(db, can, actor(db), parent['id'], {'expectedRevision': parent['revision']}, **arguments)
    assert len(assets.get_asset(db, can, assembled['asset_id'])['components']) == 2
    assert wishes.assemble(db, can, actor(db), parent['id'], {'expectedRevision': parent['revision']}, **arguments)['asset_id'] == assembled['asset_id']
    with pytest.raises(wishes.WishError):
        wishes.save_wish(db, can, actor(db), {'expectedRevision': row['revision'], 'name': 'Changed'}, row['id'])
    assert not db.execute('PRAGMA foreign_key_check').fetchall()


def test_deleting_owned_asset_reopens_missing_quantity_without_losing_research(db):
    row = acquire(db, save(db, notes='Keep my research'))
    owned = assets.get_asset(db, can, row['acquisitions'][0]['asset_id'])
    assets.delete_asset(db, can, owned['id'], owned['revision'])
    result = wishes.wish(db, can, actor(db), row['id'])
    assert result['missing'] == 1 and result['notes'] == 'Keep my research'
    assert result['acquisitions'][0]['asset_id'] is None
    wishes.remove(db, can, actor(db), 'wishes', row['id'], {'expectedRevision': result['revision']})
    assert not db.execute('SELECT 1 FROM wish_acquisitions').fetchone()


def test_existing_asset_can_only_fulfil_one_wish(db):
    original = assets.create_asset(db, can, {'name': 'Owned hand tool'}, parse_fields=inventory_app.parse_field_definitions, validate_specs=inventory_app.validate_dynamic_specs)
    one = save(db, name='Hand tool')
    result = acquire(db, one, asset_id=original['id'])
    assert result['acquisitions'][0]['asset_id'] == original['id']
    two = save(db, name='Another hand tool')
    with pytest.raises(wishes.WishError):
        acquire(db, two, asset_id=original['id'], requestKey='synthetic-request-005')
    assert wishes.wish(db, can, actor(db), two['id'])['missing'] == 1


def test_currency_and_stale_edit_guards(db):
    parent = wishes.save_project(db, can, actor(db), {'name': 'Workshop'})
    with pytest.raises(wishes.WishError):
        save(db, project_id=parent['id'], currency='USD')
    row = save(db, project_id=parent['id'])
    with pytest.raises(wishes.WishError):
        wishes.save_project(db, can, actor(db), {'currency': 'USD', 'expectedRevision': parent['revision']}, parent['id'])
    with pytest.raises(wishes.WishError):
        wishes.save_wish(db, can, actor(db), {'name': 'Stale', 'expectedRevision': row['revision'] + 1}, row['id'])


def test_releasing_an_accidental_acquisition_keeps_inventory_and_replay_protection(db):
    original = save(db)
    row = acquire(db, original)
    record = row['acquisitions'][0]
    released = wishes.release(db, can, actor(db), row['id'], record['id'], {'expectedRevision': row['revision']})
    assert released['missing'] == 1
    assert assets.get_asset(db, can, record['asset_id'])['name'] == 'Workbench'
    assert acquire(db, original)['missing'] == 1
    with pytest.raises(wishes.WishError):
        wishes.release(db, can, actor(db), row['id'], record['id'], {'expectedRevision': row['revision']})
