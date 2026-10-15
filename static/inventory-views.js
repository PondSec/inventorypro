(() => {
  'use strict';
  const root = document.querySelector('[data-saved-views]');
  if (!root) return;
  const form = root.querySelector('[data-save-view]');
  const list = root.querySelector('[data-view-list]');
  const status = root.querySelector('[data-view-status]');
  const key = `inventorypro.inventoryViews.${window.inventoryUsername}`;
  const allowed = ['q', 'kind', 'filter', 'sort', 'direction', 'per_page'];
  function query(value) {
    const input = new URLSearchParams(value);
    const output = new URLSearchParams();
    for (const name of allowed) {
      if (input.has(name)) output.set(name, input.get(name).slice(0, 500));
    }
    return output.toString();
  }
  let views = [];
  try {
    const stored = JSON.parse(localStorage.getItem(key) || '[]');
    if (Array.isArray(stored)) views = stored.filter(view => view && typeof view.name === 'string' && typeof view.query === 'string').slice(0, 12);
  } catch (_) { status.textContent = 'Gespeicherte Ansichten sind in diesem Browser nicht verfügbar.'; }
  function persist(next, message) {
    try {
      localStorage.setItem(key, JSON.stringify(next));
      views = next;
      render();
      status.textContent = message;
      return true;
    } catch (_) { status.textContent = 'Speichern nicht möglich. Prüfen Sie die Speichereinstellungen des Browsers.'; return false; }
  }
  function render() {
    list.replaceChildren();
    for (const view of views) {
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = '/inventory?' + query(view.query);
      link.textContent = view.name.slice(0, 60);
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'btn btn-secondary';
      remove.textContent = 'Entfernen';
      remove.setAttribute('aria-label', `${view.name.slice(0, 60)} als gespeicherte Ansicht entfernen`);
      remove.addEventListener('click', () => {
        if (persist(views.filter(candidate => candidate !== view), 'Ansicht entfernt.')) form.elements.view_name.focus();
      });
      item.append(link, remove);
      list.append(item);
    }
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const name = form.elements.view_name.value.trim();
    if (!name) { form.elements.view_name.focus(); return; }
    const existing = views.findIndex(view => view.name === name);
    if (existing < 0 && views.length >= 12) { status.textContent = 'Maximal zwölf Ansichten. Entfernen Sie zuerst eine Ansicht.'; return; }
    const next = views.slice();
    const view = { name: name.slice(0, 60), query: query(location.search) };
    if (existing < 0) next.push(view); else next[existing] = view;
    if (persist(next, existing < 0 ? 'Ansicht gespeichert.' : 'Ansicht aktualisiert.')) form.reset();
  });
  render();
})();
