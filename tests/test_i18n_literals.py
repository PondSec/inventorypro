import pytest
from flask import Flask,g
from jinja2 import Environment,DictLoader
from inventorypro.i18n import InterfaceLanguage,InterfaceCodeGenerator,translate,literal,template_literals


@pytest.fixture
def translated(monkeypatch):
    import inventorypro.i18n as i18n
    monkeypatch.setattr(i18n.catalog,'_messages',{'Standort':'Location','Name & Nummer':'Name & number','Speichern':'Save','Hallo':'Hello'},raising=False)
    app=Flask(__name__)
    with app.test_request_context():g.ui_language='en';yield


def render(source,localized=True,**values):
    env=Environment(loader=DictLoader({'test.html':source}),autoescape=True,extensions=[InterfaceLanguage] if localized else [])
    env.globals.update(ui_t=translate,ui_literal=literal)
    return env.get_template('test.html').render(**values)


def test_only_static_ui_text_translates_and_model_values_remain_unchanged(translated):
    result=render('<label title="Standort">Standort</label><span>{{ name }}</span><input placeholder="Standort" value="{{ name }}">',name='Standort')
    assert '<label title="Location">Location</label>' in result
    assert '<span>Standort</span>' in result and 'value="Standort"' in result
    assert 'placeholder="Location"' in result


def test_scripts_styles_dynamic_attributes_and_escaping_remain_intact(translated):
    source='<script>const x="Standort";const value={{ value|tojson }};</script><style>.x{content:"Standort"}</style><p>Name &amp; Nummer</p><a title="{{ name }}">{{ name }}</a>'
    result=render(source,name='<unsafe>',value='Standort')
    assert 'const x="Standort"' in result and 'content:"Standort"' in result
    assert '<p>Name &amp; number</p>' in result and 'title="&lt;unsafe&gt;"' in result
    assert '<unsafe>' not in result


@pytest.mark.parametrize('source',[
 '<p> Standort </p>',
 '{% if flag %}<p>Hallo</p>{% else %}<b>Standort</b>{% endif %}',
 '<button aria-label="Speichern"> Speichern </button><span>{{ name }}</span>',
 '<p>&copy; Name &amp; Nummer &#169;</p>',
 '  {% set name="Standort" -%}  <p>{{name}}</p>\n',
 '<input title="{{name}} Standort"><!-- Standort --><p>Hallo</p>',
])
def test_german_template_rendering_is_unchanged(source):
    assert render(source,flag=True,name='QA name')==render(source,localized=False,flag=True,name='QA name')


def test_compiler_translates_macro_labels_but_preserves_dynamic_properties(translated):
    env=Environment(loader=DictLoader({'test.html':"{% macro property(label,value) %}<dt>{{label}}</dt><dd>{{value}}</dd>{% endmacro %}{% set page_title='Standort' %}<h1>{{page_title}}</h1>{{property('Standort',name)}}{{property(field_name,name)}}"}),autoescape=True,extensions=[InterfaceLanguage])
    env.code_generator_class=InterfaceCodeGenerator;env.globals.update(ui_t=translate,ui_literal=literal)
    assert env.get_template('test.html').render(name='Standort',field_name='Standort')=='<h1>Location</h1><dt>Location</dt><dd>Standort</dd><dt>Standort</dt><dd>Standort</dd>'


def test_pattern_translation_preserves_whitespace_and_inserted_values(translated,monkeypatch):
    import inventorypro.i18n as i18n
    monkeypatch.setattr(i18n.catalog,'_messages',{'Menge für {0}':'Quantity for {0}'})
    assert translate('  Menge für Standort \n')=='  Quantity for Standort \n'


def test_english_catalog_preserves_placeholders_and_core_vocabulary():
    import json,re
    from inventorypro.i18n import CATALOG_PATH
    messages=json.loads(CATALOG_PATH.read_text())
    assert messages['Abbrechen']=='Cancel' and messages['Speichern']=='Save'
    assert messages['Berechtigungen']=='Permissions' and messages['Sicherung']=='Backup'
    for key,value in messages.items():
        assert isinstance(value,str) and value.strip(),key
        assert sorted(re.findall(r'\{\d+\}',key))==sorted(re.findall(r'\{\d+\}',value)),key
