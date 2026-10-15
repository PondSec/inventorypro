/* Real composition picker, retained legacy maintenance and existing assignment APIs. */
(() => {
  const detail=document.querySelector('[data-asset-detail]');if(!detail)return;
  const id=Number(detail.dataset.assetDetail),dialog=document.querySelector('[data-component-dialog]');
  let revision=Number(detail.dataset.assetRevision),opener,selected=new Map(),queryVersion=0,searchTimer,saving=false;
  const error=detail.querySelector('[data-detail-error]');
  async function api(url,method='GET',payload){
    const response=await fetch(url,{method,headers:payload ? {'Content-Type':'application/json'} : {},body:payload ? JSON.stringify(payload) : undefined});
    if(response.redirected)throw new Error('Ihre Sitzung ist abgelaufen. Bitte erneut anmelden.');
    const result=await response.json();if(!response.ok)throw new Error(result.error || 'Die Änderung konnte nicht gespeichert werden.');return result;
  }
  function showError(problem){error.textContent=problem.message;error.hidden=false;}
  function renderSelection(){
    const list=dialog.querySelector('[data-component-selection]');list.replaceChildren();
    for(const item of selected.values()){
      const row=document.createElement('div'),name=document.createElement('strong'),quantity=document.createElement('input'),remove=document.createElement('button');row.className='component-selection-row';name.textContent=item.name;
      quantity.type='number';quantity.min='1';quantity.max='1000000';quantity.step='1';quantity.className='input';quantity.value=item.quantity;quantity.setAttribute('aria-label','Menge für '+item.name);quantity.addEventListener('input',()=>item.quantity=Number(quantity.value));
      remove.type='button';remove.className='btn btn-secondary';remove.textContent='Entfernen';remove.setAttribute('aria-label',item.name+' aus Auswahl entfernen');remove.addEventListener('click',()=>{selected.delete(item.id);renderSelection();search();});
      row.append(name,quantity,remove);list.append(row);
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
  document.querySelector('[data-open-components]')?.addEventListener('click',async event=>{
    opener=event.currentTarget;selected=new Map();renderSelection();dialog.showModal();dialog.querySelector('[data-component-search]').focus();await search();
  });
  dialog?.querySelectorAll('[data-close-components]').forEach(button=>button.addEventListener('click',close));
  dialog?.addEventListener('cancel',event=>{event.preventDefault();close();});
  dialog?.querySelector('[data-component-search]').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(search,200);});
  dialog?.querySelector('[data-save-components]').addEventListener('click',async event=>{
    if(saving)return;if(!selected.size){dialog.querySelector('[data-component-status]').textContent='Bitte mindestens ein Asset auswählen.';return;}
    saving=true;event.currentTarget.disabled=true;
    try{await api(`/api/inventory/assets/${id}/components`,'PUT',{expectedRevision:revision,items:[...selected.values()]});location.reload();}
    catch(problem){dialog.querySelector('[data-component-status]').textContent=problem.message;saving=false;dialog.querySelector('[data-save-components]').disabled=false;}
  });
  detail.querySelectorAll('[data-remove-component]').forEach(button=>button.addEventListener('click',async()=>{
    if(!confirm('Zuordnung entfernen? Das enthaltene Asset bleibt im Bestand.'))return;button.disabled=true;
    try{await api(`/api/inventory/assets/${id}/components/${button.dataset.removeComponent}`,'DELETE',{expectedRevision:revision});location.reload();}catch(problem){showError(problem);button.disabled=false;}
  }));
  detail.querySelectorAll('[data-asset-note],[data-asset-maintenance],[data-asset-assignment]').forEach(form=>{
    if(form.matches('[data-asset-assignment]'))api('/api/asset-assignments/options').then(options=>{
      const select=form.querySelector('[data-assignment-target]');
      for(const [type,items] of [['user',options.users],['team',options.teams]])for(const item of items){const option=document.createElement('option');option.value=type+':'+item.id;option.textContent=(type==='team' ? 'Team: ' : '')+(item.username || item.name);select.append(option);}
    }).catch(showError);
    form.addEventListener('submit',async event=>{
      event.preventDefault();const button=form.querySelector('button');if(button.disabled)return;button.disabled=true;
      const values=Object.fromEntries(new FormData(form));let url;
      if(form.matches('[data-asset-note]'))url=`/api/inventory/assets/${id}/notes`;
      else if(form.matches('[data-asset-maintenance]'))url=`/api/inventory/assets/${id}/maintenance`;
      else{url=`/assets/${id}/${values.action}`;const [type,identifier]=(values.target || '').split(':');values.assigned_to_user_id=type==='user' ? Number(identifier) : null;values.assigned_to_team_id=type==='team' ? Number(identifier) : null;if(!values.due_at)delete values.due_at;}
      try{await api(url,'POST',values);location.reload();}catch(problem){form.querySelector('[data-form-status]').textContent=problem.message;button.disabled=false;}
    });
  });
  detail.querySelectorAll('[data-maintenance-key]').forEach(button=>button.addEventListener('click',async()=>{
    button.disabled=true;try{await api(`/api/inventory/assets/${id}/maintenance/${button.dataset.maintenanceKey}`,'PUT',{status:button.dataset.maintenanceStatus});location.reload();}catch(problem){showError(problem);button.disabled=false;}
  }));
})();
