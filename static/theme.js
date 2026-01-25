(() => {
  const root = document.documentElement;
  const stored = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initial = stored || (prefersDark ? 'dark' : 'light');
  const customizationKey = 'inventorypro.customization';
  const defaultCustomization = {
    branding: {
      name: 'Inventory Pro',
      tagline: 'Smart Asset Hub',
      primary: '#4f46e5',
      accent: '#14b8a6',
      background: '#f8fafc',
      radius: 16,
      density: 1,
      logoDataUrl: '',
    },
    formStyle: {
      buttonColor: '#4f46e5',
      buttonText: '#ffffff',
      inputBackground: '#ffffff',
      inputBorder: '#e2e8f0',
      spacing: 16,
    },
    layout: {
      widgets: [],
    },
  };

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

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

  const hexToRgb = (hex) => {
    const normalized = hex.replace('#', '');
    if (normalized.length === 3) {
      const r = parseInt(normalized[0] + normalized[0], 16);
      const g = parseInt(normalized[1] + normalized[1], 16);
      const b = parseInt(normalized[2] + normalized[2], 16);
      return [r, g, b];
    }
    if (normalized.length !== 6) {
      return [79, 70, 229];
    }
    return [
      parseInt(normalized.slice(0, 2), 16),
      parseInt(normalized.slice(2, 4), 16),
      parseInt(normalized.slice(4, 6), 16),
    ];
  };

  const adjustHex = (hex, amount) => {
    const [r, g, b] = hexToRgb(hex);
    const factor = 1 + amount;
    const next = [
      clamp(Math.round(r * factor), 0, 255),
      clamp(Math.round(g * factor), 0, 255),
      clamp(Math.round(b * factor), 0, 255),
    ];
    return `#${next.map((value) => value.toString(16).padStart(2, '0')).join('')}`;
  };

  const mergeCustomization = (data = {}) => ({
    ...defaultCustomization,
    ...data,
    branding: { ...defaultCustomization.branding, ...(data.branding || {}) },
    formStyle: { ...defaultCustomization.formStyle, ...(data.formStyle || {}) },
    layout: { ...defaultCustomization.layout, ...(data.layout || {}) },
  });

  const applySpacingScale = (density) => {
    const base = [4, 8, 12, 16, 20, 24, 32, 40, 48, 64];
    base.forEach((value, index) => {
      const scaled = Math.round(value * density);
      root.style.setProperty(`--space-${index + 1}`, `${scaled}px`);
    });
  };

  const applyCustomizationStyles = (customization) => {
    const branding = customization.branding;
    const formStyle = customization.formStyle;
    const primary = branding.primary || defaultCustomization.branding.primary;
    const accentSoft = hexToRgb(primary).join(', ');

    root.style.setProperty('--color-bg', branding.background || defaultCustomization.branding.background);
    root.style.setProperty('--color-accent', primary);
    root.style.setProperty('--color-accent-strong', adjustHex(primary, -0.18));
    root.style.setProperty('--color-accent-soft', `rgba(${accentSoft}, 0.12)`);
    root.style.setProperty('--brand-accent', branding.accent || defaultCustomization.branding.accent);
    root.style.setProperty('--radius-md', `${branding.radius}px`);
    root.style.setProperty('--radius-sm', `${Math.max(6, branding.radius - 6)}px`);
    root.style.setProperty('--radius-lg', `${branding.radius + 6}px`);
    root.style.setProperty('--button-bg', formStyle.buttonColor || defaultCustomization.formStyle.buttonColor);
    root.style.setProperty('--button-text', formStyle.buttonText || defaultCustomization.formStyle.buttonText);
    root.style.setProperty('--input-bg', formStyle.inputBackground || defaultCustomization.formStyle.inputBackground);
    root.style.setProperty('--input-border', formStyle.inputBorder || defaultCustomization.formStyle.inputBorder);
    root.style.setProperty('--form-gap', `${formStyle.spacing || defaultCustomization.formStyle.spacing}px`);
    applySpacingScale(branding.density || defaultCustomization.branding.density);
  };

  const applyBrandingContent = (customization) => {
    const branding = customization.branding;
    document.querySelectorAll('[data-brand-name]').forEach((element) => {
      element.textContent = branding.name || defaultCustomization.branding.name;
    });
    document.querySelectorAll('[data-brand-tagline]').forEach((element) => {
      element.textContent = branding.tagline || defaultCustomization.branding.tagline;
    });
    document.querySelectorAll('[data-brand-logo]').forEach((element) => {
      const logo = branding.logoDataUrl;
      const icon = element.querySelector('[data-brand-logo-icon]');
      if (logo) {
        element.style.background = `url(${logo}) center/cover no-repeat`;
        if (icon) {
          icon.style.display = 'none';
        }
      } else {
        element.style.background = '';
        if (icon) {
          icon.style.display = '';
        }
      }
    });
    if (branding.name && document.title.includes(defaultCustomization.branding.name)) {
      document.title = document.title.replace(defaultCustomization.branding.name, branding.name);
    }
  };

  const applyCustomization = (data) => {
    const merged = mergeCustomization(data);
    applyCustomizationStyles(merged);
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => applyBrandingContent(merged), { once: true });
    } else {
      applyBrandingContent(merged);
    }
  };

  const loadCustomization = () => {
    const saved = localStorage.getItem(customizationKey);
    if (!saved) {
      applyCustomization(defaultCustomization);
      return;
    }
    try {
      applyCustomization(JSON.parse(saved));
    } catch (error) {
      console.warn('Customize settings could not be loaded', error);
      applyCustomization(defaultCustomization);
    }
  };

  window.InventoryTheme = {
    toggle() {
      const next = root.classList.contains('dark') ? 'light' : 'dark';
      setTheme(next);
    },
    set: setTheme,
  };

  window.InventoryCustomization = {
    apply: applyCustomization,
    load: loadCustomization,
  };

  loadCustomization();
  document.addEventListener('DOMContentLoaded', updateButtons);
  window.addEventListener('storage', (event) => {
    if (event.key === customizationKey) {
      loadCustomization();
    }
  });
})();
