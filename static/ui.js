const sidebarStorageKey = 'inventorypro.sidebar.collapsed';
const sidebarToggleButtons = document.querySelectorAll('[data-sidebar-toggle]');
const bodyElement = document.body;

const setSidebarCollapsed = (collapsed) => {
  bodyElement.classList.toggle('sidebar-collapsed', collapsed);
  bodyElement.classList.toggle('sidebar-open', !collapsed);
  sidebarToggleButtons.forEach((button) => {
    button.setAttribute('aria-pressed', collapsed ? 'true' : 'false');
    button.setAttribute(
      'title',
      collapsed ? 'Navigation ausklappen' : 'Navigation einklappen'
    );
  });
};

const mobileQuery = window.matchMedia('(max-width: 1024px)');

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

sidebarToggleButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const nextState = !bodyElement.classList.contains('sidebar-collapsed');
    setSidebarCollapsed(nextState);
    if (!mobileQuery.matches) {
      localStorage.setItem(sidebarStorageKey, String(nextState));
    }
  });
});
