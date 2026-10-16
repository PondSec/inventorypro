/* General wishes and projects: accessible native dialogs, real inventory actions. */
(() => {
  'use strict';
  const config = JSON.parse(document.querySelector('[data-wish-config]').textContent);
  const pageError = document.querySelector('[data-page-error]');
  const dialogs = [...document.querySelectorAll('.wish-dialog')];
  let row = null, activeKind = '', dirty = false, busy = false, opener = null;
  let existingAsset = null, requestKey = '', searchTimer, searchController;
  const t = window.uiText;
  async function api(url, method = 'GET', payload) {
    const response = await fetch(url, {method, headers: {'Content-Type': 'application/json'}, ...(payload ? {body: JSON.stringify(payload)} : {})});
    const value = await response.json().catch(() => ({}));
    if (!response.ok) throw Object.assign(new Error(value.error || t('Die Aktion konnte nicht abgeschlossen werden.')), {fields: value.fields || {}});
    return value;
  }
  function showError(target, problem) {
    const error = target.querySelector('[data-error]') || pageError;
    error.textContent = problem.message; error.hidden = false;
    for (const [key] of Object.entries(problem.fields || {})) {
      const input = target.elements?.namedItem(key) || [...target.querySelectorAll('[data-spec-name]')].find(i => i.dataset.specName === key.replace(/^specs\./, ''));
      input?.setAttribute('aria-invalid', 'true');
    }
    error.scrollIntoView({block: 'nearest'});
  }
  function begin(dialog, form, initial, kind) {
    row = initial; activeKind = kind; dirty = false; existingAsset = null;
    form.reset(); form.querySelector('[data-error]').hidden = true;
    form.querySelectorAll('[aria-invalid]').forEach(input => input.removeAttribute('aria-invalid'));
    form.querySelectorAll('input,select,textarea').forEach(input => input.disabled = false);
    for (const input of form.querySelectorAll('[name]')) {
      if (Object.hasOwn(initial, input.name)) input.value = initial[input.name] ?? '';
    }
    dialog.showModal();
    form.querySelector('input:not([disabled])')?.focus();
  }
  function done(url) { dirty = false; location.assign(url || location.pathname + location.search); }
  function close(dialog) {
    if (busy || dirty && !confirm(t('Ungespeicherte Änderungen verwerfen?'))) return;
    dirty = false; searchController?.abort(); dialog.close(); opener?.focus();
  }
  dialogs.forEach(dialog => {
    dialog.addEventListener('cancel', event => { event.preventDefault(); close(dialog); });
    dialog.querySelectorAll('[data-close-dialog]').forEach(button => button.addEventListener('click', () => close(dialog)));
    dialog.addEventListener('input', () => dirty = true);
    dialog.addEventListener('change', () => dirty = true);
  });
  window.addEventListener('beforeunload', event => { if (dirty) {event.preventDefault(); event.returnValue = '';} });
  async function submit(form, action) {
    if (busy) return;
    busy = true; form.querySelector('[data-error]').hidden = true;
    const buttons = [...form.closest('dialog').querySelectorAll('button')];
    buttons.forEach(button => button.disabled = true);
    try { await action(); } catch (problem) { showError(form, problem); }
    finally { busy = false; buttons.forEach(button => button.disabled = false); }
  }
  function payload(form) { return Object.fromEntries(new FormData(form)); }
  function ids(value, keys) { for (const key of keys) value[key] = value[key] ? Number(value[key]) : null; return value; }
  function price(value) { return value === null || value === undefined ? '' : (value / 100).toFixed(2); }
  function fields(container, categoryId) {
    container.replaceChildren();
    const category = config.categories.find(item => item.id === Number(categoryId));
    let definitions = {};
    try { definitions = typeof category?.fields === 'string' ? JSON.parse(category.fields) : category?.fields || {}; } catch (_) { /* Server validates the same schema. */ }
    for (const [name, definition] of Object.entries(definitions)) {
      const field = typeof definition === 'object' && definition ? definition : {};
      const label = document.createElement('label'); label.textContent = name + (field.unit ? ` (${field.unit})` : '');
      const input = document.createElement(field.type === 'select' ? 'select' : 'input'); input.className = 'input'; input.dataset.specName = name;
      if (field.type === 'select') for (const value of ['', ...(field.options || [])]) {const option = document.createElement('option'); option.value = value; option.textContent = value || t('Nicht festgelegt'); input.append(option);}
      else {input.type = ['number', 'date', 'checkbox'].includes(field.type) ? field.type : 'text'; if (input.type === 'number') input.step = 'any';}
      label.append(input); container.append(label);
    }
  }
  function specs(container) { return Object.fromEntries([...container.querySelectorAll('[data-spec-name]')].map(input => [input.dataset.specName, input.type === 'checkbox' ? input.checked : input.value])); }
  const wishDialog = document.querySelector('[data-wish-dialog]'), wishForm = document.querySelector('[data-wish-form]');
  const projectDialog = document.querySelector('[data-project-dialog]'), projectForm = document.querySelector('[data-project-form]');
  const acquireDialog = document.querySelector('[data-acquire-dialog]'), acquireForm = document.querySelector('[data-acquire-form]');
  const assembleDialog = document.querySelector('[data-assemble-dialog]'), assembleForm = document.querySelector('[data-assemble-form]');
  function projectCurrency() {
    const project = config.projects.find(item => item.id === Number(wishForm.elements.project_id.value));
    wishForm.elements.currency.readOnly = Boolean(project);
    if (project) wishForm.elements.currency.value = project.currency;
  }
  wishForm.elements.project_id.addEventListener('change', projectCurrency);
  async function openWish(id) {
    const initial = id ? await api('/api/wishes/' + id) : {name: '',quantity: 1, currency: config.project?.currency || 'EUR', project_id: config.project?.id || null, visibility: 'private', priority: 'normal'};
    begin(wishDialog, wishForm, initial, 'wish');
    wishForm.elements.unit_price.value = price(initial.unit_price_cents);
    document.querySelector('#wish-dialog-title').textContent = t(id ? 'Wunsch bearbeiten' : 'Wunsch hinzufügen');
    const locked = !config.canManage || Boolean(initial.project_asset_id);
    wishForm.querySelectorAll('input,select,textarea').forEach(input => input.disabled = locked);
    wishForm.querySelector('[data-save]').hidden = locked;
    wishForm.querySelector('[data-delete-wish]').hidden = !id || !config.canManage;
    const archive = wishForm.querySelector('[data-archive-wish]'); archive.hidden = !id || locked; archive.textContent = t(initial.archived ? 'Wieder aktivieren' : 'Archivieren');
    const history = wishForm.querySelector('[data-wish-history]'), list = wishForm.querySelector('[data-acquisitions]'); list.replaceChildren();
    history.hidden = !initial.acquisitions?.length;
    for (const item of initial.acquisitions || []) {
      const li = document.createElement('li');
      const link = document.createElement(item.asset_id ? 'a' : 'span');
      if (item.asset_id) link.href = '/inventory/assets/' + item.asset_id;
      link.textContent = item.restricted ? t('Asset ohne Anzeigeberechtigung') : item.asset_name + (item.asset_id ? '' : ' · ' + t('Nicht mehr im Bestand'));
      li.append(link); list.append(li);
    }
    projectCurrency(); dirty = false;
  }
  async function openProject(id) {
    const initial = id ? await api('/api/wishes/projects/' + id) : {name: '', currency: 'EUR', visibility: 'private'};
    begin(projectDialog, projectForm, initial, 'project');
    projectForm.elements.budget.value = price(initial.budget_cents);
    document.querySelector('#project-dialog-title').textContent = t(id ? 'Projekt bearbeiten' : 'Projekt erstellen');
    projectForm.querySelector('[data-delete-project]').hidden = !id;
  }
  function selectedAsset(asset) {
    existingAsset = asset;
    const label = acquireForm.querySelector('[data-selected-asset]'); label.textContent = asset ? t('Ausgewählt: {name}', {name: asset.name}) : '';
    acquireForm.querySelector('[data-clear-asset]').hidden = !asset;
    for (const name of ['quantity', 'unit_cost', 'location_id', 'serial_number']) acquireForm.elements[name].disabled = Boolean(asset);
    if (asset) acquireForm.elements.quantity.value = '1';
    acquireForm.querySelector('[data-acquire-specs]').hidden = Boolean(asset);
  }
  acquireForm.querySelector('[data-clear-asset]').addEventListener('click', () => selectedAsset(null));
  acquireForm.querySelector('[data-asset-search]').addEventListener('input', event => {
    clearTimeout(searchTimer); searchController?.abort();
    const query = event.target.value.trim(), results = acquireForm.querySelector('[data-asset-results]'); results.replaceChildren();
    if (!query) return;
    searchTimer = setTimeout(async () => {
      searchController = new AbortController();
      try {
        const response = await fetch('/api/inventory/assets?per_page=10&q=' + encodeURIComponent(query), {signal: searchController.signal});
        if (!response.ok) throw new Error(t('Die Assets konnten nicht geladen werden.'));
        const value = await response.json(); results.replaceChildren();
        for (const asset of value.rows) {
          const button = document.createElement('button'); button.type = 'button'; button.className = 'btn btn-secondary';
          button.textContent = asset.name + (asset.serial_number ? ' · ' + asset.serial_number : '');
          button.addEventListener('click', () => { selectedAsset(asset); dirty = true; results.replaceChildren(); }); results.append(button);
        }
        if (!value.rows.length) results.textContent = t('Keine passenden Assets.');
      } catch (problem) { if (problem.name !== 'AbortError') showError(acquireForm, problem); }
    }, 250);
  });
  async function openAcquire(id) {
    const initial = await api('/api/wishes/' + id);
    begin(acquireDialog, acquireForm, initial, 'acquire');
    requestKey = crypto.randomUUID ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint8Array(24)), b => b.toString(16).padStart(2, '0')).join('');
    acquireForm.elements.quantity.value = '1'; acquireForm.elements.quantity.max = Math.min(50, initial.missing);
    acquireForm.elements.unit_cost.value = price(initial.unit_price_cents);
    acquireDialog.querySelector('[data-acquire-name]').textContent = initial.name + ' · ' + t('Noch offen: {count}', {count: initial.missing}) + ' · ' + initial.currency;
    acquireForm.querySelector('[data-existing-details]').open = false;
    acquireForm.querySelector('[data-asset-results]').replaceChildren(); selectedAsset(null);
    fields(acquireForm.querySelector('[data-acquire-specs]'), initial.category_id); dirty = false;
  }
  async function openAssemble(id) {
    const initial = await api('/api/wishes/projects/' + id); begin(assembleDialog, assembleForm, initial, 'assemble');
    fields(assembleForm.querySelector('[data-assemble-specs]'), null);
  }
  assembleForm.elements.category_id.addEventListener('change', () => fields(assembleForm.querySelector('[data-assemble-specs]'), assembleForm.elements.category_id.value));
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-new-wish],[data-new-project],[data-edit-wish],[data-edit-project],[data-acquire-wish],[data-assemble-project]');
    if (!button || busy) return;
    opener = button; pageError.hidden = true; button.disabled = true;
    try {
      if (button.hasAttribute('data-new-wish')) await openWish();
      else if (button.hasAttribute('data-new-project')) await openProject();
      else if (button.dataset.editWish) await openWish(button.dataset.editWish);
      else if (button.dataset.editProject) await openProject(button.dataset.editProject);
      else if (button.dataset.acquireWish) await openAcquire(button.dataset.acquireWish);
      else await openAssemble(button.dataset.assembleProject);
    } catch (problem) { showError(document, problem); } finally { button.disabled = false; }
  });
  wishForm.addEventListener('submit', event => {event.preventDefault(); submit(wishForm, async () => {
    const value = ids(payload(wishForm), ['project_id','category_id']); value.quantity = Number(value.quantity); value.expectedRevision = row.revision;
    await api('/api/wishes' + (row.id ? '/' + row.id : ''), row.id ? 'PUT' : 'POST', value); done();
  });});
  projectForm.addEventListener('submit', event => {event.preventDefault(); submit(projectForm, async () => {
    const value = {...payload(projectForm), expectedRevision: row.revision};
    const saved = await api('/api/wishes/projects' + (row.id ? '/' + row.id : ''), row.id ? 'PUT' : 'POST', value);
    done('/wishes/projects/' + saved.id);
  });});
  acquireForm.addEventListener('submit', event => {event.preventDefault(); submit(acquireForm, async () => {
    const value = ids(payload(acquireForm), ['location_id']); value.quantity = existingAsset ? 1 : Number(value.quantity); value.expectedRevision = row.revision; value.requestKey = requestKey;
    if (existingAsset) {value.asset_id = existingAsset.id; delete value.unit_cost;}
    else value.specs = specs(acquireForm.querySelector('[data-acquire-specs]'));
    await api('/api/wishes/' + row.id + '/acquire', 'POST', value); done();
  });});
  assembleForm.addEventListener('submit', event => {event.preventDefault(); submit(assembleForm, async () => {
    const value = ids(payload(assembleForm), ['location_id','category_id']); value.expectedRevision = row.revision; value.specs = specs(assembleForm.querySelector('[data-assemble-specs]'));
    await api('/api/wishes/projects/' + row.id + '/assemble', 'POST', value); done();
  });});
  wishForm.querySelector('[data-archive-wish]').addEventListener('click', () => submit(wishForm, async () => {
    await api('/api/wishes/' + row.id, 'PUT', {expectedRevision: row.revision, archived: !row.archived}); done();
  }));
  wishForm.querySelector('[data-delete-wish]').addEventListener('click', () => {
    if (confirm(t('Wunsch und Recherche löschen? Bereits erfasste Assets bleiben erhalten.'))) submit(wishForm, async () => {await api('/api/wishes/' + row.id, 'DELETE', {expectedRevision: row.revision}); done();});
  });
  projectForm.querySelector('[data-delete-project]').addEventListener('click', () => {
    if (confirm(t('Projekt löschen? Seine Wünsche bleiben privat bei ihren Erstellern erhalten. Assets werden nicht gelöscht.'))) submit(projectForm, async () => {await api('/api/wishes/projects/' + row.id, 'DELETE', {expectedRevision: row.revision}); done('/wishes?tab=projects');});
  });
  document.querySelector('[data-page-size]').addEventListener('change', event => event.target.form.requestSubmit());
})();
