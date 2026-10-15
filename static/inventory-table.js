/* URL-backed filters, bounded pagination, and page-scoped selection/export. */
(() => {
  'use strict';
  const form = document.querySelector('[data-inventory-filters]');
  if (!form) return;
  form.classList.add('is-enhanced');
  document.addEventListener('change', event => {
    if (event.target.form === form && event.target.matches('select')) form.requestSubmit();
  });
  form.querySelector('[type=search]').addEventListener('search', event => {
    if (!event.target.value) form.requestSubmit();
  });
  const items = Array.from(document.querySelectorAll('[data-select-entry]'));
  const all = document.querySelector('[data-select-all]');
  const toolbar = document.querySelector('[data-selection-toolbar]');
  if (!toolbar || !all) return;
  function update() {
    const selected = items.filter(item => item.checked);
    toolbar.hidden = !selected.length;
    toolbar.querySelector('[data-selection-count]').textContent = selected.length + (selected.length === 1 ? ' Eintrag' : ' Einträge') + ' dieser Seite ausgewählt';
    all.checked = !!items.length && selected.length === items.length;
    all.indeterminate = selected.length > 0 && selected.length < items.length;
    for (const item of items) item.closest('tr').toggleAttribute('data-bulk-selected', item.checked);
    const url = new URL(document.querySelector('[data-inventory-export]').href);
    url.searchParams.set('selection', selected.map(item => item.dataset.selectEntry).join(','));
    toolbar.querySelector('[data-selection-export]').href = url.href;
  }
  all.addEventListener('change', () => {for (const item of items) item.checked = all.checked; update();});
  items.forEach(item => item.addEventListener('change', update));
  toolbar.querySelector('[data-clear-selection]').addEventListener('click', () => {items.forEach(item => {item.checked = false;});update();all.focus();});
  update();
})();
