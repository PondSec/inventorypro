import pytest
from inventorypro.domains.catalog import commons
from inventorypro.domains.catalog.network import ProviderError


def claim(value):return {'mainsnak':{'snaktype':'value','datavalue':{'value':value}}}


def entity(name,**claims):return {'labels':{'en':{'value':name}},'claims':{key:[claim(value)] for key,value in claims.items()}}


def fixture_api(monkeypatch,*,name='Logitech MX Master 3S',manufacturer='Logitech',license='CC BY-SA 4.0',license_url='https://creativecommons.org/licenses/by-sa/4.0/',image_url='https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Mouse.jpg/960px-Mouse.jpg',**metadata):
    queries=[]
    def api(url):
        from urllib.parse import parse_qs,urlsplit
        query=parse_qs(urlsplit(url).query);queries.append(query)
        if query['action']==['wbsearchentities']:return {'search':[{'id':'Q123'}]}
        if query['action']==['wbgetentities']:
            if query['ids']==['Q123']:return {'entities':{'Q123':entity(name,P176={'id':'Q1'},P18='Mouse.jpg')}}
            return {'entities':{'Q1':entity(manufacturer)}}
        return {'query':{'pages':{'1':{'title':'File:Mouse.jpg','imageinfo':[{'thumburl':image_url,'thumbmime':'image/jpeg','extmetadata':{
            key:{'value':value} for key,value in {'Artist':'<a href="https://example.invalid">QA Author</a>','LicenseShortName':license,'LicenseUrl':license_url,**metadata}.items()}}]}}}}
    monkeypatch.setattr(commons,'fetch_json',api);return queries


def identity(**values):return {'manufacturer':'Logitech','model':'MX Master 3S',**values}


def test_exact_public_model_and_licensed_image_with_plain_attribution(monkeypatch):
    queries=fixture_api(monkeypatch)
    result=commons.lookup(identity(serial_number='PRIVATE-SERIAL',location='PRIVATE-ROOM',owner='PRIVATE-PERSON',name='PRIVATE-ASSET'))
    assert result['status']=='matched' and result['image']['license_code']=='CC-BY-SA-4.0'
    assert result['image']['attribution']=='QA Author' and '<a' not in result['image']['attribution']
    assert 'PRIVATE' not in str(queries) and 'PRIVATE' not in str(result)


@pytest.mark.parametrize('values',[{'model':'MX Master 3'},{'manufacturer':'Other'},{'model':'MX Master'},{'model':'3S'},{'model':''}])
def test_wrong_generation_manufacturer_and_partial_names_never_auto_match(monkeypatch,values):
    fixture_api(monkeypatch)
    assert commons.lookup(identity(**values))['status']!='matched'


@pytest.mark.parametrize('metadata',[
    {'license':'All rights reserved','license_url':'https://example.com/license'},
    {'license':'CC BY-NC 4.0','license_url':'https://creativecommons.org/licenses/by-nc/4.0/'},
    {'license':'CC BY-SA 4.0','license_url':'https://evil.example/by-sa/4.0/'},
    {'Restrictions':'Non-free'}, {'Artist':''},
])
def test_missing_unsupported_or_restricted_rights_rejected(monkeypatch,metadata):
    fixture_api(monkeypatch,**metadata)
    assert commons.lookup(identity())['status']=='unlicensed'


def test_private_media_host_is_rejected_before_image_download(monkeypatch):
    fixture_api(monkeypatch,image_url='http://169.254.169.254/latest/meta-data')
    with pytest.raises(ProviderError):commons.lookup(identity())


def test_cc0_explicit_license_and_no_artist_is_accepted(monkeypatch):
    fixture_api(monkeypatch,license='CC0',license_url='https://creativecommons.org/publicdomain/zero/1.0/',Artist='')
    assert commons.lookup(identity())['image']['license_code']=='CC0-1.0'


def test_gtin_only_identity_requires_and_returns_the_actual_public_identifier(monkeypatch):
    fixture_api(monkeypatch);original=commons.fetch_json
    def api(url):
        result=original(url)
        if 'ids=Q123' in url:result['entities']['Q123']['claims']['P3962']=[claim('4006381333931')]
        return result
    monkeypatch.setattr(commons,'fetch_json',api)
    result=commons.lookup(identity(model='',gtin='4006381333931'))
    assert result['status']=='matched' and result['entity']['verified_gtin']=='4006381333931'
    assert commons.lookup(identity(model='',gtin='5901234123457'))['status']=='no_match'


def test_two_exact_entities_remain_ambiguous(monkeypatch):
    fixture_api(monkeypatch)
    original=commons.fetch_json
    def api(url):
        result=original(url.replace('ids=Q123%7CQ124','ids=Q123'))
        if 'wbsearchentities' in url:result['search'].append({'id':'Q124'})
        if 'ids=Q123%7CQ124' in url:result['entities']['Q124']=result['entities']['Q123']
        return result
    monkeypatch.setattr(commons,'fetch_json',api)
    assert commons.lookup(identity())['status']=='ambiguous'


def test_localized_official_cc0_deed_is_accepted(monkeypatch):
    fixture_api(monkeypatch,license='CC0',license_url='http://creativecommons.org/publicdomain/zero/1.0/deed.en')
    result=commons.lookup(identity())
    assert result['status']=='matched' and result['image']['license_code']=='CC0-1.0'


@pytest.mark.parametrize('title,expected', [
    ('File:AirPods 4 ANC and case.jpg',True), ('File:Apple AirPods 4 ANC.jpg',True),
    ('File:AirPods 4 and AirPods Pro 2.jpg',False), ('File:Airpods 4.jpg',False),
    ('File:AirPods 4 ANC 2.jpg',False), ('File:AirPods Pro 2.jpg',False)])
def test_commons_titles_preserve_generation_variant_and_exclude_comparisons(title,expected):
    assert commons._title_matches(identity(manufacturer='Apple',model='AirPods 4 ANC'),title) is expected


def test_exact_commons_photo_without_wikidata_entity_is_found(monkeypatch):
    queries=fixture_api(monkeypatch,license='CC0',license_url='https://creativecommons.org/publicdomain/zero/1.0/deed.en')
    original=commons.fetch_json
    def api(url):
        if 'wbsearchentities' in url:return {'search':[]}
        if 'list=search' in url:return {'query':{'search':[{'title':'File:AirPods 4 ANC and case.jpg'},{'title':'File:AirPods 4 and AirPods Pro 2.jpg'}]}}
        return original(url)
    monkeypatch.setattr(commons,'fetch_json',api)
    result=commons.lookup(identity(manufacturer='Apple',model='AirPods 4 ANC'))
    assert result['status']=='matched' and result['entity']['source_kind']=='commons'
    assert result['entity']['source_ref']=='File:AirPods 4 ANC and case.jpg'
