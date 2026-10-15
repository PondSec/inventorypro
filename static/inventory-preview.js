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
    for (const candidate of rows) {
      candidate.toggleAttribute('data-preview-selected', candidate === row);
      candidate.querySelector('[data-object-link]').setAttribute('aria-expanded', String(candidate === row));
    }
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
    trigger = row.querySelector('[data-object-link]');
    dialog.querySelector('[data-preview-detail]').href = trigger.href;
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
    const link = row.querySelector('[data-object-link]');
    link.setAttribute('aria-haspopup', 'dialog');
    link.setAttribute('aria-controls', dialog.id);
    row.classList.add('preview-row');
    row.addEventListener('click', event => {
      if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const control = event.target.closest('a,button,input,select,textarea,label,summary,[contenteditable]');
      if (control && control !== link) return;
      const selection = window.getSelection();
      if (selection && !selection.isCollapsed && row.contains(selection.anchorNode)) return;
      event.preventDefault();
      if (location.hash === '#preview-' + row.dataset.previewKey) return;
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
