"""Local interface translations. Inventory values are never sent to a translator."""
from __future__ import annotations

import html
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3

from flask import g, has_request_context,request
from jinja2 import Environment,nodes
from jinja2.compiler import CodeGenerator
from jinja2.ext import Extension
from markupsafe import Markup, escape

SUPPORTED_LANGUAGES=('de','en')
CATALOG_PATH=Path(__file__).resolve().parents[1]/'static'/'locale-en.json'


def catalog():
    if not hasattr(catalog,'_messages'):
        catalog._messages=json.loads(CATALOG_PATH.read_text()) if CATALOG_PATH.exists() else {}
    return catalog._messages


def language():
    return getattr(g,'ui_language','de') if has_request_context() else 'de'


def translate(message,values=None):
    if not isinstance(message,str):return message
    match=re.match(r'^(\s*)(.*?)(\s*)$',message,re.S)
    prefix,key,suffix=match.groups()
    text=catalog().get(key,key) if language()=='en' else key
    if language()=='en' and key not in catalog():
        for pattern,indexes,prefix,replacement in message_patterns():
            if not key.startswith(prefix):continue
            found=pattern.fullmatch(key)
            if found:
                captured={index:found.group(i+1) for i,index in enumerate(indexes)}
                text=re.sub(r'\{(\d+)\}',lambda m:captured.get(int(m[1]),m[0]),replacement);break
    if values is not None:
        for index,value in enumerate(values):text=text.replace('{'+str(index)+'}',str(value))
    return prefix+text+suffix


def message_patterns():
    messages=catalog()
    if getattr(message_patterns,'_source',None) is not messages:
        result=[]
        for key,value in messages.items():
            if not re.search(r'\{\d+\}',key):continue
            pieces=re.split(r'(\{\d+\})',key);indexes=[];pattern=''
            for part in pieces:
                if re.fullmatch(r'\{\d+\}',part):indexes.append(int(part[1:-1]));pattern+=r'([\s\S]*?)'
                else:pattern+=re.escape(part)
            result.append((re.compile(pattern),indexes,key.split('{')[0],value))
        message_patterns._source=messages;message_patterns._patterns=result
    return message_patterns._patterns


def literal(message):
    """Only called for trusted literal template text, never a model value."""
    key=html.unescape(message).strip()
    if language()=='de' or key not in catalog():return Markup(message)
    prefix=message[:len(message)-len(message.lstrip())];suffix=message[len(message.rstrip()):]
    return Markup(prefix)+escape(catalog()[key])+Markup(suffix)


class _StaticText(HTMLParser):
    def __init__(self,source):
        super().__init__(convert_charrefs=False)
        self.source=source;self.offsets=[0];self.ranges=[];self.attributes=[];self.raw=None
        self.offsets.extend(match.end() for match in re.finditer('\n',source))
    def absolute_offset(self):
        line,column=self.getpos();return self.offsets[line-1]+column
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style'}:self.raw=tag
        text=self.get_starttag_text();offset=self.absolute_offset()
        for match in re.finditer(r'\b(?:aria-label|aria-description|title|placeholder|alt)\s*=\s*([\'"])(.*?)\1',text,re.S):
            self.attributes.append((offset+match.start(2),offset+match.end(2)))
    def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs)
    def handle_endtag(self,tag):
        if tag==self.raw:self.raw=None
    def handle_data(self,data):
        if not self.raw:self.ranges.append((self.absolute_offset(),self.absolute_offset()+len(data)))
    def handle_entityref(self,name):
        if not self.raw:self.ranges.append((self.absolute_offset(),self.absolute_offset()+len(name)+2))
    def handle_charref(self,name):
        if not self.raw:self.ranges.append((self.absolute_offset(),self.absolute_offset()+len(name)+3))


