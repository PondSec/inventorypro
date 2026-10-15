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
