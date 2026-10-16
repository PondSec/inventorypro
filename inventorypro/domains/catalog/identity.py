"""Recognize public product identities without sending free-form names abroad.

Only complete, bounded product patterns are inferred. Unrecognized inventory
names, owner suffixes and locations never become external search terms.
"""
import re
from .matching import identity_from_specs, manufacturer_key, _name_without_inventory_suffix

PATTERNS = (
    ('Apple', r'(?:Apple\s+)?(AirPods\s+(?:Pro\s+)?[1-4](?:\s+ANC)?)'),
    ('Apple', r'(?:Apple\s+)?(iPhone\s+\d{1,2}(?:\s+(?:Pro\s+Max|Pro|Plus|mini))?)(?:\s+(?:64|128|256|512)\s*GB|\s+[12]\s*TB)?'),
    ('Apple', r'(?:Apple\s+)?(MacBook\s+(?:Air|Pro)\s+(?:13|14|15|16)(?:\s*(?:"|Zoll|inch))?\s+M[1-5](?:\s+(?:Pro|Max))?)'),
    ('Logitech', r'(?:Logitech\s+)?(MX\s+Master\s+[23]S?)'),
    ('Samsung', r'Samsung\s+(Galaxy\s+(?:S\d{2}|A\d{2})(?:\s+(?:Ultra|Plus|FE))?)'),
    ('Lenovo', r'Lenovo\s+(ThinkPad\s+[A-Z]\d{2,3}(?:\s+Gen\s+\d{1,2})?)'),
    ('Dell', r'Dell\s+((?:OptiPlex|Latitude|Precision)\s+\d{4}(?:\s+(?:Micro|SFF|Tower))?)'),
    ('Bosch', r'Bosch\s+((?:GSR|GSB|GWS|GST|GKS)\s+\d{1,3}(?:[A-Z]{1,3})?(?:-\d{1,3})?(?:\s+[A-Z]{1,3})?)'),
    ('DeWalt', r'(?:DeWalt\s+)(DCD\d{3}(?:[A-Z]\d?)?)'),
)


def inferred_name(name):
    candidate = _name_without_inventory_suffix(name).replace('″', '"').replace('”', '"').strip()
    for maker, pattern in PATTERNS:
        match = re.fullmatch(pattern, candidate, re.IGNORECASE)
        if match:
            model = re.sub(r'\s+', ' ', re.sub(r'\s*(?:"|\bZoll\b|\binch\b)', '', match[1], flags=re.IGNORECASE)).strip()
            return {'manufacturer': maker, 'model': model}
    return None


def for_object(specs, name):
    identity = identity_from_specs(specs)
    if identity['model'] or identity['model_code'] or identity['mpn'] or identity['gtin']:
        return identity
    inferred = inferred_name(name)
    if inferred and (not identity['manufacturer'] or manufacturer_key(identity['manufacturer']) == manufacturer_key(inferred['manufacturer'])):
        identity.update(inferred)
    return identity
