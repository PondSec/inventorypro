/* Canonical editor preserves all dynamic fields and unsaved inputs on errors. */
(() => {
  const form=document.querySelector('[data-asset-editor]');if(!form)return;
  const initial=JSON.parse(document.querySelector('[data-asset-initial]').textContent);
  const values={...initial.asset.specs};let dirty=false,saving=false;
  const inline=document.querySelector('[data-inline-asset-editor]'),opener=document.querySelector('[data-edit-asset]');
  function setEditing(open){
    if(!inline)return;
    inline.hidden=!open;document.querySelector('[data-asset-detail]').hidden=open;
    document.querySelector('[data-inline-editor-actions]').hidden=!open;opener.hidden=open;
    document.querySelector('.page-tabbar').hidden=open;
    (open ? form.elements.name : opener).focus();
  }
  const error=form.querySelector('[data-asset-error]'),specs=form.querySelector('[data-asset-specs]');
  function remember(){for(const input of specs.querySelectorAll('[data-spec-name]'))values[input.dataset.specName]=input.type==='checkbox' ? input.checked : input.value;}
  function renderFields(){
    remember();const category=initial.options.categories.find(item=>String(item.id)===form.elements.category_id.value);
    const fields=category?.fields || {};const keys=[...new Set([...Object.keys(fields),...Object.keys(values)])];specs.replaceChildren();
    for(const key of keys){
      const config=fields[key] || {},label=document.createElement('label');label.textContent=key+(config.unit ? ` (${config.unit})` : '');
      const input=document.createElement(config.type==='select' ? 'select' : 'input');input.className='input';input.dataset.specName=key;
      if(config.type==='select')for(const value of ['',...(config.options || [])]){const option=document.createElement('option');option.value=value;option.textContent=value || uiText('Nicht festgelegt');input.append(option);}
      else input.type=config.type==='checkbox' ? 'checkbox' : ['number','date'].includes(config.type) ? config.type : 'text';
      if(input.type==='checkbox')input.checked=Boolean(values[key]);else input.value=values[key] ?? '';
      if(input.type==='number')input.step='any';
      label.append(input);specs.append(label);
    }
    form.querySelector('[data-no-specs]').hidden=keys.length>0;
  }
  renderFields();form.elements.category_id.addEventListener('change',renderFields);
  opener?.addEventListener('click',()=>setEditing(true));
  document.querySelector('[data-cancel-asset-edit]')?.addEventListener('click',()=>{
    if(saving || dirty && !confirm(uiText('Ungespeicherte Änderungen verwerfen?')))return;
    form.reset();specs.replaceChildren();Object.keys(values).forEach(key=>delete values[key]);Object.assign(values,initial.asset.specs);
    renderFields();dirty=false;error.hidden=true;
    form.querySelectorAll('[aria-invalid]').forEach(input=>input.removeAttribute('aria-invalid'));
    const url=new URL(location.href);url.searchParams.delete('edit');history.replaceState(null,'',url);setEditing(false);
  });
  if(initial.inplace && initial.open)setEditing(true);
  form.addEventListener('input',()=>dirty=true);form.addEventListener('change',()=>dirty=true);
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(saving)return;saving=true;error.hidden=true;remember();
    document.querySelectorAll('[form="asset-editor"]').forEach(button=>button.disabled=true);
    for(const input of form.querySelectorAll('[aria-invalid]'))input.removeAttribute('aria-invalid');
    try{
      const payload={...Object.fromEntries(new FormData(form)),specs:values,expectedRevision:initial.asset.revision};
      for(const key of ['category_id','location_id','vendor_id','purchase_order_id'])payload[key]=payload[key] ? Number(payload[key]) : null;
      const response=await fetch('/api/inventory/assets'+(initial.asset.id ? '/'+initial.asset.id : ''),{method:initial.asset.id ? 'PUT' : 'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      if(response.redirected)throw new Error(uiText('Ihre Sitzung ist abgelaufen. Bitte erneut anmelden; Ihre Eingaben bleiben erhalten.'));
      const result=await response.json();
      if(!response.ok){
        for(const key of Object.keys(result.fields || {})){const input=key.startsWith('specs.') ? [...specs.querySelectorAll('[data-spec-name]')].find(input=>input.dataset.specName===key.slice(6)) : form.elements.namedItem(key);input?.setAttribute('aria-invalid','true');}
        throw new Error(result.error || uiText('Das Asset konnte nicht gespeichert werden.'));
      }
      dirty=false;
      if(initial.inplace){const url=new URL(location.href);url.searchParams.delete('edit');history.replaceState(null,'',url);location.reload();}
      else location.assign('/inventory/assets/'+result.id);
    }catch(problem){error.textContent=problem.message;error.hidden=false;error.scrollIntoView({block:'nearest'});}
    finally{saving=false;document.querySelectorAll('[form="asset-editor"]').forEach(button=>button.disabled=false);}
  });
})();
