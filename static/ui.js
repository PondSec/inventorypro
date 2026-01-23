const sidebarStorageKey = 'inventorypro.sidebar.collapsed';
const themeStorageKey = 'inventorypro.theme';
const sidebarToggleButtons = document.querySelectorAll('[data-sidebar-toggle]');
const themeToggleInputs = document.querySelectorAll('[data-theme-toggle]');
const bodyElement = document.body;
const rootElement = document.documentElement;

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

const setTheme = (theme) => {
  rootElement.setAttribute('data-theme', theme);
  themeToggleInputs.forEach((input) => {
    input.checked = theme === 'dark';
    input.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
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

const storedTheme = localStorage.getItem(themeStorageKey);
if (storedTheme) {
  setTheme(storedTheme);
} else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
  setTheme('dark');
} else {
  setTheme('light');
}

themeToggleInputs.forEach((input) => {
  input.addEventListener('change', (event) => {
    const nextTheme = event.target.checked ? 'dark' : 'light';
    setTheme(nextTheme);
    localStorage.setItem(themeStorageKey, nextTheme);
  });
});
