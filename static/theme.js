(() => {
  const root = document.documentElement;
  const storage = {
    getItem(key) { try { return localStorage.getItem(key); } catch (_) { return null; } },
    setItem(key, value) { try { localStorage.setItem(key, value); } catch (_) {} },
    removeItem(key) { try { localStorage.removeItem(key); } catch (_) {} },
  };
  const stored = storage.getItem('theme');
  const initial = stored || 'light';
  const customizationCacheKey = 'inventorypro.customization.cache';
  const customizationLocalKey = 'inventorypro.customization.local';
  const legacyCustomizationKey = 'inventorypro.customization';
  let activeCustomization = null;

  const defaultCustomization = window.inventoryDesignDefaults;

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

  const applyModeTokens = (customization) => {
    if (!customization) return;
    if (!root.classList.contains('dark')) {
      return;
    }

    root.style.setProperty('--color-bg', '#0b0f14');
    root.style.setProperty('--color-surface', '#111820');
    root.style.setProperty('--color-surface-muted', '#16202a');
    root.style.setProperty('--color-surface-elevated', '#111820');
    root.style.setProperty('--color-text', '#e6edf3');
    root.style.setProperty('--color-text-muted', '#93a4b5');
    root.style.setProperty('--color-border', '#263442');
    root.style.setProperty('--color-border-strong', '#344454');
    root.style.setProperty('--color-accent', '#7aa2f7');
    root.style.setProperty('--color-accent-strong', '#9ab7ff');
    root.style.setProperty('--color-accent-soft', 'rgba(122, 162, 247, 0.16)');
    root.style.setProperty('--focus-ring', 'rgba(122, 162, 247, 0.34)');
    root.style.setProperty('--color-success', '#4ade80');
    root.style.setProperty('--color-warning', '#fbbf24');
    root.style.setProperty('--color-danger', '#f87171');
    root.style.setProperty('--color-info', '#38bdf8');
    root.style.setProperty('--input-bg', '#0f151d');
    root.style.setProperty('--input-text', '#e6edf3');
    root.style.setProperty('--input-border', '#263442');
    root.style.setProperty('--input-placeholder', '#718196');
    root.style.setProperty('--button-bg', '#e6edf3');
    root.style.setProperty('--button-bg-hover', '#f4f7fb');
    root.style.setProperty('--button-bg-active', '#cbd5e1');
    root.style.setProperty('--button-text', '#0b0f14');
    root.style.setProperty('--button-secondary-bg', '#111820');
    root.style.setProperty('--button-secondary-bg-hover', '#16202a');
    root.style.setProperty('--button-secondary-bg-active', '#1c2936');
    root.style.setProperty('--button-secondary-text', '#e6edf3');
    root.style.setProperty('--button-secondary-border', '#263442');
    root.style.setProperty('--card-bg', '#111820');
    root.style.setProperty('--card-border', '#263442');
    root.style.setProperty('--table-header-bg', '#16202a');
    root.style.setProperty('--table-row-bg', '#111820');
    root.style.setProperty('--table-zebra-bg', '#131c25');
    root.style.setProperty('--table-border', '#263442');
    root.style.setProperty('--modal-bg', '#111820');
    root.style.setProperty('--navbar-bg', '#111820');
    root.style.setProperty('--navbar-border', '#263442');
    root.style.setProperty('--navbar-text', '#e6edf3');
    root.style.setProperty('--sidebar-bg', '#101720');
    root.style.setProperty('--sidebar-border', '#263442');
    root.style.setProperty('--sidebar-text', '#e6edf3');
  };

  const refreshModeAwareTheme = () => {
    if (!activeCustomization) return;
    applyThemeToCSSVars(activeCustomization);
    applyModeTokens(activeCustomization);
  };

  const setTheme = (mode) => {
    if (mode === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    storage.setItem('theme', mode);
    refreshModeAwareTheme();
    updateButtons();
  };

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

  const hexToRgb = (hex) => {
    if (!hex) return [79, 70, 229];
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

  const deepMerge = (base, override) => {
    if (typeof base !== 'object' || base === null) return override;
    if (typeof override !== 'object' || override === null) return base;
    const output = Array.isArray(base) ? [...base] : { ...base };
    Object.keys(override).forEach((key) => {
      if (Array.isArray(override[key])) {
        output[key] = [...override[key]];
      } else if (typeof override[key] === 'object' && override[key] !== null) {
        output[key] = deepMerge(base[key] || {}, override[key]);
      } else {
        output[key] = override[key];
      }
    });
    return output;
  };

  const migrateCustomization = (data) => {
    if (!data || typeof data !== 'object') {
      return deepMerge({}, defaultCustomization);
    }

    const hasLegacy = data.branding || data.formStyle || data.layout;
    if (hasLegacy && !data.baseTokens) {
      const migrated = deepMerge({}, defaultCustomization);
      const branding = data.branding || {};
      const formStyle = data.formStyle || {};
      migrated.branding.name = branding.name || migrated.branding.name;
      migrated.branding.tagline = branding.tagline || migrated.branding.tagline;
      migrated.branding.logoDataUrl = branding.logoDataUrl || migrated.branding.logoDataUrl;
      migrated.baseTokens.colors.primary = branding.primary || migrated.baseTokens.colors.primary;
      migrated.baseTokens.colors.accent = branding.accent || migrated.baseTokens.colors.accent;
      migrated.baseTokens.colors.background = branding.background || migrated.baseTokens.colors.background;
      migrated.baseTokens.spacing.radius.md = branding.radius || migrated.baseTokens.spacing.radius.md;
      migrated.layoutPrefs.density = branding.density || migrated.layoutPrefs.density;
      migrated.componentOverrides.button.primary.background = formStyle.buttonColor || migrated.componentOverrides.button.primary.background;
      migrated.componentOverrides.button.primary.text = formStyle.buttonText || migrated.componentOverrides.button.primary.text;
      migrated.componentOverrides.input.background = formStyle.inputBackground || migrated.componentOverrides.input.background;
      migrated.componentOverrides.input.border = formStyle.inputBorder || migrated.componentOverrides.input.border;
      migrated.layoutPrefs.formSpacing = formStyle.spacing || migrated.layoutPrefs.formSpacing;
      return migrated;
    }

    const merged = deepMerge(defaultCustomization, data);
    merged.schemaVersion = 1;
    return merged;
  };

  const validateCustomization = (data) => {
    const errors = [];
    if (!data || typeof data !== 'object') {
      errors.push('Customization muss ein Objekt sein.');
      return { valid: false, errors };
    }
    if (typeof data.schemaVersion !== 'number') {
      errors.push('schemaVersion fehlt oder ist ungültig.');
    }
    if (!data.baseTokens || !data.componentOverrides || !data.layoutPrefs) {
      errors.push('Basisbereiche fehlen.');
    }
    return { valid: errors.length === 0, errors };
  };

  const applySpacingScale = (values = [], density = 1) => {
    const base = values.length ? values : defaultCustomization.baseTokens.spacing.paddingScale;
    base.forEach((value, index) => {
      const scaled = Math.round(value * density);
      root.style.setProperty(`--space-${index + 1}`, `${scaled}px`);
    });
  };

  const applyThemeToCSSVars = (customization) => {
    const base = customization.baseTokens;
    const colors = base.colors;
    const typography = base.typography;
    const spacing = base.spacing;
    const layout = base.layout;
    const states = base.states;

    root.style.setProperty('--font-sans', typography.fontFamily);
    root.style.setProperty('--font-size-xs', typography.fontSizes.xs);
    root.style.setProperty('--font-size-sm', typography.fontSizes.sm);
    root.style.setProperty('--font-size-base', typography.fontSizes.base);
    root.style.setProperty('--font-size-lg', typography.fontSizes.lg);
    root.style.setProperty('--font-size-xl', typography.fontSizes.xl);
    root.style.setProperty('--font-weight-normal', typography.fontWeights.normal);
    root.style.setProperty('--font-weight-medium', typography.fontWeights.medium);
    root.style.setProperty('--font-weight-semibold', typography.fontWeights.semibold);
    root.style.setProperty('--font-weight-bold', typography.fontWeights.bold);
    root.style.setProperty('--line-height-tight', typography.lineHeights.tight);
    root.style.setProperty('--line-height-normal', typography.lineHeights.normal);
    root.style.setProperty('--line-height-relaxed', typography.lineHeights.relaxed);
    root.style.setProperty('--letter-spacing-tight', typography.letterSpacing.tight);
    root.style.setProperty('--letter-spacing-normal', typography.letterSpacing.normal);
    root.style.setProperty('--letter-spacing-wide', typography.letterSpacing.wide);

    root.style.setProperty('--color-bg', colors.background);
    root.style.setProperty('--color-surface', colors.surface);
    root.style.setProperty('--color-surface-muted', adjustHex(colors.surface, -0.04));
    root.style.setProperty('--color-surface-elevated', colors.surface);
    root.style.setProperty('--color-text', colors.text);
    root.style.setProperty('--color-text-muted', colors.textMuted);
    root.style.setProperty('--color-border', colors.border);
    root.style.setProperty('--color-accent', colors.primary);
    root.style.setProperty('--color-accent-strong', adjustHex(colors.primary, -0.18));
    root.style.setProperty('--color-accent-soft', `rgba(${hexToRgb(colors.primary).join(', ')}, 0.12)`);
    root.style.setProperty('--color-success', colors.success);
    root.style.setProperty('--color-warning', colors.warning);
    root.style.setProperty('--color-danger', colors.danger);
    root.style.setProperty('--color-info', colors.info);
    root.style.setProperty('--brand-accent', colors.accent);
    root.style.setProperty('--focus-ring', colors.focus);

    root.style.setProperty('--radius-sm', `${spacing.radius.sm}px`);
    root.style.setProperty('--radius-md', `${spacing.radius.md}px`);
    root.style.setProperty('--radius-lg', `${spacing.radius.lg}px`);
    root.style.setProperty('--radius-pill', `${spacing.radius.pill}px`);

    root.style.setProperty('--max-content', `${customization.layoutPrefs.containerWidth || layout.containerWidth}px`);
    root.style.setProperty('--sidebar-width', `${customization.layoutPrefs.sidebarWidth || layout.sidebarWidth}px`);

    applySpacingScale(spacing.paddingScale, customization.layoutPrefs.density || 1);

    const density = customization.layoutPrefs.density || 1;
    const formSpacing = customization.layoutPrefs.formSpacing || 16;
    root.style.setProperty('--density-scale', density);
    root.style.setProperty('--form-gap', `${formSpacing}px`);

    const button = customization.componentOverrides.button;
    root.style.setProperty('--button-radius', `${button.primary.radius}px`);
    root.style.setProperty('--button-bg', button.primary.background);
    root.style.setProperty('--button-text', button.primary.text);
    root.style.setProperty('--button-border', button.primary.border);
    root.style.setProperty('--button-shadow', button.primary.shadow);
    root.style.setProperty('--button-bg-hover', button.primary.hoverBg);
    root.style.setProperty('--button-bg-active', button.primary.activeBg);
    root.style.setProperty('--button-bg-disabled', button.primary.disabledBg);
    root.style.setProperty('--button-text-disabled', button.primary.disabledText);

    root.style.setProperty('--button-secondary-radius', `${button.secondary.radius}px`);
    root.style.setProperty('--button-secondary-bg', button.secondary.background);
    root.style.setProperty('--button-secondary-text', button.secondary.text);
    root.style.setProperty('--button-secondary-border', button.secondary.border);
    root.style.setProperty('--button-secondary-shadow', button.secondary.shadow);
    root.style.setProperty('--button-secondary-bg-hover', button.secondary.hoverBg);
    root.style.setProperty('--button-secondary-bg-active', button.secondary.activeBg);
    root.style.setProperty('--button-secondary-bg-disabled', button.secondary.disabledBg);
    root.style.setProperty('--button-secondary-text-disabled', button.secondary.disabledText);

    const input = customization.componentOverrides.input;
    root.style.setProperty('--input-radius', `${input.radius}px`);
    root.style.setProperty('--input-bg', input.background);
    root.style.setProperty('--input-text', input.text);
    root.style.setProperty('--input-border', input.border);
    root.style.setProperty('--input-focus', input.focusRing);
    root.style.setProperty('--input-shadow', input.shadow);
    root.style.setProperty('--input-placeholder', input.placeholder);

    const card = customization.componentOverrides.card;
    root.style.setProperty('--card-radius', `${card.radius}px`);
    root.style.setProperty('--card-bg', card.background);
    root.style.setProperty('--card-border', card.border);
    root.style.setProperty('--card-shadow', card.shadow);

    const table = customization.componentOverrides.table;
    root.style.setProperty('--table-radius', `${table.radius}px`);
    root.style.setProperty('--table-header-bg', table.headerBg);
    root.style.setProperty('--table-row-bg', table.rowBg);
    const zebra = customization.layoutPrefs.zebraStriping;
    root.style.setProperty('--table-zebra-bg', zebra ? table.zebraBg : table.rowBg);
    root.style.setProperty('--table-border', table.border);

    const modal = customization.componentOverrides.modal;
    root.style.setProperty('--modal-radius', `${modal.radius}px`);
    root.style.setProperty('--modal-bg', modal.background);
    root.style.setProperty('--modal-shadow', modal.shadow);

    const toast = customization.componentOverrides.toast;
    root.style.setProperty('--toast-radius', `${toast.radius}px`);
    root.style.setProperty('--toast-bg', toast.background);
    root.style.setProperty('--toast-text', toast.text);
    root.style.setProperty('--toast-shadow', toast.shadow);

    const badge = customization.componentOverrides.badge;
    root.style.setProperty('--badge-radius', `${badge.radius}px`);
    root.style.setProperty('--badge-bg', badge.background);
    root.style.setProperty('--badge-text', badge.text);

    const navbar = customization.componentOverrides.navbar;
    root.style.setProperty('--navbar-bg', navbar.background);
    root.style.setProperty('--navbar-border', navbar.border);
    root.style.setProperty('--navbar-text', navbar.text);

    const sidebar = customization.componentOverrides.sidebar;
    root.style.setProperty('--sidebar-bg', sidebar.background);
    root.style.setProperty('--sidebar-border', sidebar.border);
    root.style.setProperty('--sidebar-text', sidebar.text);

    root.style.setProperty('--state-hover', states.hover);
    root.style.setProperty('--state-active', states.active);
    root.style.setProperty('--state-disabled', states.disabled);

    const tableDensity = customization.layoutPrefs.tableDensity;
    const rowHeight = customization.layoutPrefs.rowHeight;
    const densityMap = {
      compact: 6,
      normal: 8,
      comfortable: 12,
    };
    const rowPadding = densityMap[tableDensity] || densityMap.normal;
    root.style.setProperty('--table-row-padding', `${rowPadding}px`);
    root.style.setProperty('--table-row-height', `${rowHeight}px`);
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
    const merged = migrateCustomization(data);
    activeCustomization = merged;
    applyThemeToCSSVars(merged);
    applyModeTokens(merged);
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => applyBrandingContent(merged), { once: true });
    } else {
      applyBrandingContent(merged);
    }
    return merged;
  };

  const getCachedCustomization = () => {
    const cached = storage.getItem(customizationCacheKey);
    if (!cached) return null;
    try {
      return JSON.parse(cached);
    } catch (error) {
      console.warn('Customize cache could not be loaded', error);
      return null;
    }
  };

  const migrateLegacyCustomization = () => {
    const legacy = storage.getItem(legacyCustomizationKey);
    if (!legacy) return null;
    try {
      const parsed = JSON.parse(legacy);
      const migrated = migrateCustomization(parsed);
      storage.removeItem(legacyCustomizationKey);
      setCachedCustomization({ customization: migrated, cachedAt: new Date().toISOString() });
      return migrated;
    } catch (error) {
      console.warn('Legacy customization could not be migrated', error);
      return null;
    }
  };

  const setCachedCustomization = (payload) => {
    storage.setItem(customizationCacheKey, JSON.stringify(payload));
  };

  const getLocalOverride = () => {
    const storedOverride = storage.getItem(customizationLocalKey);
    if (!storedOverride) return null;
    try {
      return JSON.parse(storedOverride);
    } catch (error) {
      console.warn('Customize override could not be loaded', error);
      return null;
    }
  };

  const setLocalOverride = (override) => {
    if (!override) {
      storage.removeItem(customizationLocalKey);
      return;
    }
    storage.setItem(customizationLocalKey, JSON.stringify(override));
  };

  const loadCustomization = async () => {
    let applied = applyCustomization(defaultCustomization);
    const legacy = migrateLegacyCustomization();
    if (legacy) {
      applied = applyCustomization(legacy);
    }
    const cached = getCachedCustomization();
    if (cached && cached.customization) {
      applied = applyCustomization(cached.customization);
    }

    try {
      const response = await fetch('/api/customize', { credentials: 'same-origin' });
      const contentType = response.headers.get('content-type') || '';
      if (response.ok && contentType.includes('application/json')) {
        const serverData = await response.json();
        if (serverData.customization) {
          applied = applyCustomization(serverData.customization);
          setCachedCustomization({
            customization: applied,
            updatedAt: serverData.updated_at,
            revisionId: serverData.revision_id,
            cachedAt: new Date().toISOString(),
          });
        }
      }
    } catch (error) {
      console.warn('Customize settings could not be loaded', error);
    }

    const localOverride = getLocalOverride();
    if (localOverride) {
      applied = applyCustomization(deepMerge(applied, localOverride));
    }

    return applied;
  };

  window.InventoryTheme = {
    toggle() {
      const next = root.classList.contains('dark') ? 'light' : 'dark';
      setTheme(next);
    },
    set: setTheme,
  };

  window.InventoryCustomization = {
    defaults: () => deepMerge({}, defaultCustomization),
    merge: deepMerge,
    migrate: migrateCustomization,
    validate: validateCustomization,
    apply: applyCustomization,
    applyThemeToCSSVars,
    load: loadCustomization,
    getCached: getCachedCustomization,
    setCached: setCachedCustomization,
    getLocalOverride,
    setLocalOverride,
  };

  loadCustomization();
  document.addEventListener('DOMContentLoaded', updateButtons);
  window.addEventListener('storage', (event) => {
    if (event.key === customizationCacheKey || event.key === customizationLocalKey) {
      loadCustomization();
    }
  });
})();
