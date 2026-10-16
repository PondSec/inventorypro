/* Explicit page selection; atomic, revision-checked changes on canonical assets. */
(() => {
  'use strict';
  const dialog = document.querySelector('[data-bulk-dialog]');
  if (!dialog) return;
  const form = dialog.querySelector('form'), error = dialog.querySelector('[data-bulk-error]');
  const buttons = [...document.querySelectorAll('[data-bulk-action]')];
  const t = window.uiText;
  let items = [], action = '', opener = null, busy = false, dirty = false;
  async function api(url, payload) {
    const response = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || t('Die Aktion konnte nicht abgeschlossen werden.'));
    return data;
  }
  function showError(problem) { error.textContent = problem.message; error.hidden = false; error.scrollIntoView({block: 'nearest'}); }
  function close() {
    if (busy || dirty && !confirm(t('Ungespeicherte Änderungen verwerfen?'))) return;
    dirty = false; dialog.close(); opener?.focus();
  }
  dialog.querySelectorAll('[data-bulk-close]').forEach(button => button.addEventListener('click', close));
  dialog.addEventListener('cancel', event => {event.preventDefault(); close();});
  dialog.addEventListener('input', () => dirty = true);
  dialog.addEventListener('change', () => dirty = true);
  window.addEventListener('beforeunload', event => {if (dirty) {event.preventDefault(); event.returnValue = '';}});
  dialog.querySelectorAll('[data-bulk-field]').forEach(field => {
    field.querySelector('[data-field-action]').addEventListener('change', event => {
      const set = event.target.value === 'set';
      field.querySelector('[data-field-value-label]').hidden = !set;
      field.querySelector('[data-field-value]').disabled = !set;
      field.querySelector('[data-field-value]').required = set;
    });
  });
  buttons.forEach(button => button.addEventListener('click', async () => {
    if (busy) return;
    opener = button; action = button.dataset.bulkAction; items = []; dirty = false; error.hidden = true;
    form.reset();
    dialog.querySelectorAll('[data-field-value-label]').forEach(label => label.hidden = true);
    dialog.querySelectorAll('[data-field-value]').forEach(input => {input.disabled = true; input.required = false;});
    dialog.querySelector('[data-bulk-title]').textContent = t(action === 'delete' ? 'Auswahl löschen' : 'Gemeinsam bearbeiten');
    dialog.querySelector('[data-bulk-edit]').hidden = action === 'delete';
    dialog.querySelector('[data-bulk-delete]').hidden = action !== 'delete';
    dialog.querySelector('[data-bulk-submit]').textContent = t(action === 'delete' ? 'Ausgewählte Assets endgültig löschen' : 'Änderungen speichern');
    dialog.querySelector('[data-bulk-summary]').textContent = t('Auswahl wird geprüft …');
    dialog.querySelector('[data-bulk-names]').replaceChildren();
    dialog.querySelector('[data-bulk-submit]').disabled = true;
    dialog.showModal(); busy = true;
    try {
      const selected = [...document.querySelectorAll('[data-select-entry]:checked')].map(input => ({id: Number(input.dataset.selectEntry.replace(/^asset-/, ''))}));
      const data = await api('/api/inventory/assets/bulk/prepare', {items: selected});
      items = data.items;
      dialog.querySelector('[data-bulk-summary]').textContent = t(items.length === 1 ? '{0} Asset ausgewählt.' : '{0} Assets ausgewählt.', [items.length]);
      for (const item of items) {const li = document.createElement('li'); li.textContent = item.name; dialog.querySelector('[data-bulk-names]').append(li);}
      for (const [key, values] of [['category_id', data.options.categories], ['location_id', data.options.locations]]) {
        const select = dialog.querySelector(`[data-bulk-field="${key}"] [data-field-value]`);
        select.replaceChildren(new Option(t('Bitte auswählen'), ''), ...values.map(value => new Option(value.name, value.id)));
      }
      dialog.querySelector('[data-bulk-submit]').disabled = false;
    } catch (problem) {showError(problem);} finally {busy = false;}
  }));
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (busy || !items.length) return;
    const changes = {};
    if (action === 'update') {
      for (const field of dialog.querySelectorAll('[data-bulk-field]')) {
        const mode = field.querySelector('[data-field-action]').value, key = field.dataset.bulkField;
        if (mode === 'keep') continue;
        changes[key] = mode === 'clear' ? null : field.querySelector('[data-field-value]').value;
        if (mode === 'set' && key.endsWith('_id')) changes[key] = Number(changes[key]);
      }
      if (!Object.keys(changes).length) {showError(new Error(t('Bitte mindestens ein gemeinsames Feld auswählen.'))); return;}
    }
    busy = true; error.hidden = true;
    dialog.querySelectorAll('button').forEach(button => button.disabled = true);
    try {await api('/api/inventory/assets/bulk', {action, items, changes}); dirty = false; location.reload();}
    catch (problem) {showError(problem);}
    finally {busy = false; dialog.querySelectorAll('button').forEach(button => button.disabled = false);}
  });
})();
