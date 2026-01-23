const sidebarStorageKey = 'inventorypro.sidebar.collapsed';
const sidebarToggleButtons = document.querySelectorAll('[data-sidebar-toggle]');
const bodyElement = document.body;

const setSidebarCollapsed = (collapsed) => {
  bodyElement.classList.toggle('sidebar-collapsed', collapsed);
  sidebarToggleButtons.forEach((button) => {
    button.setAttribute('aria-pressed', collapsed ? 'true' : 'false');
    button.setAttribute(
      'title',
      collapsed ? 'Navigation ausklappen' : 'Navigation einklappen'
    );
  });
};

const storedSidebarState = localStorage.getItem(sidebarStorageKey);
if (storedSidebarState !== null) {
  setSidebarCollapsed(storedSidebarState === 'true');
}

sidebarToggleButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const nextState = !bodyElement.classList.contains('sidebar-collapsed');
    setSidebarCollapsed(nextState);
    localStorage.setItem(sidebarStorageKey, String(nextState));
  });
});
