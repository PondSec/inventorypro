"""Conservative Wikidata identities plus licensed Commons images.

Only public product fields are accepted. Inventory names, serial numbers, people,
locations and credentials are never used to construct a provider query.
"""
from html.parser import HTMLParser
import re
from urllib.parse import urlencode, quote

from .matching import compact, manufacturer_key, valid_gtin
from .network import fetch_json, validate_url, IMAGE_HOSTS, ProviderError

WIKIDATA='https://www.wikidata.org/w/api.php?'
COMMONS='https://commons.wikimedia.org/w/api.php?'


class PlainText(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[]
    def handle_data(self,data):self.parts.append(data)


def plain(value,limit=2000):
    parser=PlainText();parser.feed(str(value or '')[:12000])
    return ' '.join(' '.join(parser.parts).split())[:limit]


def public_identity(value):
    """Whitelist keys rather than passing any object payload to the provider."""
    if not isinstance(value,dict):return None
    fields={key:' '.join(str(value.get(key) or '').split())[:240] for key in ['manufacturer','model','model_code','mpn','gtin']}
    if not manufacturer_key(fields['manufacturer']):return None
    if not fields['model'] and not valid_gtin(fields['gtin']):return None
    if any(ord(char)<32 for char in ''.join(fields.values())):return None
    return fields


def values(entity,property_id):
    result=[]
    for claim in entity.get('claims',{}).get(property_id,[]):
        if claim.get('rank')=='deprecated':continue
        snak=claim.get('mainsnak',{})
        if snak.get('snaktype')!='value':continue
        value=snak.get('datavalue',{}).get('value')
        if value is not None:result.append(value)
    return result


def names(entity):
    result=[label.get('value','') for label in entity.get('labels',{}).values()]
    for labels in entity.get('aliases',{}).values():result.extend(label.get('value','') for label in labels)
    return [value for value in result if isinstance(value,str) and value]


def entity_data(ids):
    if not ids:return {}
    data=fetch_json(WIKIDATA+urlencode({'action':'wbgetentities','ids':'|'.join(ids),'props':'labels|aliases|claims','languages':'en|de','format':'json'}))
    return {key:value for key,value in data.get('entities',{}).items() if key in ids and isinstance(value,dict) and 'missing' not in value}


def _exact(identity,entity,makers):
    maker=manufacturer_key(identity['manufacturer'])
    references=values(entity,'P176')+values(entity,'P1716')
    manufacturer_matches=any(isinstance(ref,dict) and any(manufacturer_key(name)==maker for name in names(makers.get(ref.get('id'),{}))) for ref in references)
    if not manufacturer_matches:return False
    gtin=valid_gtin(identity['gtin'])
    source_codes={valid_gtin(code) for code in values(entity,'P3962') if isinstance(code,str)}-{None}
    if gtin and source_codes:return gtin in source_codes
    model=compact(identity['model'])
    # Exact full names/aliases only; a manufacturer prefix may be present in
    # the public label. Generation, size, suffix and digits remain significant.
    if len(model)<5 or not any(c.isdigit() for c in model):return False
    candidates={compact(name) for name in names(entity)}
    return model in candidates or compact(identity['manufacturer']+identity['model']) in candidates


def image_info(filename):
    if not isinstance(filename,str) or not filename or len(filename)>240 or any(c in filename for c in '|\r\n'):return None
    data=fetch_json(COMMONS+urlencode({'action':'query','format':'json','titles':'File:'+filename,
        'prop':'imageinfo','iiprop':'url|mime|size|extmetadata','iiurlwidth':960,'iiurlheight':960,
        'iiextmetadatafilter':'Artist|Credit|LicenseShortName|LicenseUrl|UsageTerms|Restrictions','iiextmetadatalanguage':'en'}))
    pages=data.get('query',{}).get('pages',{})
    for page in pages.values():
        infos=page.get('imageinfo',[])
        if not infos:continue
        info=infos[0];metadata=info.get('extmetadata',{})
        get=lambda key:plain(metadata.get(key,{}).get('value',''))
        short=get('LicenseShortName').casefold().replace('_',' ')
        license_url=get('LicenseUrl').replace('http://','https://')
        match=re.fullmatch(r'https://creativecommons.org/licenses/(by|by-sa)/(1\.0|2\.0|2\.5|3\.0|4\.0)/?',license_url)
        if match and short in {f'cc {match[1]} {match[2]}',f'cc-{match[1]}-{match[2]}'}:
            license_code='CC-'+match[1].upper()+'-'+match[2]
        elif license_url.rstrip('/')=='https://creativecommons.org/publicdomain/zero/1.0' and short in {'cc0','cc0 1.0','cc-zero'}:
            license_code='CC0-1.0'
        else:return None
        if get('Restrictions'):return None
        artist=get('Artist')
        if license_code!='CC0-1.0' and not artist:return None
        url=info.get('thumburl') or info.get('url','')
        validate_url(url,IMAGE_HOSTS)
        mime=info.get('thumbmime') or info.get('mime','')
        if mime not in {'image/png','image/jpeg','image/webp'}:return None
        return {'image_url':url,'mime':mime,'source_kind':'commons','source_ref':page.get('title','File:'+filename),
            'source_url':'https://commons.wikimedia.org/wiki/'+quote(page.get('title','File:'+filename).replace(' ','_'),safe=':'),
            'license_code':license_code,'attribution':artist or get('Credit') or 'Wikimedia Commons (CC0)',
            'changes':'Sicher neu kodiert und skaliert; Metadaten entfernt.','license_url':license_url}
    return None


def lookup(identity):
    identity=public_identity(identity)
    if not identity:return {'status':'insufficient','candidates':[]}
    query=(identity['manufacturer']+' '+identity['model']).strip() if identity['model'] else identity['gtin']
    data=fetch_json(WIKIDATA+urlencode({'action':'wbsearchentities','search':query,'language':'en','format':'json','limit':3,'type':'item'}))
    ids=[row['id'] for row in data.get('search',[]) if re.fullmatch(r'Q[1-9]\d*',str(row.get('id','')))][:3]
    entities=entity_data(ids)
    maker_ids=list(dict.fromkeys(ref['id'] for entity in entities.values() for ref in values(entity,'P176')+values(entity,'P1716')
        if isinstance(ref,dict) and re.fullmatch(r'Q[1-9]\d*',str(ref.get('id','')))))[:12]
    makers=entity_data(maker_ids)
    candidates=[{'source_ref':identifier,'name':names(entity)[0] if names(entity) else identifier,
        'source_url':'https://www.wikidata.org/wiki/'+identifier,'exact':_exact(identity,entity,makers)} for identifier,entity in entities.items()]
    exact=[candidate for candidate in candidates if candidate['exact']]
    if len(exact)!=1:return {'status':'ambiguous' if exact else 'no_match','candidates':candidates}
    candidate=exact[0];entity=entities[candidate['source_ref']]
    pictures=values(entity,'P18')
    if not pictures:return {'status':'no_image','candidates':candidates}
    image=image_info(pictures[0])
    if image is None:return {'status':'unlicensed','candidates':candidates}
    return {'status':'matched','candidates':candidates,'identity':identity,'entity':candidate,'image':image}
