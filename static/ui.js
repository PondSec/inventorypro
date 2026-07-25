const sidebarStorageKey = 'inventorypro.sidebar.collapsed';
const sidebarToggleButtons = document.querySelectorAll('[data-sidebar-toggle]');
const sidebarElement = document.querySelector('.app-sidebar');
const bodyElement = document.body;
let sidebarFocusHandler = null;
let sidebarLastFocus = null;
let modalKeydownHandler = null;
let activeModal = null;
let modalLastFocus = null;
let featherRetryTimer = null;

const fallbackFeatherPaths = {
  activity: '<path d="M22 12h-4l-3 7-6-14-3 7H2"></path>',
  'arrow-up-down': '<path d="m21 16-4 4-4-4"></path><path d="M17 20V4"></path><path d="m3 8 4-4 4 4"></path><path d="M7 4v16"></path>',
  'bar-chart-2': '<line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line>',
  'book-open': '<path d="M2 4h7a3 3 0 0 1 3 3v13a3 3 0 0 0-3-3H2z"></path><path d="M22 4h-7a3 3 0 0 0-3 3v13a3 3 0 0 1 3-3h7z"></path>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"></rect><path d="M16 2v4"></path><path d="M8 2v4"></path><path d="M3 10h18"></path>',
  clock: '<circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path>',
  cpu: '<rect x="6" y="6" width="12" height="12" rx="2"></rect><path d="M9 2v4"></path><path d="M15 2v4"></path><path d="M9 18v4"></path><path d="M15 18v4"></path><path d="M2 9h4"></path><path d="M2 15h4"></path><path d="M18 9h4"></path><path d="M18 15h4"></path>',
  edit: '<path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"></path>',
  'git-merge': '<circle cx="18" cy="18" r="3"></circle><circle cx="6" cy="6" r="3"></circle><path d="M6 9v3a6 6 0 0 0 6 6h3"></path><path d="M18 6v12"></path>',
  home: '<path d="m3 11 9-8 9 8"></path><path d="M5 10v10h14V10"></path><path d="M9 20v-6h6v6"></path>',
  layers: '<path d="m12 2 9 5-9 5-9-5Z"></path><path d="m3 12 9 5 9-5"></path><path d="m3 17 9 5 9-5"></path>',
  layout: '<rect x="3" y="3" width="18" height="18" rx="2"></rect><path d="M3 9h18"></path><path d="M9 21V9"></path>',
  'life-buoy': '<circle cx="12" cy="12" r="10"></circle><circle cx="12" cy="12" r="4"></circle><path d="M4.9 4.9 9.2 9.2"></path><path d="m14.8 14.8 4.3 4.3"></path><path d="m19.1 4.9-4.3 4.3"></path><path d="m9.2 14.8-4.3 4.3"></path>',
  'link-2': '<path d="M9 17H7a5 5 0 0 1 0-10h2"></path><path d="M15 7h2a5 5 0 0 1 0 10h-2"></path><path d="M8 12h8"></path>',
  lock: '<rect x="3" y="11" width="18" height="10" rx="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path>',
  'log-out': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><path d="M16 17l5-5-5-5"></path><path d="M21 12H9"></path>',
  'map-pin': '<path d="M21 10c0 7-9 12-9 12S3 17 3 10a9 9 0 1 1 18 0Z"></path><circle cx="12" cy="10" r="3"></circle>',
  menu: '<path d="M4 6h16"></path><path d="M4 12h16"></path><path d="M4 18h16"></path>',
  monitor: '<rect x="3" y="4" width="18" height="12" rx="2"></rect><path d="M8 20h8"></path><path d="M12 16v4"></path>',
  'more-horizontal': '<circle cx="12" cy="12" r="1"></circle><circle cx="19" cy="12" r="1"></circle><circle cx="5" cy="12" r="1"></circle>',
  'more-vertical': '<circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="19" r="1"></circle>',
  package: '<path d="m16.5 9.4-9-5.2"></path><path d="M21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.7Z"></path><path d="M3.3 7 12 12l8.7-5"></path><path d="M12 22V12"></path>',
  plus: '<path d="M12 5v14"></path><path d="M5 12h14"></path>',
  'plus-circle': '<circle cx="12" cy="12" r="10"></circle><path d="M12 8v8"></path><path d="M8 12h8"></path>',
  search: '<circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path>',
  settings: '<circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 4.6 15 1.7 1.7 0 0 0 3 14H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1A1.7 1.7 0 0 0 19.4 9c.2.6.8 1 1.6 1H21a2 2 0 1 1 0 4h-.1c-.7 0-1.3.4-1.5 1Z"></path>',
  'share-2': '<circle cx="18" cy="5" r="3"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><path d="m8.6 13.5 6.8 4"></path><path d="m15.4 6.5-6.8 4"></path>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"></path>',
  'shopping-cart': '<circle cx="8" cy="21" r="1"></circle><circle cx="19" cy="21" r="1"></circle><path d="M2.1 2.1h3l2.7 12.4a2 2 0 0 0 2 1.6h7.3a2 2 0 0 0 2-1.6L21 7H6"></path>',
  sliders: '<path d="M4 21v-7"></path><path d="M4 10V3"></path><path d="M12 21v-9"></path><path d="M12 8V3"></path><path d="M20 21v-5"></path><path d="M20 12V3"></path><path d="M2 14h4"></path><path d="M10 8h4"></path><path d="M18 16h4"></path>',
  'trash-2': '<path d="M3 6h18"></path><path d="M8 6V4h8v2"></path><path d="M19 6l-1 14H6L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M22 21v-2a4 4 0 0 0-3-3.9"></path><path d="M16 3.1a4 4 0 0 1 0 7.8"></path>',
  x: '<path d="M18 6 6 18"></path><path d="m6 6 12 12"></path>',
  'x-circle': '<circle cx="12" cy="12" r="10"></circle><path d="m15 9-6 6"></path><path d="m9 9 6 6"></path>'
};

