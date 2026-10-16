/* One object panel: docked beside the work list, modal only on narrow screens. */
(() => {
  'use strict';
  const dialog = document.querySelector('[data-inventory-preview]');
  if (!dialog || !dialog.showModal) return;
  const rows = Array.from(document.querySelectorAll('[data-preview-key]'));
  const content = dialog.querySelector('[data-object-content]');
  const docked = window.matchMedia('(min-width: 1280px)');
  let trigger = null;
  let currentRow = null;
  let controller = null;
  let loaded = false;

  function showMode() {
    const active = dialog.contains(document.activeElement) ? document.activeElement : null;
    const shouldDock = docked.matches;
    if (dialog.open && dialog.classList.contains('object-panel--docked') !== shouldDock) dialog.close();
    dialog.classList.toggle('object-panel--docked', shouldDock);
    dialog.setAttribute('aria-modal', String(!shouldDock));
    document.body.classList.toggle('has-object-panel', shouldDock && !!currentRow);
    if (currentRow && !dialog.open) {
      if (shouldDock) dialog.show(); else dialog.showModal();
      if (active) active.focus({preventScroll: true});
    }
  }

  function selectedTab() {
    return location.hash.split('/')[1] || 'overview';
  }

  function switchTab(key, updateLocation = false) {
    const tabs = Array.from(content.querySelectorAll('[data-object-tab]'));
    const selected = tabs.find(tab => tab.dataset.objectTab === key) || tabs[0];
    if (!selected) return;
    for (const tab of tabs) {
      const active = tab === selected;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      content.querySelector('#' + tab.getAttribute('aria-controls')).hidden = !active;
    }
    if (updateLocation) history.replaceState(history.state, '', '#preview-' + currentRow.dataset.previewKey + (selected.dataset.objectTab === 'overview' ? '' : '/' + selected.dataset.objectTab));
  }

  function message(text, error = false) {
    content.replaceChildren();
    const name = document.createElement('h2');
    name.id = 'object-panel-name';
    name.className = 'object-loading-name';
    name.textContent = JSON.parse(currentRow.dataset.preview).name;
    const status = document.createElement('p');
    status.className = error ? 'form-error' : 'muted';
    status.setAttribute('role', error ? 'alert' : 'status');
    status.textContent = text;
    content.append(name, status);
    if (error) {
      const retry = document.createElement('button');
      retry.type = 'button'; retry.className = 'btn btn-secondary';
      retry.dataset.panelRetry = ''; retry.textContent = uiText('Erneut laden'); content.append(retry);
      const detail = document.createElement('a');
      detail.href = trigger.href; detail.className = 'btn btn-secondary';
      detail.textContent = uiText('Detailseite'); content.append(detail);
    } else {
      const skeleton = document.createElement('div');
      skeleton.className = 'object-skeleton'; skeleton.setAttribute('aria-hidden', 'true');
      content.append(skeleton);
    }
  }

  async function loadObject(row) {
    if (controller) controller.abort();
    const pending = new AbortController(); controller = pending;
    loaded = false; content.setAttribute('aria-busy', 'true');
    message(uiText('Objektdaten werden geladen …'));
    try {
      const key = row.dataset.previewKey.split('-');
      const response = await fetch('/api/inventory/' + key[0] + '/' + key[1] + '/panel?format=html', {signal: pending.signal, headers: {'Accept': 'text/html'}});
      if (response.redirected) throw new Error(uiText('Die Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.'));
      if (!response.ok) throw new Error(response.status === 403 ? uiText('Keine Berechtigung für diesen Eintrag.') : response.status === 404 ? uiText('Dieser Eintrag ist nicht mehr vorhanden.') : uiText('Die Objektdaten konnten nicht geladen werden.'));
      const html = await response.text();
      if (pending.signal.aborted || currentRow !== row) return;
      // Only our server-rendered, autoescaped fragment is inserted, never object
      // field content interpreted as HTML in the browser.
      content.innerHTML = html;
      loaded = true; switchTab(selectedTab());
    } catch (error) {
      if (pending.signal.aborted || currentRow !== row) return;
      message(error.message || uiText('Verbindung fehlgeschlagen. Bitte versuchen Sie es erneut.'), true);
    } finally {
      if (controller === pending) content.removeAttribute('aria-busy');
    }
  }

  function displayLocation() {
    const match = /^#preview-((?:device|asset)-\d+)(?:\/(overview|details|accessories|tickets|history))?$/.exec(location.hash);
    const row = match && rows.find(candidate => candidate.dataset.previewKey === match[1]);
    for (const candidate of rows) {
      candidate.toggleAttribute('data-preview-selected', candidate === row);
      candidate.querySelector('[data-object-link]').setAttribute('aria-expanded', String(candidate === row));
    }
    if (!row) {
      currentRow = null; loaded = false;
      if (controller) controller.abort();
      document.body.classList.remove('has-object-panel');
      if (dialog.open) {
        dialog.close();
        if (trigger?.isConnected) trigger.focus({preventScroll:true});
      }
      return;
    }
    const changed = currentRow !== row;
    currentRow = row; trigger = row.querySelector('[data-object-link]');
    if (changed) loadObject(row);
    else if (loaded) switchTab(selectedTab());
    showMode();
  }

  function closePanel() {
    if (history.state?.inventoryPreview) history.back();
    else { history.replaceState(history.state, '', location.pathname + location.search); displayLocation(); }
  }

  for (const row of rows) {
    const link = row.querySelector('[data-object-link]');
    link.setAttribute('aria-haspopup', 'dialog'); link.setAttribute('aria-controls', dialog.id);
    row.classList.add('preview-row');
    row.addEventListener('click', event => {
      if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const control = event.target.closest('a,button,input,select,textarea,label,summary,[contenteditable]');
      if (control && control !== link) return;
      const selection = window.getSelection();
      if (selection && !selection.isCollapsed && row.contains(selection.anchorNode)) return;
      event.preventDefault();
      if (currentRow === row) return;
      const url = '#preview-' + row.dataset.previewKey;
      if (currentRow) history.replaceState(history.state, '', url);
      else history.pushState({...history.state, inventoryPreview: true}, '', url);
      displayLocation();
    });
  }
  dialog.querySelector('[data-close-preview]').addEventListener('click', closePanel);
  content.addEventListener('click', event => {
    const tab = event.target.closest('[data-object-tab]');
    if (tab) switchTab(tab.dataset.objectTab, true);
    if (event.target.closest('[data-panel-retry]')) loadObject(currentRow);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && dialog.open && docked.matches) { event.preventDefault(); closePanel(); }
  });
  dialog.addEventListener('cancel', event => {event.preventDefault(); closePanel();});
  docked.addEventListener('change', () => {if (currentRow) showMode();});
  window.addEventListener('popstate', displayLocation);
  displayLocation();
})();
