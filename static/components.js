/* Shared keyboard contract for client-side tab panels in every module. */
(() => {
  'use strict';
  const initialized = new WeakSet();
  const tabsOf = list => Array.from(list.querySelectorAll('[role=tab]')).filter(tab => !tab.disabled && tab.getAttribute('aria-disabled') !== 'true');
  function setup() {
    document.querySelectorAll('[role=tablist]').forEach(list => {
      const tabs = tabsOf(list);
      const selected = tabs.find(tab => tab.getAttribute('aria-selected') === 'true') || tabs[0];
      for (const tab of tabs) {
        const value = tab === selected ? '0' : '-1';
        if (tab.getAttribute('tabindex') !== value) tab.setAttribute('tabindex', value);
      }
      if (initialized.has(list)) return;
      initialized.add(list);
      list.addEventListener('keydown', event => {
        const current = event.target.closest('[role=tab]');
        const available = tabsOf(list);
        const index = available.indexOf(current);
        if (index < 0) return;
        const vertical = list.getAttribute('aria-orientation') === 'vertical';
        const forward = vertical ? 'ArrowDown' : 'ArrowRight';
        const backward = vertical ? 'ArrowUp' : 'ArrowLeft';
        let next;
        if (event.key === forward) next = (index + 1) % available.length;
        else if (event.key === backward) next = (index - 1 + available.length) % available.length;
        else if (event.key === 'Home') next = 0;
        else if (event.key === 'End') next = available.length - 1;
        else return;
        event.preventDefault();
        event.stopPropagation();
        available[next].click();
        available[next].focus();
      });
    });
  }
  setup();
  new MutationObserver(setup).observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['aria-selected']});
})();

/* Shared shell controls use native semantics and never depend on a framework. */
(() => {
  const search = document.querySelector('.global-search input');
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k' && search) {
      event.preventDefault(); search.focus(); search.select();
    }
    if (event.key === 'Escape') {
      document.querySelectorAll('[data-account-menu][open]').forEach(menu => {
        menu.open = false; menu.querySelector('summary').focus();
      });
    }
  });
  document.addEventListener('click', event => {
    if (event.target.closest('.nav-group > summary') && document.body.classList.contains('sidebar-collapsed')) {
      document.querySelector('.app-header [data-sidebar-toggle]')?.click();
    }
    document.querySelectorAll('[data-account-menu][open]').forEach(menu => {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });
})();

/* Copyable identifiers retain a useful selection even without Clipboard API. */
document.addEventListener('click', async event => {
  const button = event.target.closest('[data-copy-value]');
  if (!button) return;
  const feedback = document.querySelector('[data-copy-status]');
  try {
    await navigator.clipboard.writeText(button.dataset.copyValue);
    if (feedback) feedback.textContent = 'Kopiert.';
  } catch (_) {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(button.parentElement); selection.removeAllRanges(); selection.addRange(range);
    if (feedback) feedback.textContent = 'Bitte mit Strg/Cmd+C kopieren.';
  }
});
