"""Validated length units and guided inputs for the existing packing algorithm."""
import json
import math
import re
import unicodedata

UNITS = {'mm': 1.0, 'cm': 10.0, 'm': 1000.0, 'in': 25.4}
AXES = ('width', 'height', 'depth')
ALIASES = {'width': {'breite', 'width', 'w'}, 'height': {'hohe', 'hoehe', 'height', 'h'},
           'depth': {'tiefe', 'depth', 'lange', 'laenge', 'length', 'd'}}
MAX_ITEMS = 200


class PlanningError(ValueError):
    pass


def positive_number(value, label, *, zero=False):
    if isinstance(value, bool):
        raise PlanningError(f'{label}: Zahl erwartet.')
    try:
        number = float(str(value).strip().replace(',', '.'))
    except (TypeError, ValueError):
        raise PlanningError(f'{label}: Bitte ein gültiges Maß eingeben.') from None
    if not math.isfinite(number) or number < 0 or (number == 0 and not zero) or number > 1000000:
        raise PlanningError(f'{label}: Maß muss {"mindestens 0" if zero else "größer als 0"} und höchstens 1.000.000 sein.')
    return number


def normalized_words(value):
    text = ''.join(char for char in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(char))
    return set(re.findall(r'[a-z]+', text))


def dimension_suggestions(specs, fields):
    """Only infer unambiguous names; preserve unknown units for explicit review."""
    try:
        specs = json.loads(specs) if isinstance(specs, str) else specs
        fields = json.loads(fields) if isinstance(fields, str) else fields
    except (ValueError, TypeError):
        return {'dimensions': {}, 'fields': [], 'warnings': ['Vorhandene Felder konnten nicht gelesen werden.']}
    specs = specs if isinstance(specs, dict) else {}
    fields = fields if isinstance(fields, dict) else {}
    candidates, warnings, dimensions = [], [], {}
    for name, raw in specs.items():
        config = fields.get(name, {})
        config = config if isinstance(config, dict) else {}
        try:
            value = positive_number(raw, name)
        except PlanningError:
            continue
        words = normalized_words(name)
        unit = str(config.get('unit') or '').strip().lower()
        embedded = words.intersection(UNITS)
        if not unit and len(embedded) == 1:
            unit = embedded.pop()
        # Unlabelled values are presented as mm; users confirm the unit in step 2.
        unit = unit or 'mm'
        if unit not in UNITS:
            warnings.append(f'{name}: Einheit „{unit}“ bitte manuell prüfen.')
            continue
        candidates.append({'name': name, 'value_mm': value * UNITS[unit], 'unit': unit, 'axes': [axis for axis in AXES if words.intersection(ALIASES[axis])]})
    for axis in AXES:
        matches = [field for field in candidates if axis in field['axes']]
        if len(matches) == 1:
            dimensions[axis] = matches[0]['value_mm']
        elif len(matches) > 1:
            warnings.append(f'{axis}: Mehrere geeignete Felder; bitte das Maß bestätigen.')
    return {'dimensions': dimensions, 'fields': candidates, 'warnings': warnings}