const applyFallbackFeatherIcons = () => {
  const icons = document.querySelectorAll('i[data-feather]');
  icons.forEach((icon) => {
    const name = icon.getAttribute('data-feather') || '';
    const paths = fallbackFeatherPaths[name];
    if (!paths) {
      return;
    }
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    svg.setAttribute('width', '24');
    svg.setAttribute('height', '24');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '2');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    svg.setAttribute('class', `feather feather-${name} ${icon.getAttribute('class') || ''}`.trim());
    svg.innerHTML = paths;
    icon.replaceWith(svg);
  });
  return icons.length > 0;
};

const sanitizeFeatherBindings = () => {
  document.querySelectorAll('i[data-feather]').forEach((icon) => {
    icon.removeAttribute(':data-feather');
    icon.removeAttribute('x-bind:data-feather');
  });
};

const refreshFeatherIcons = () => {
  sanitizeFeatherBindings();
  const usedFallbacks = applyFallbackFeatherIcons();
  if (window.feather && typeof window.feather.replace === 'function') {
    try {
      window.feather.replace();
      return true;
    } catch (error) {
      console.warn('Icon refresh skipped unsupported icon:', error.message);
      return applyFallbackFeatherIcons() || usedFallbacks;
    }
  }
  return usedFallbacks;
};

window.InventoryRefreshIcons = refreshFeatherIcons;

window.logout = async function logout() {
  try {
    const response = await fetch('/logout', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }
    });

    if (response.ok) {
      window.location.href = '/login';
      return;
    }

    const data = await response.json().catch(() => ({}));
    window.alert('Logout fehlgeschlagen: ' + (data.error || 'Unbekannter Fehler'));
  } catch (error) {
    window.alert('Netzwerkfehler: ' + error.message);
  }
};

const scheduleFeatherRefresh = () => {
  let attempts = 0;
  const maxAttempts = 25;
  const retry = () => {
    attempts += 1;
    if (refreshFeatherIcons() || attempts >= maxAttempts) {
      if (featherRetryTimer) {
        clearTimeout(featherRetryTimer);
        featherRetryTimer = null;
      }
      return;
    }
    featherRetryTimer = setTimeout(retry, 120);
  };
  retry();
};

