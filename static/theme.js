(() => {
  const root = document.documentElement;
  const stored = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initial = stored || (prefersDark ? 'dark' : 'light');

  if (initial === 'dark') {
    root.classList.add('dark');
  }

  const updateButtons = () => {
    const isDark = root.classList.contains('dark');
    document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
      button.setAttribute('aria-pressed', String(isDark));
      const label = button.querySelector('[data-theme-label]');
      const icon = button.querySelector('[data-theme-icon]');
      if (label) {
        label.textContent = isDark ? 'Light Mode' : 'Dark Mode';
      }
      if (icon) {
        icon.textContent = isDark ? '☀️' : '🌙';
      }
    });
  };

  const setTheme = (mode) => {
    if (mode === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('theme', mode);
    updateButtons();
  };

  window.InventoryTheme = {
    toggle() {
      const next = root.classList.contains('dark') ? 'light' : 'dark';
      setTheme(next);
    },
    set: setTheme,
  };

  document.addEventListener('DOMContentLoaded', updateButtons);
})();
