(() => {
  'use strict';
  const dialog = document.querySelector('[data-inventory-preview]');
  if (!dialog || !dialog.showModal) return;
  const rows = Array.from(document.querySelectorAll('[data-preview-key]'));
  const fields = dialog.querySelector('[data-preview-fields]');
  let trigger = null;
  function displayLocation() {
    const match = /^#preview-((?:device|asset)-\d+)$/.exec(location.hash);
    const row = match && rows.find(candidate => candidate.dataset.previewKey === match[1]);
    if (!row) {
      if (dialog.open) dialog.close();
      if (trigger && trigger.isConnected) trigger.focus();
      return;
    }
    const data = JSON.parse(row.dataset.preview);
    fields.replaceChildren();
    for (const [key, label] of [['name','Bezeichnung'], ['kind','Art'], ['category','Vorlage'], ['serial','Identifikation'], ['location','Standort'], ['status','Status']]) {
      const item = document.createElement('div');
      const term = document.createElement('dt');
      const value = document.createElement('dd');
      term.textContent = label;
      value.textContent = data[key] || 'Nicht festgelegt';
      item.append(term, value);
      fields.append(item);
    }
    dialog.querySelector('[data-preview-detail]').href = row.querySelector('td a').href;
    if (!dialog.open) dialog.showModal();
  }
  function closePreview() {
    if (history.state && history.state.inventoryPreview) history.back();
    else {
      history.replaceState(history.state, '', location.pathname + location.search);
      displayLocation();
    }
  }
  for (const row of rows) {
    const button = row.querySelector('[data-open-preview]');
    button.addEventListener('click', () => {
      trigger = button;
      history.pushState({...history.state, inventoryPreview: true}, '', '#preview-' + row.dataset.previewKey);
      displayLocation();
    });
  }
  dialog.querySelector('[data-close-preview]').addEventListener('click', closePreview);
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = Array.from(dialog.querySelectorAll('button:not(:disabled), a[href]'));
    const first = controls[0];
    const last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus();
    }
  });
  dialog.addEventListener('cancel', event => { event.preventDefault(); closePreview(); });
  window.addEventListener('popstate', displayLocation);
  displayLocation();
})();
