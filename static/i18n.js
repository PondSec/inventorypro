/* Only interface literals pass through this API. Inventory data stays unchanged. */
(() => {
  const language=document.documentElement.lang==='en' ? 'en' : 'de';
  const messages=language==='en' ? (window.inventoryTranslations || {}) : {};
  const patterns=Object.entries(messages).filter(([key])=>/\{\d+\}/.test(key)).map(([key,value])=>{
    const indexes=[];const escaped=key.split(/(\{\d+\})/).map(part=>{
      if(/^\{\d+\}$/.test(part)){indexes.push(Number(part.slice(1,-1)));return '([\\s\\S]*?)';}
      return part.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
    }).join('');return {prefix:key.split('{')[0],regex:new RegExp('^'+escaped+'$'),indexes,value};
  });
  function t(message,values){
    if(typeof message!=='string')return message;
    const [,left,key,right]=message.match(/^(\s*)([\s\S]*?)(\s*)$/);let result=messages[key] ?? key;
    if(language==='en' && !Object.hasOwn(messages,key)){
      for(const pattern of patterns){if(!key.startsWith(pattern.prefix))continue;const match=key.match(pattern.regex);if(match){const captured=[];pattern.indexes.forEach((index,i)=>captured[index]=match[i+1]);result=pattern.value.replace(/\{(\d+)\}/g,(_,i)=>captured[i] ?? '');break;}}
    }
    if(values)result=result.replace(/\{(\d+)\}/g,(_,i)=>String(values[i] ?? ''));
    return left+result+right;
  }
  const escape=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  function htmlFragment(fragment){
    if(language==='de')return fragment;
    return fragment.replace(/(^|>)([^<]+)(?=<|$)/g,(all,start,text)=>{const decoded=document.createElement('textarea');decoded.innerHTML=text;const value=t(decoded.value);return start+(value===decoded.value ? text : escape(value));}).replace(/\b(aria-label|title|placeholder|alt)=(['"])(.*?)\2/g,(all,name,quote,value)=>{const translated=t(value);return translated===value ? all : name+'='+quote+escape(translated)+quote;});
  }
  window.InventoryI18n={language,locale:language==='en' ? 'en-GB' : 'de-DE',t,htmlFragment};
  window.uiText=t;
})();
