/* Shared asset taxonomy: real fields, protected reassignment, no inventory deletion. */
(() => {
  const data=document.querySelector('[data-category-data]');if(!data)return;
  const categories=JSON.parse(data.textContent),dialog=document.querySelector('[data-category-dialog]'),form=dialog.querySelector('form'),deleteDialog=document.querySelector('[data-category-delete-dialog]');
  let current=null,opener=null,dirty=false,saving=false,page=1;
  function paginate(){
    const query=document.querySelector('[data-category-search]').value.toLocaleLowerCase('de');
    const matches=categories.filter(item=>(item.name+' '+(item.description || '')).toLocaleLowerCase('de').includes(query));
    const pages=Math.max(1,Math.ceil(matches.length/10));page=Math.min(page,pages);const ids=new Set(matches.slice((page-1)*10,page*10).map(item=>item.id));
    document.querySelectorAll('[data-category-row]').forEach(row=>row.hidden=!ids.has(Number(row.dataset.categoryRow)));
    document.querySelector('[data-category-count]').textContent=uiText("{0} Kategorien", [matches.length]);
    document.querySelector('[data-category-page]').textContent=uiText("Seite {0} von {1}", [page, pages]);
    document.querySelector('[data-category-back]').disabled=page<=1;document.querySelector('[data-category-next]').disabled=page>=pages;
    document.querySelector('[data-no-categories]').hidden=matches.length>0;
  }
  document.querySelector('[data-category-search]').value=new URL(location.href).searchParams.get('q') || '';
  paginate();document.querySelector('[data-category-search]').addEventListener('input',()=>{page=1;paginate();});
  document.querySelector('[data-category-back]').addEventListener('click',()=>{page--;paginate();});document.querySelector('[data-category-next]').addEventListener('click',()=>{page++;paginate();});
  function field(name='',config={}){
    const row=document.createElement('fieldset');row.className='category-field';const legend=document.createElement('legend');legend.textContent=name || uiText('Neues Feld');row.append(legend);
    for(const [key,label,value] of [['name',uiText('Feldname'),name],['type','Feldtyp',config.type || 'text'],['unit',uiText('Einheit'),config.unit || ''],['options',uiText('Auswahlwerte (ein Wert pro Zeile)'),(config.options || []).join('\n')]]){
      const wrapper=document.createElement('label');wrapper.dataset.fieldControl=key;wrapper.textContent=label;const input=document.createElement(key==='type' ? 'select' : key==='options' ? 'textarea' : 'input');input.className='input';input.dataset.fieldProperty=key;input.setAttribute('aria-label',label);
      if(key==='type')for(const [type,text] of [['text','Text'],['number',uiText('Zahl')],['date',uiText('Datum')],['checkbox',uiText('Ja/Nein')],['select',uiText('Auswahl')]]){const option=document.createElement('option');option.value=type;option.textContent=text;input.append(option);}
      if(key==='name'){input.required=true;input.maxLength=120;}if(key==='options')input.rows=2;input.value=value;wrapper.append(input);row.append(wrapper);
    }
    const visibility=()=>{const type=row.querySelector('[data-field-property=type]').value;row.querySelector('[data-field-control=options]').hidden=type!=='select';row.querySelector('[data-field-control=unit]').hidden=['checkbox','date','select'].includes(type);};row.querySelector('[data-field-property=type]').addEventListener('change',visibility);visibility();
    const remove=document.createElement('button');remove.type='button';remove.className='btn btn-secondary';remove.textContent=uiText('Feld entfernen');remove.addEventListener('click',()=>{row.remove();dirty=true;});row.append(remove);form.querySelector('[data-category-fields]').append(row);
  }
  function open(item,button){current=item;opener=button;dirty=false;form.reset();form.elements.name.value=item?.name || '';form.elements.description.value=item?.description || '';if(item?.icon && ![...form.elements.icon.options].some(option=>option.value===item.icon))form.elements.icon.append(new Option(uiText('Bisheriges Symbol'),item.icon));form.elements.icon.value=item?.icon || 'package';form.querySelector('[data-category-error]').hidden=true;form.querySelector('[data-category-fields]').replaceChildren();for(const [name,config] of Object.entries(item?.fields || {}))field(name,config);dialog.showModal();form.elements.name.focus();}
  function close(){if(saving)return;if(dirty && !confirm(uiText('Nicht gespeicherte Kategorieänderungen verwerfen?')))return;dirty=false;dialog.close();opener?.focus();}
  form.addEventListener('input',()=>dirty=true);form.addEventListener('change',()=>dirty=true);dialog.addEventListener('cancel',event=>{event.preventDefault();close();});dialog.querySelectorAll('[data-close-category]').forEach(button=>button.addEventListener('click',close));
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  document.querySelector('[data-new-category]')?.addEventListener('click',event=>open(null,event.currentTarget));
  document.querySelectorAll('[data-edit-category]').forEach(button=>button.addEventListener('click',()=>open(categories.find(item=>item.id===Number(button.dataset.editCategory)),button)));
  form.querySelector('[data-add-category-field]').addEventListener('click',()=>{field();dirty=true;});
  async function api(url,method,payload){const response=await fetch(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(response.redirected)throw new Error(uiText('Die Sitzung ist abgelaufen. Bitte erneut anmelden.'));const result=await response.json();if(!response.ok)throw new Error(result.error || uiText('Kategorie konnte nicht gespeichert werden.'));return result;}
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(saving)return;saving=true;const button=form.querySelector('[type=submit]'),error=form.querySelector('[data-category-error]');button.disabled=true;error.hidden=true;
    try{const fields={};for(const row of form.querySelectorAll('.category-field')){const values=Object.fromEntries([...row.querySelectorAll('[data-field-property]')].map(input=>[input.dataset.fieldProperty,input.value]));const name=values.name.trim();if(!name || Object.hasOwn(fields,name))throw new Error(uiText('Bitte eindeutige Feldnamen eingeben.'));fields[name]={type:values.type,unit:values.unit,options:values.options.split('\n').map(value=>value.trim()).filter(Boolean)};}
      await api('/api/inventory/categories'+(current ? '/'+current.id : ''),current ? 'PUT' : 'POST',{name:form.elements.name.value,description:form.elements.description.value,icon:form.elements.icon.value,fields,expectedRevision:current?.revision});dirty=false;location.assign('/inventory/categories?q='+encodeURIComponent(form.elements.name.value));
    }catch(problem){error.textContent=problem.message;error.hidden=false;button.disabled=false;saving=false;}
  });
  let deleting;
  document.querySelectorAll('[data-delete-category]').forEach(button=>button.addEventListener('click',()=>{
    deleting=categories.find(item=>item.id===Number(button.dataset.deleteCategory));opener=button;
    deleteDialog.querySelector('[data-delete-category-description]').textContent=uiText("„{0}“ löschen?", [deleting.name]);
    const target=deleteDialog.querySelector('select');target.replaceChildren(new Option(uiText('Ohne Umzuordnung versuchen'),''));
    for(const item of categories.filter(item=>item.id!==deleting.id))target.append(new Option(item.name,String(item.id)));
    deleteDialog.querySelector('[data-category-delete-error]').hidden=true;deleteDialog.showModal();target.focus();
  }));
  deleteDialog.querySelectorAll('[data-close-delete-category]').forEach(button=>button.addEventListener('click',()=>{if(saving)return;deleteDialog.close();opener?.focus();}));
  deleteDialog.querySelector('form').addEventListener('submit',async event=>{
    event.preventDefault();if(saving)return;saving=true;const button=event.target.querySelector('[type=submit]'),error=deleteDialog.querySelector('[data-category-delete-error]');button.disabled=true;error.hidden=true;
    try{const target=deleteDialog.querySelector('select').value;await api('/api/inventory/categories/'+deleting.id,'DELETE',{expectedRevision:deleting.revision,target_category_id:target ? Number(target) : null});location.reload();}
    catch(problem){error.textContent=problem.message;error.hidden=false;button.disabled=false;saving=false;}
  });
})();
