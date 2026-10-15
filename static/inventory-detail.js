(() => {
  'use strict';
  let dirty = false;
  document.querySelectorAll('form[data-inventory-action]').forEach(form => {
    form.addEventListener('input', () => { dirty = true; });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const button = form.querySelector('button[type=submit]');
      if (button.disabled) return;
      const status = form.querySelector('[data-form-status]');
      button.disabled = true;
      status.textContent = 'Wird gespeichert …';
      try {
        const payload = Object.fromEntries(new FormData(form));
        const response = await fetch(form.dataset.inventoryAction, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Speichern fehlgeschlagen.');
        dirty = false;
        window.location.reload();
      } catch (error) {
        status.setAttribute('role', 'alert');
        status.textContent = error.message || 'Verbindung fehlgeschlagen. Ihre Eingaben bleiben erhalten.';
        button.disabled = false;
      }
    });
  });
  window.addEventListener('beforeunload', event => {
    if (dirty) { event.preventDefault(); event.returnValue = ''; }
  });
})();
