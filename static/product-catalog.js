/* Local catalog and image management. CSRF headers come from shared csrf.js. */
(() => {
  'use strict';
  let dirty=false;
  document.addEventListener('input',event=>{if(event.target.closest('[data-catalog-form],[data-catalog-upload],[data-public-source]'))dirty=true;});
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  function discard(){return !dirty || window.confirm('Ungespeicherte Eingaben verwerfen?');}
  function reload(){dirty=false;location.reload();}
  const model = document.querySelector('[data-model-state]');
  const photo = document.querySelector('[data-photo-state]');
  async function api(url, options = {}) {
    const response = await fetch(url, options);
    if (response.redirected) throw new Error(uiText('Die Sitzung ist abgelaufen. Bitte erneut anmelden.'));
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || uiText('Die Änderung konnte nicht gespeichert werden.'));
    return data;
  }
  const json = data => ({method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  async function perform(button, status, task) {
    if (button?.disabled) return;
    if (button) button.disabled = true;
    if (status) { status.classList.remove('form-error'); status.textContent=uiText('Wird verarbeitet …'); }
    try { await task(); }
    catch (error) { if (status) {status.classList.add('form-error');status.textContent=error.message;} }
    finally { if (button) button.disabled=false; }
  }
  document.addEventListener('click', event => {
    const open=event.target.closest('[data-open-dialog]');
    if (open) {const dialog=document.getElementById(open.dataset.openDialog);dialog._opener=open;dialog.showModal();}
    const close=event.target.closest('[data-close-dialog]');
    if (close) {const dialog=close.closest('dialog');if(discard()){dirty=false;dialog.close();dialog._opener?.focus();}}
    const action=event.target.closest('[data-photo-action],[data-assign-model]');
    if (action && photo && discard()) perform(action,photo.querySelector('[data-photo-status]'),async () => {
      await api(photo.dataset.photoApi,json({action:action.dataset.photoAction || 'assign',product_id:Number(action.dataset.assignModel),expectedUpdatedAt:photo.dataset.photoVersion}));
      reload();
    });
    const image=event.target.closest('[data-model-image]');
    if (image && model && discard()) perform(image,image.closest('section').querySelector('[data-image-status]'),async () => {
      await api(`/api/catalog/models/${model.dataset.modelId}/images/${image.dataset.imageId}`,json({action:image.dataset.modelImage,expectedUpdatedAt:model.dataset.modelVersion}));reload();
    });
    const remove=event.target.closest('[data-delete-model]');
    if (remove && model && window.confirm(uiText('Produktmodell löschen? Inventarisierte Geräte, Sets und eigene Fotos bleiben erhalten.'))) perform(remove,document.querySelector('[data-delete-status]'),async () => {
      await api('/api/catalog/models/'+model.dataset.modelId,{...json({expectedUpdatedAt:model.dataset.modelVersion}),method:'DELETE'});dirty=false;location.assign('/inventory/catalog');
    });
    const reconcile=event.target.closest('[data-reconcile]');
    if (reconcile) perform(reconcile,document.querySelector('[data-reconcile-status]'),async () => {
      let after={},processed=0,matched=0;
      for (;;) {
        const result=await api('/api/catalog/reconcile',json({after}));after=result.last;processed+=result.processed;matched+=result.matched;
        document.querySelector('[data-reconcile-status]').textContent=uiText("{0} Einträge geprüft, {1} zugeordnet.", [processed, matched]);
        if (result.processed===0) break;
        // Stay below the server's per-user reconciliation rate limit.
        await new Promise(resolve => setTimeout(resolve,2100));
      }
    });
  });
  const publicCatalog=document.querySelector('[data-public-catalog]');
  const publicForm=publicCatalog?.querySelector('[data-public-source]');
  let sourcePoll=null;
  const sourceLabels={queued:'Wartet',running:uiText('Wird geprüft'),matched:uiText('Bild verfügbar'),no_match:uiText('Kein eindeutiger Treffer'),no_image:uiText('Kein Bild verfügbar'),ambiguous:'Mehrdeutig',unlicensed:uiText('Keine freigegebene Lizenz'),insufficient:uiText('Produktdaten unvollständig'),error:'Abruf fehlgeschlagen'};
  async function refreshSource() {
    if(!publicCatalog)return;
    const result=await api('/api/catalog/external');
    publicCatalog.querySelector('[data-public-counts]').textContent=Object.entries(result.counts).map(([key,value])=>`${sourceLabels[key] || key}: ${value}`).join(' · ') || uiText('Noch keine öffentlichen Bildabgleiche.');
    const list=publicCatalog.querySelector('[data-public-jobs]');list.replaceChildren();
    for(const job of result.recent){
      const li=document.createElement('li'),name=document.createElement('strong'),state=document.createElement('span');
      name.textContent=`${job.identity.manufacturer} ${job.identity.model || job.identity.gtin}`;
      state.textContent=job.message || sourceLabels[job.status] || job.status;li.append(name,state);
      if(job.result.product_id){const link=document.createElement('a');link.href='/inventory/catalog/'+job.result.product_id;link.textContent='Produktmodell';li.append(link);}
      for(const candidate of (job.result.candidates || [])){
        const link=document.createElement('a');
        // Never accept provider-controlled schemes/hosts in browser links.
        if(!/^https:\/\/www\.wikidata\.org\/wiki\/Q[1-9][0-9]*$/.test(candidate.source_url || ''))continue;
        link.href=candidate.source_url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=uiText("Vorschlag prüfen: {0}", [candidate.name]);li.append(link);
      }
      list.append(li);
    }
    clearTimeout(sourcePoll);
    if(result.settings.external_enabled && ((result.counts.queued || 0)+(result.counts.running || 0)>0))sourcePoll=setTimeout(()=>refreshSource().catch(sourceError),3000);
    return result;
  }
  function sourceError(error){const status=publicCatalog?.querySelector('[data-public-status]');if(status){status.classList.add('form-error');status.textContent=error.message;}}
  if(publicCatalog){
    refreshSource().catch(sourceError);
    publicCatalog.querySelector('[data-public-queue]').addEventListener('click',event=>perform(event.currentTarget,publicCatalog.querySelector('[data-public-status]'),async()=>{
      let after={},processed=0;
      for(;;){const result=await api('/api/catalog/external/queue',json({after}));after=result.last;processed+=result.processed;
        publicCatalog.querySelector('[data-public-status]').textContent=uiText("{0} Einträge geprüft. Geeignete Produktdaten werden im Hintergrund abgeglichen.", [processed]);
        await refreshSource();if(!result.processed)break;await new Promise(resolve=>setTimeout(resolve,2100));
      }
    }));
    publicForm.addEventListener('submit',event=>{event.preventDefault();perform(publicForm.querySelector('[type=submit]'),publicCatalog.querySelector('[data-public-status]'),async()=>{
      const result=await api('/api/catalog/external',{...json({enabled:publicForm.elements.enabled.checked,rightsReviewed:publicForm.elements.reviewed.checked,expectedUpdatedAt:publicForm.dataset.sourceVersion}),method:'PUT'});
      publicForm.dataset.sourceVersion=result.updated_at;dirty=false;
      publicCatalog.querySelector('[data-public-queue]').disabled=!result.external_enabled;
      publicCatalog.querySelector('[data-public-status]').textContent=result.external_enabled ? uiText('Öffentliche Bildquelle aktiviert.') : uiText('Öffentliche Bildquelle deaktiviert. Bereits gespeicherte Bilder bleiben verfügbar.');
      await refreshSource();
    });});
  }
  document.addEventListener('submit', event => {
    const form=event.target;
    if (form.matches('[data-catalog-form],[data-catalog-upload]')) {
      event.preventDefault();perform(form.querySelector('button[type=submit],button:not([type])'),form.querySelector('[data-form-status]'),async () => {
        const data=new FormData(form);
        let options;
        if (form.matches('[data-catalog-upload]')) options={method:'POST',body:data};
        else {const values=Object.fromEntries(data);values.aliases=data.getAll('alias');options={...json(values),method:form.dataset.method || 'POST'};}
        const result=await api(form.action,options);
        dirty=false;
        if (form.matches('[data-catalog-form]')) location.assign('/inventory/catalog/'+result.id);else reload();
      });
    }
    if (form.matches('[data-model-search]')) {
      event.preventDefault();perform(form.querySelector('button'),document.querySelector('[data-search-status]'),async () => {
        const result=await api('/api/catalog/models?per_page=20&q='+encodeURIComponent(new FormData(form).get('q')));
        const list=document.querySelector('[data-model-results]');list.replaceChildren();
        for (const item of result.models) {
          const li=document.createElement('li'),copy=document.createElement('span'),name=document.createElement('strong'),maker=document.createElement('small'),button=document.createElement('button');
          name.textContent=item.name;maker.textContent=item.manufacturer;copy.append(name,maker);
          button.type='button';button.className='btn btn-secondary';button.dataset.assignModel=item.id;button.textContent=uiText('Zuordnen');li.append(copy,button);list.append(li);
        }
        document.querySelector('[data-search-status]').textContent=result.total ? uiText("{0} von {1} Modellen. Bitte das passende Modell bestätigen.", [Math.min(20,result.total), result.total]) : uiText('Kein passendes Modell gefunden. Eigene Fotos können Sie weiterhin hochladen.');
      });
    }
  });
  // Native dialog provides focus containment and Escape; restore the opener too.
  document.querySelectorAll('.ui-dialog').forEach(dialog => {dialog.addEventListener('close',()=>dialog._opener?.focus());dialog.addEventListener('cancel',event=>{if(!discard())event.preventDefault();else dirty=false;});});
})();
