const sidebarStorageKey = 'inventorypro.sidebar.collapsed';
const sidebarToggleButtons = document.querySelectorAll('[data-sidebar-toggle]');
const sidebarElement = document.querySelector('.app-sidebar');
const bodyElement = document.body;
let sidebarFocusHandler = null;
let sidebarLastFocus = null;
let modalKeydownHandler = null;
let activeModal = null;
let modalLastFocus = null;

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

const setupSidebarSearch = () => {
  const searchInputs = document.querySelectorAll('[data-sidebar-search]');
  if (!searchInputs.length) {
    return;
  }

  const matchesQuery = (label, query) => {
    if (!query) {
      return true;
    }
    return label.toLowerCase().includes(query);
  };

  const applyFilter = (query) => {
    const normalized = query.trim().toLowerCase();
    const items = Array.from(document.querySelectorAll('[data-sidebar-item]'));
    const subgroups = Array.from(document.querySelectorAll('.sidebar-subgroup'));
    const groups = Array.from(document.querySelectorAll('[data-sidebar-group]'));

    items.forEach((item) => {
      const label = (item.getAttribute('data-sidebar-label') || '').trim().toLowerCase();
      const shouldShow = matchesQuery(label, normalized);
      if (item.matches('.sidebar-nav-link, .sidebar-favorite-link, .sidebar-subgroup-toggle')) {
        item.style.display = shouldShow ? '' : 'none';
      }
      item.dataset.sidebarMatch = shouldShow ? 'true' : 'false';
    });

    subgroups.forEach((subgroup) => {
      const toggle = subgroup.querySelector('.sidebar-subgroup-toggle');
      const links = Array.from(subgroup.querySelectorAll('.sidebar-nav-link'));
      const childVisible = links.some((link) => link.style.display !== 'none');
      const toggleMatches = toggle
        ? matchesQuery((toggle.getAttribute('data-sidebar-label') || '').toLowerCase(), normalized)
        : false;
      const shouldShow = !normalized || toggleMatches || childVisible;
      if (toggle) {
        toggle.style.display = shouldShow ? '' : 'none';
      }
      subgroup.style.display = shouldShow ? '' : 'none';
      if (normalized && childVisible) {
        subgroup.open = true;
      } else if (!normalized) {
        subgroup.open = subgroup.hasAttribute('data-default-open') || subgroup.open;
      }
    });

    groups.forEach((group) => {
      const visibleChild = Array.from(group.querySelectorAll('.sidebar-nav-link, .sidebar-subgroup'))
        .some((item) => item.style.display !== 'none');
      group.style.display = !normalized || visibleChild ? '' : 'none';
    });
  };

  searchInputs.forEach((input) => {
    input.addEventListener('input', (event) => {
      applyFilter(event.target.value || '');
    });
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
document.addEventListener('DOMContentLoaded', () => {
  scheduleResponsiveTableUpdate();
  setupSidebarSearch();
});

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