def compute_plan(db, payload, *, pack, build_layers, enrich_layers):
    if not isinstance(payload, dict):
        raise PlanningError('JSON-Objekt erwartet.')
    try:
        json.dumps(payload, allow_nan=False)
    except (ValueError, TypeError):
        raise PlanningError('Ungültige oder nicht endliche Eingabewerte.') from None
    unit = payload.get('unit', 'mm')
    if not isinstance(unit, str) or unit not in UNITS:
        raise PlanningError('Maßeinheit muss mm, cm, m oder in sein.')
    factor = UNITS[unit]
    container = payload.get('container')
    if not isinstance(container, dict):
        raise PlanningError('Bitte die Behältermaße erfassen.')
    dimensions = {axis: positive_number(container.get(axis), f'Behälter {axis}') * factor for axis in AXES}
    clearance = positive_number(payload.get('clearance', 0), 'Wandabstand', zero=True) * factor
    gap = positive_number(payload.get('gap', 0), 'Abstand zwischen Gegenständen', zero=True) * factor
    effective = {axis: value - 2 * clearance for axis, value in dimensions.items()}
    if any(value <= 0 for value in effective.values()):
        raise PlanningError('Der Wandabstand lässt keinen nutzbaren Innenraum übrig.')
    rotation = payload.get('allow_rotation', True)
    if not isinstance(rotation, bool):
        raise PlanningError('Rotation muss ein Wahrheitswert sein.')
    selected = payload.get('items')
    if not isinstance(selected, list) or not selected or len(selected) > MAX_ITEMS:
        raise PlanningError(f'Bitte 1 bis {MAX_ITEMS} Gegenstände wählen.')
    items, seen, total = [], set(), 0
    container_id = payload.get('container_id')
    if container_id is not None:
        if isinstance(container_id, bool) or not isinstance(container_id, int):
            raise PlanningError('Ungültiger Behälter.')
        if not db.execute('SELECT 1 FROM assets WHERE id=?', (container_id,)).fetchone():
            raise PlanningError('Der Behälter existiert nicht mehr.')
    for item in selected:
        if not isinstance(item, dict):
            raise PlanningError('Ungültiger Gegenstand.')
        identifier, quantity = item.get('id'), item.get('quantity', 1)
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier in seen:
            raise PlanningError('Gegenstände müssen eindeutige gültige Inventareinträge sein.')
        if identifier == container_id:
            raise PlanningError('Der Behälter kann nicht in sich selbst eingeräumt werden.')
        seen.add(identifier)
        row = db.execute('SELECT name FROM assets WHERE id=?', (identifier,)).fetchone()
        if not row:
            raise PlanningError('Ein ausgewählter Gegenstand existiert nicht mehr.')
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise PlanningError('Mengen müssen positive ganze Zahlen sein.')
        total += quantity
        if total > MAX_ITEMS:
            raise PlanningError(f'Maximal {MAX_ITEMS} Stück pro Planung sind zulässig.')
        raw = item.get('dimensions')
        if not isinstance(raw, dict):
            raise PlanningError(f'{row["name"]}: Abmessungen fehlen.')
        physical = {axis: positive_number(raw.get(axis), f'{row["name"]}: {axis}') * factor for axis in AXES}
        for index in range(quantity):
            items.append({'id': identifier, 'name': row['name'] + (f' ({index+1}/{quantity})' if quantity > 1 else ''),
                          'dimensions': {axis: value + gap for axis, value in physical.items()}})
    placements, unplaced, metadata = pack({axis: value + gap for axis, value in effective.items()}, items, rotation)
    for placement in placements:
        for axis in AXES:
            placement[axis] = max(0, placement[axis] - gap)
        for coordinate in ('x', 'y', 'z'):
            placement[coordinate] += clearance
        placement['original_dimensions'] = {axis: value-gap for axis,value in placement['original_dimensions'].items()}
        placement['orientation_label'] = ' × '.join(f'{placement[axis]:g}' for axis in AXES) + ' mm'
    layers = build_layers(placements)
    steps = enrich_layers(dimensions, layers)
    volume = math.prod(dimensions.values())
    used = sum(math.prod(p[axis] for axis in AXES) for p in placements)
    return {
        'enabled': True, 'status': 'ready', 'unit': 'mm', 'allow_rotation': rotation,
        'container': {**dimensions, 'volume': volume}, 'placements': placements, 'layers': layers, 'steps': steps,
        'placed_count': len(placements), 'total_count': total, 'unplaced_count': len(unplaced), 'invalid_count': 0,
        'layer_count': len(layers), 'step_count': len(steps), 'next_step': steps[0] if steps else None,
        'used_height': max((p['z']+p['height'] for p in placements), default=0),
        'used_volume': used, 'free_volume': max(0, volume-used), 'efficiency_percent': round(used/volume*100, 1),
        'used_height_percent': round(max((p['z']+p['height'] for p in placements),default=0)/dimensions['height']*100,1),
        'content_category_name': 'Ausgewählte Gegenstände', 'packing_strategy': metadata['strategy_key'],
        'algorithm_label': metadata['algorithm_label'], 'packing_strategy_label': metadata['strategy_label'],
        'plan_status': 'complete' if not unplaced else 'partial',
        'plan_status_label': 'Vollständig eingeplant' if not unplaced else 'Teilweise eingeplant',
        'unplaced_assets': [{'id': item['id'], 'name': item['name'], 'dimensions': {axis: item['dimensions'][axis]-gap for axis in AXES}} for item in unplaced], 'invalid_assets': [],
        'message': 'Heuristischer Packvorschlag; keine Garantie für eine optimale Lösung. Tragfähigkeit und sichere Handhabung vor Ort prüfen.',
    }
