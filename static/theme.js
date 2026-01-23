const themeStorageKey = 'inventorypro.theme';
const themeToggleButtons = document.querySelectorAll('[data-theme-toggle]');
const themeLabelSelector = '[data-theme-label]';

const getSystemTheme = () => {
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    return 'dark';
  }
  return 'light';
};

const applyTheme = (theme, persist = true) => {
  document.body.dataset.theme = theme;
  if (persist) {
    localStorage.setItem(themeStorageKey, theme);
  }

  themeToggleButtons.forEach((button) => {
    button.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
    const label = button.querySelector(themeLabelSelector);
    if (label) {
      label.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
    }
  });
};

const storedTheme = localStorage.getItem(themeStorageKey);
applyTheme(storedTheme || getSystemTheme(), false);

if (!storedTheme && window.matchMedia) {
  const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  mediaQuery.addEventListener('change', (event) => {
    applyTheme(event.matches ? 'dark' : 'light', false);
  });
}

themeToggleButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const currentTheme = document.body.dataset.theme === 'dark' ? 'dark' : 'light';
    const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(nextTheme);
  });
});