document.addEventListener('DOMContentLoaded', () => {
  scheduleFeatherRefresh();
  if (window.MutationObserver) {
    const observer = new MutationObserver((mutations) => {
      const hasNewIcons = mutations.some((mutation) =>
        Array.from(mutation.addedNodes || []).some((node) => {
          if (!(node instanceof Element)) {
            return false;
          }
          return node.matches('[data-feather]') || node.querySelector?.('[data-feather]');
        })
      );
      if (hasNewIcons) {
        scheduleFeatherRefresh();
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }
});

const getFocusableElements = (container) => {
  if (!container) {
    return [];
  }
  return Array.from(
    container.querySelectorAll(
      'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
  ).filter((el) => !el.hasAttribute('aria-hidden'));
};

const trapFocus = (event, container) => {
  const focusable = getFocusableElements(container);
  if (!focusable.length) {
    event.preventDefault();
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
};

const releaseSidebarFocus = () => {
  if (sidebarFocusHandler) {
    document.removeEventListener('keydown', sidebarFocusHandler);
    sidebarFocusHandler = null;
  }
  if (sidebarLastFocus) {
    sidebarLastFocus.focus();
    sidebarLastFocus = null;
  }
};

const activateSidebarFocus = () => {
  if (!sidebarElement) {
    return;
  }
  sidebarLastFocus = document.activeElement;
  const focusable = getFocusableElements(sidebarElement);
  const target = focusable[0] || sidebarElement;
  if (!sidebarElement.hasAttribute('tabindex')) {
    sidebarElement.setAttribute('tabindex', '-1');
  }
  target.focus({ preventScroll: true });
  sidebarFocusHandler = (event) => {
    if (!bodyElement.classList.contains('sidebar-open')) {
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      setSidebarCollapsed(true);
      return;
    }
    if (event.key === 'Tab') {
      trapFocus(event, sidebarElement);
    }
  };
  document.addEventListener('keydown', sidebarFocusHandler);
};

const setSidebarCollapsed = (collapsed) => {
  bodyElement.classList.toggle('sidebar-collapsed', collapsed);
  bodyElement.classList.toggle('sidebar-open', !collapsed);
  sidebarToggleButtons.forEach((button) => {
    button.setAttribute('aria-pressed', collapsed ? 'true' : 'false');
    button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    button.setAttribute(
      'title',
      collapsed ? 'Navigation ausklappen' : 'Navigation einklappen'
    );
  });
  if (mobileQuery.matches) {
    if (collapsed) {
      releaseSidebarFocus();
    } else {
      activateSidebarFocus();
    }
  }
};

const mobileQuery = window.matchMedia('(max-width: 1024px)');
const responsiveTableSelector = 'table.responsive-table';
let responsiveTableFrame = null;

const applyResponsiveTableLabels = () => {
  const tables = document.querySelectorAll(responsiveTableSelector);
  tables.forEach((table) => {
    const headers = Array.from(table.querySelectorAll('thead th')).map((th) =>
      th.textContent.trim()
    );
    if (!headers.length) {
      return;
    }
    table.querySelectorAll('tbody tr').forEach((row) => {
      Array.from(row.children).forEach((cell, index) => {
        if (!cell.matches('td, th')) {
          return;
        }
        if (!cell.getAttribute('data-label') && headers[index]) {
          cell.setAttribute('data-label', headers[index]);
        }
      });
    });
  });
};

const scheduleResponsiveTableUpdate = () => {
  if (responsiveTableFrame) {
    return;
  }
  responsiveTableFrame = window.requestAnimationFrame(() => {
    applyResponsiveTableLabels();
    responsiveTableFrame = null;
  });
};

const applyResponsiveSidebarState = () => {
  if (mobileQuery.matches) {
    setSidebarCollapsed(true);
    return;
  }

  const storedSidebarState = localStorage.getItem(sidebarStorageKey);
  if (storedSidebarState !== null) {
    setSidebarCollapsed(storedSidebarState === 'true');
  } else {
    setSidebarCollapsed(false);
  }
};

applyResponsiveSidebarState();
mobileQuery.addEventListener('change', applyResponsiveSidebarState);
document.addEventListener('DOMContentLoaded', scheduleResponsiveTableUpdate);

const tableObserver = new MutationObserver(scheduleResponsiveTableUpdate);
tableObserver.observe(document.body, { childList: true, subtree: true });

sidebarToggleButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const nextState = !bodyElement.classList.contains('sidebar-collapsed');
    setSidebarCollapsed(nextState);
    if (!mobileQuery.matches) {
      localStorage.setItem(sidebarStorageKey, String(nextState));
    }
  });
});

document.addEventListener('click', (event) => {
  if (!mobileQuery.matches || bodyElement.classList.contains('sidebar-collapsed')) {
    return;
  }

  const target = event.target;
  if (target.closest('[data-sidebar-toggle]') || target.closest('.app-sidebar')) {
    return;
  }

  setSidebarCollapsed(true);
});

const isElementVisible = (element) => {
  if (!element) {
    return false;
  }
  return !!(element.offsetParent || element.getClientRects().length);
};

const getActiveModal = () => {
  const modals = Array.from(document.querySelectorAll('.modal'));
  return modals.find((modal) => isElementVisible(modal));
};

const releaseModalFocus = () => {
  if (modalKeydownHandler) {
    document.removeEventListener('keydown', modalKeydownHandler);
    modalKeydownHandler = null;
  }
  if (activeModal) {
    activeModal = null;
  }
  if (modalLastFocus) {
    modalLastFocus.focus();
    modalLastFocus = null;
  }
  if (!getActiveModal()) {
    bodyElement.classList.remove('modal-open');
  }
};

const closeActiveModal = () => {
  if (!activeModal) {
    return;
  }
  const closeButton = activeModal.querySelector('[data-modal-close]');
  if (closeButton) {
    closeButton.click();
  }
};

const activateModalFocus = (modal) => {
  if (!modal || activeModal === modal) {
    return;
  }
  releaseModalFocus();
  activeModal = modal;
  modalLastFocus = document.activeElement;
  bodyElement.classList.add('modal-open');
  const panel = modal.querySelector('.modal-panel') || modal;
  if (!panel.hasAttribute('tabindex')) {
    panel.setAttribute('tabindex', '-1');
  }
  const focusable = getFocusableElements(panel);
  (focusable[0] || panel).focus({ preventScroll: true });
  if (!modal.dataset.modalListenersAttached) {
    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        closeActiveModal();
      }
    });
    modal.dataset.modalListenersAttached = 'true';
  }
  modalKeydownHandler = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeActiveModal();
      return;
    }
    if (event.key === 'Tab') {
      trapFocus(event, panel);
    }
  };
  document.addEventListener('keydown', modalKeydownHandler);
};

const syncModalState = () => {
  const visibleModal = getActiveModal();
  if (visibleModal) {
    activateModalFocus(visibleModal);
  } else if (activeModal) {
    releaseModalFocus();
  }
};

syncModalState();
const modalObserver = new MutationObserver(syncModalState);
modalObserver.observe(document.body, { childList: true, subtree: true, attributes: true });