def template_literals(source):
    """Find static UI text while keeping Jinja expressions and script bodies opaque."""
    tokens=list(Environment().lex(source));parts=[];masked=[];data_ranges=[];offset=0
    for _,kind,value in tokens:
        parts.append(value)
        if kind=='data':masked.append(value);data_ranges.append((offset,offset+len(value)))
        else:masked.append(re.sub(r'[^\n]',' ',value))
        offset+=len(value)
    source=''.join(parts);parser=_StaticText(''.join(masked));parser.feed(''.join(masked))
    merged=[]
    for start,end in parser.ranges:
        if merged and merged[-1][1]==start:merged[-1]=(merged[-1][0],end)
        else:merged.append((start,end))
    intervals=[]
    for start,end in merged+parser.attributes:
        for left,right in data_ranges:
            a,b=max(left,start),min(right,end)
            if a<b and re.search(r'[^\W\d_]',html.unescape(source[a:b]),re.UNICODE):
                # Partially dynamic attributes belong to their template expression.
                if (start,end) in parser.attributes and (a!=start or b!=end):continue
                intervals.append((a,b,source[a:b]))
    return source,sorted(set(intervals))


def localize_template(source):
    source,intervals=template_literals(source)
    for start,end,text in reversed(intervals):
        source=source[:start]+'{{ ui_literal('+json.dumps(text,ensure_ascii=False)+') }}'+source[end:]
    return source


class InterfaceLanguage(Extension):
    def preprocess(self,source,name,filename=None):return localize_template(source) if name and name.endswith('.html') else source


class InterfaceCodeGenerator(CodeGenerator):
    def visit_Output(self,node,frame):
        def expression(item):
            if isinstance(item,nodes.Const) and isinstance(item.value,str):
                return nodes.Call(nodes.Getitem(nodes.EnvironmentAttribute('globals'),nodes.Const('ui_t'),'load'),[item],[],None,None).set_lineno(item.lineno)
            if isinstance(item,nodes.CondExpr):item.expr1=expression(item.expr1);item.expr2=expression(item.expr2)
            elif isinstance(item,nodes.Concat):item.nodes=[expression(child) for child in item.nodes]
            return item
        node.nodes=[expression(item) for item in node.nodes]
        return super().visit_Output(node,frame)


def register_i18n(application,get_db):
    application.jinja_env.add_extension(InterfaceLanguage)
    application.jinja_env.code_generator_class=InterfaceCodeGenerator
    application.jinja_env.globals.update(ui_t=translate,ui_literal=literal)
    @application.before_request
    def load_interface_language():
        if request.endpoint=='static':g.ui_language='de';return
        try:
            row=get_db().execute('SELECT ui_language FROM server_settings WHERE id=1').fetchone()
            g.ui_language=row[0] if row and row[0] in SUPPORTED_LANGUAGES else 'de'
        except sqlite3.OperationalError:g.ui_language='de'
    # Resolve the instance language before authentication/CSRF error handling.
    application.before_request_funcs[None].remove(load_interface_language)
    application.before_request_funcs[None].insert(0,load_interface_language)
    version_cache={}
    def version():
        messages=catalog()
        if version_cache.get('source') is not messages:
            version_cache.update(source=messages,value=hashlib.sha256(json.dumps(messages,sort_keys=True).encode()).hexdigest()[:16])
        return version_cache['value']
    @application.get('/i18n/en.js')
    def interface_catalog():
        response=application.response_class('window.inventoryTranslations='+json.dumps(catalog(),ensure_ascii=False)+';',mimetype='application/javascript')
        response.set_etag(version());response.headers['Cache-Control']='public,max-age=31536000,immutable' if request.args.get('v')==version() else 'no-cache'
        return response.make_conditional(request)
    @application.context_processor
    def interface_context():return {'ui_language':language(),'ui_catalog_version':version()}
    @application.after_request
    def translate_errors(response):
        if language()!='en' or response.status_code<400 or not response.is_json:return response
        payload=response.get_json(silent=True)
        if not isinstance(payload,dict):return response
        def messages(value):
            if isinstance(value,str):return translate(value)
            if isinstance(value,list):return [messages(item) for item in value]
            if isinstance(value,dict):return {key:messages(item) for key,item in value.items()}
            return value
        for key in ['error','message','details','errors']:
            if key in payload:payload[key]=messages(payload[key])
        response.set_data(application.json.dumps(payload));return response
