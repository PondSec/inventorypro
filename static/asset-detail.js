/* Real composition picker, retained legacy maintenance and existing assignment APIs. */
(() => {
  const detail=document.querySelector('[data-asset-detail]');if(!detail)return;
  const id=Number(detail.dataset.assetDetail),dialog=document.querySelector('[data-component-dialog]');
  let revision=Number(detail.dataset.assetRevision),opener,selected=new Map(),queryVersion=0,searchTimer,saving=false,pickerMode='components';
  const error=detail.querySelector('[data-detail-error]');
  async function api(url,method='GET',payload){
    const response=await fetch(url,{method,headers:payload && !(payload instanceof FormData) ? {'Content-Type':'application/json'} : {},body:payload instanceof FormData ? payload : payload ? JSON.stringify(payload) : undefined});
    if(response.redirected)throw new Error('Ihre Sitzung ist abgelaufen. Bitte erneut anmelden.');
    const result=await response.json().catch(()=>({error:'Die Serverantwort konnte nicht gelesen werden. Bitte erneut versuchen.'}));if(!response.ok)throw new Error(result.error || 'Die Änderung konnte nicht gespeichert werden.');return result;
  }
  const dirtyForms=new Set();
  detail.addEventListener('input',event=>{const form=event.target.closest('form');if(form)dirtyForms.add(form);});
  window.addEventListener('beforeunload',event=>{if(dirtyForms.size){event.preventDefault();event.returnValue='';}});
  function otherChanges(form){return ![...dirtyForms].some(item=>item!==form) || confirm('Weitere Formulare enthalten ungespeicherte Eingaben. Diese beim Speichern verwerfen?');}
  function showError(problem){error.textContent=problem.message;error.hidden=false;}
  function renderSelection(){
    const list=dialog.querySelector('[data-component-selection]');list.replaceChildren();
    for(const item of selected.values()){
      const row=document.createElement('div'),name=document.createElement('strong'),quantity=document.createElement('input'),remove=document.createElement('button');row.className='component-selection-row';name.textContent=item.name;
      quantity.type='number';quantity.min='1';quantity.max='1000000';quantity.step='1';quantity.className='input';quantity.value=item.quantity;quantity.setAttribute('aria-label','Menge für '+item.name);quantity.addEventListener('input',()=>item.quantity=Number(quantity.value));
      remove.type='button';remove.className='btn btn-secondary';remove.textContent='Entfernen';remove.setAttribute('aria-label',item.name+' aus Auswahl entfernen');remove.addEventListener('click',()=>{selected.delete(item.id);renderSelection();search();});
      row.append(name);if(pickerMode==='components')row.append(quantity);row.append(remove);list.append(row);
    }
    if(!selected.size)list.textContent='Noch keine Assets ausgewählt.';
  }
  async function search(){
    const version=++queryVersion,status=dialog.querySelector('[data-component-status]');
    try{
      const result=await api('/api/inventory/assets?per_page=20&q='+encodeURIComponent(dialog.querySelector('[data-component-search]').value));if(version!==queryVersion)return;
      const list=dialog.querySelector('[data-component-results]');list.replaceChildren();
      for(const item of result.rows.filter(item=>item.id!==id)){
        const row=document.createElement('label'),checkbox=document.createElement('input'),name=document.createElement('span');row.className='component-result';checkbox.type='checkbox';checkbox.checked=selected.has(item.id);name.textContent=item.name+(item.serial_number ? ' · '+item.serial_number : '');
        checkbox.addEventListener('change',()=>{if(checkbox.checked)selected.set(item.id,{id:item.id,name:item.name,quantity:1});else selected.delete(item.id);renderSelection();});row.append(checkbox,name);list.append(row);
      }
      status.textContent=`${result.total} Treffer. Die ersten 20 werden angezeigt; Suche verfeinern.`;
    }catch(problem){if(version===queryVersion)status.textContent=problem.message;}
  }
  function close(){if(saving)return;if(selected.size && !confirm('Auswahl verwerfen?'))return;dialog.close();opener?.focus();}
  async function openPicker(event,mode){
    if(!otherChanges(null))return;
    opener=event.currentTarget;pickerMode=mode;selected=new Map();renderSelection();
    dialog.querySelector('#component-dialog-title').textContent=mode==='relations' ? 'Beziehungen zu Assets' : 'Enthaltene Assets auswählen';
    dialog.querySelector('[data-relation-type-label]').hidden=mode!=='relations';
    dialog.querySelector('[data-save-components]').textContent=mode==='relations' ? 'Beziehungen speichern' : 'Assets übernehmen';
    dialog.querySelector('[data-picker-description]').textContent=mode==='relations' ? 'Eine Beziehung verknüpft eigenständige Assets. Sie verändert keine Inhaltszuordnung oder Menge.' : 'Auswahl bleibt beim Suchen erhalten. Bereits enthaltene Assets können mit einer anderen Menge übernommen werden.';
    dialog.showModal();dialog.querySelector('[data-component-search]').focus();await search();
    if(mode==='relations')try{
      const types=await api('/api/inventory/relation-types'),select=dialog.querySelector('[data-relation-type]');
      select.replaceChildren(new Option('Allgemeine Verknüpfung',''));
      for(const type of types)select.append(new Option(type.name,String(type.id)));
    }catch(problem){dialog.querySelector('[data-component-status]').textContent=problem.message;}
  }
  document.querySelector('[data-open-components]')?.addEventListener('click',event=>openPicker(event,'components'));
  document.querySelector('[data-open-relations]')?.addEventListener('click',event=>openPicker(event,'relations'));
  dialog?.querySelectorAll('[data-close-components]').forEach(button=>button.addEventListener('click',close));
  dialog?.addEventListener('cancel',event=>{event.preventDefault();close();});
  dialog?.querySelector('[data-component-search]').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(search,200);});
  dialog?.querySelector('[data-save-components]').addEventListener('click',async event=>{
    if(saving)return;if(!selected.size){dialog.querySelector('[data-component-status]').textContent='Bitte mindestens ein Asset auswählen.';return;}
    saving=true;event.currentTarget.disabled=true;
    try{if(pickerMode==='relations')await api(`/api/inventory/assets/${id}/relations`,'POST',{expectedRevision:revision,targets:[...selected.keys()],relation_type_id:Number(dialog.querySelector('[data-relation-type]').value)||null});else await api(`/api/inventory/assets/${id}/components`,'PUT',{expectedRevision:revision,items:[...selected.values()]});dirtyForms.clear();location.reload();}
    catch(problem){dialog.querySelector('[data-component-status]').textContent=problem.message;saving=false;dialog.querySelector('[data-save-components]').disabled=false;}
  });
  document.querySelector('[data-delete-asset]')?.addEventListener('click',async event=>{
    if(!otherChanges(null))return;
    if(!confirm('Asset löschen? Enthaltene Assets bleiben erhalten. Verknüpfte Vorgänge können die Löschung verhindern.'))return;
    const button=event.currentTarget;button.disabled=true;
    try{await api(`/api/inventory/assets/${id}`,'DELETE',{expectedRevision:revision});dirtyForms.clear();location.assign('/inventory');}catch(problem){showError(problem);button.disabled=false;}
  });
  detail.querySelectorAll('[data-remove-component]').forEach(button=>button.addEventListener('click',async()=>{
    if(!otherChanges(null))return;
    if(!confirm('Zuordnung entfernen? Das enthaltene Asset bleibt im Bestand.'))return;button.disabled=true;
    try{await api(`/api/inventory/assets/${id}/components/${button.dataset.removeComponent}`,'DELETE',{expectedRevision:revision});dirtyForms.clear();location.reload();}catch(problem){showError(problem);button.disabled=false;}
  }));
  detail.querySelectorAll('[data-asset-note],[data-asset-maintenance],[data-asset-assignment],[data-asset-tag],[data-asset-file],[data-asset-software]').forEach(form=>{
    if(form.matches('[data-asset-assignment]'))api('/api/asset-assignments/options').then(options=>{
      const select=form.querySelector('[data-assignment-target]');
      for(const [type,items] of [['user',options.users],['team',options.teams]])for(const item of items){const option=document.createElement('option');option.value=type+':'+item.id;option.textContent=(type==='team' ? 'Team: ' : '')+(item.username || item.name);select.append(option);}
    }).catch(showError);
    form.addEventListener('submit',async event=>{
      event.preventDefault();if(!otherChanges(form))return;const button=form.querySelector('button');if(button.disabled)return;button.disabled=true;
      let values=Object.fromEntries(new FormData(form));let url;
      if(form.matches('[data-asset-note]'))url=`/api/inventory/assets/${id}/notes`;
      else if(form.matches('[data-asset-tag]'))url=`/api/inventory/assets/${id}/tags`;
      else if(form.matches('[data-asset-file]')){url='/attachments/upload';values=new FormData(form);values.set('entity_type','asset');values.set('entity_id',String(id));}
      else if(form.matches('[data-asset-software]')){url='/api/software-installations';values.software_id=Number(values.software_id);values.asset_id=id;}
      else if(form.matches('[data-asset-maintenance]'))url=`/api/inventory/assets/${id}/maintenance`;
      else{url=`/assets/${id}/${values.action}`;const [type,identifier]=(values.target || '').split(':');values.assigned_to_user_id=type==='user' ? Number(identifier) : null;values.assigned_to_team_id=type==='team' ? Number(identifier) : null;if(!values.due_at)delete values.due_at;}
      try{await api(url,'POST',values);dirtyForms.clear();location.reload();}catch(problem){form.querySelector('[data-form-status]').textContent=problem.message;button.disabled=false;}
    });
  });
  detail.querySelectorAll('[data-extra-key]').forEach(button=>button.addEventListener('click',async()=>{
    if(!otherChanges(null) || !confirm('Eintrag entfernen?'))return;button.disabled=true;
    try{await api(`/api/inventory/assets/${id}/extras/${button.dataset.extraKind}/${button.dataset.extraKey}`,'DELETE');dirtyForms.clear();location.reload();}catch(problem){showError(problem);button.disabled=false;}
  }));
  const files=detail.querySelector('[data-asset-files]');
  if(files)api(`/attachments?entity_type=asset&entity_id=${id}`).then(items=>{
    files.replaceChildren();for(const item of items){if(!/^\/attachments\/[1-9][0-9]*\/download$/.test(item.download_url || ''))continue;const li=document.createElement('li'),link=document.createElement('a');link.textContent=item.original_filename;link.href=item.download_url;li.append(link);
      if(files.dataset.canDelete==='true'){const remove=document.createElement('button');remove.type='button';remove.className='btn btn-secondary';remove.textContent='Entfernen';remove.setAttribute('aria-label',item.original_filename+' entfernen');remove.addEventListener('click',async()=>{if(!otherChanges(null)||!confirm('Datei entfernen?'))return;remove.disabled=true;try{await api('/attachments/'+item.id+'/delete','POST');dirtyForms.clear();li.remove();if(!files.children.length)files.textContent='Keine Dateien hochgeladen.';}catch(problem){showError(problem);remove.disabled=false;}});li.append(remove);}
      files.append(li);}if(!items.length)files.textContent='Keine Dateien hochgeladen.';
  }).catch(showError);
  const softwareSelect=detail.querySelector('[data-software-options]');
  if(softwareSelect)api('/api/software').then(items=>{for(const item of items)softwareSelect.append(new Option(item.name+(item.version ? ' · '+item.version : ''),String(item.id)));}).catch(showError);
  detail.querySelectorAll('[data-remove-software]').forEach(button=>button.addEventListener('click',async()=>{
    if(!otherChanges(null) || !confirm('Softwarezuordnung entfernen?'))return;button.disabled=true;
    try{await api('/api/software-installations/'+button.dataset.removeSoftware,'DELETE');dirtyForms.clear();location.reload();}catch(problem){showError(problem);button.disabled=false;}
  }));
  detail.querySelectorAll('[data-maintenance-key]').forEach(button=>button.addEventListener('click',async()=>{
    if(!otherChanges(null))return;
    button.disabled=true;try{await api(`/api/inventory/assets/${id}/maintenance/${button.dataset.maintenanceKey}`,'PUT',{status:button.dataset.maintenanceStatus});dirtyForms.clear();location.reload();}catch(problem){showError(problem);button.disabled=false;}
  }));
  detail.querySelectorAll('[data-remove-relation]').forEach(button=>button.addEventListener('click',async()=>{
    if(!otherChanges(null)||!confirm('Beziehung entfernen? Beide Assets bleiben erhalten.'))return;
    button.disabled=true;try{await api(`/api/inventory/assets/${id}/relations/${button.dataset.removeRelation}`,'DELETE',{expectedRevision:revision});dirtyForms.clear();location.reload();}catch(problem){showError(problem);button.disabled=false;}
  }));

})();
