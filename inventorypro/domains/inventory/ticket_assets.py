"""Canonical ticket links retain hidden existing links without exposing objects."""
from . import assets


def normalize_links(db,can,values,*,existing=()):
    if not assets.unified(db):return values
    if not isinstance(values,list) or len(values)>1000:
        raise assets.AssetError('Bitte eine gültige Liste mit höchstens 1000 Assets angeben.')
    identifiers=set()
    previous=set(existing)
    for value in values:
        if isinstance(value,bool) or not isinstance(value,(int,str)) or not str(value).isdigit() or int(value)<=0:
            raise assets.AssetError('Bitte gültige Asset-IDs auswählen.')
        identifier=int(value)
        # Links already present on a visible ticket must survive an edit by a
        # user who cannot read every linked asset. New links always require read.
        if identifier not in previous:assets.require(db,can,identifier)
        identifiers.add(identifier)
    for identifier in previous:
        if not assets.can_access(db,can,identifier):identifiers.add(identifier)
    return sorted(identifiers)
