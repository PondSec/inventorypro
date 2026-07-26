export interface BrandingConfig {
  name: string;
  tagline: string;
  logoDataUrl: string;
  logoLightDataUrl: string;
  logoDarkDataUrl: string;
  faviconDataUrl: string;
}

export interface ColorTokens {
  primary: string;
  secondary: string;
  accent: string;
  neutral: string;
  background: string;
  surface: string;
  text: string;
  textMuted: string;
  border: string;
  shadow: string;
  focus: string;
  success: string;
  warning: string;
  danger: string;
  info: string;
}

export interface TypographyTokens {
  fontFamily: string;
  fontSizes: Record<'xs' | 'sm' | 'base' | 'lg' | 'xl', string>;
  fontWeights: Record<'normal' | 'medium' | 'semibold' | 'bold', number>;
  lineHeights: Record<'tight' | 'normal' | 'relaxed', number>;
  letterSpacing: Record<'tight' | 'normal' | 'wide', string>;
}

export interface SpacingTokens {
  radius: {
    sm: number;
    md: number;
    lg: number;
    pill: number;
  };
  paddingScale: number[];
  gapScale: number[];
}

export interface LayoutTokens {
  containerWidth: number;
  sidebarWidth: number;
  tableDensity: 'compact' | 'normal' | 'comfortable';
}

export interface StateTokens {
  hover: number;
  active: number;
  disabled: number;
}

export interface BaseTokens {
  colors: ColorTokens;
  typography: TypographyTokens;
  spacing: SpacingTokens;
  layout: LayoutTokens;
  states: StateTokens;
}

export interface ButtonOverride {
  radius: number;
  background: string;
  text: string;
  border: string;
  shadow: string;
  hoverBg: string;
  activeBg: string;
  disabledBg: string;
  disabledText: string;
}

export interface ComponentOverrides {
  button: {
    primary: ButtonOverride;
    secondary: ButtonOverride;
  };
  input: {
    radius: number;
    background: string;
    text: string;
    border: string;
    focusRing: string;
    shadow: string;
    placeholder: string;
  };
  card: {
    radius: number;
    background: string;
    border: string;
    shadow: string;
  };
  table: {
    radius: number;
    headerBg: string;
    rowBg: string;
    zebraBg: string;
    border: string;
  };
  modal: {
    radius: number;
    background: string;
    shadow: string;
  };
  toast: {
    radius: number;
    background: string;
    text: string;
    shadow: string;
  };
  badge: {
    radius: number;
    background: string;
    text: string;
  };
  navbar: {
    background: string;
    border: string;
    text: string;
  };
  sidebar: {
    background: string;
    border: string;
    text: string;
  };
}

export interface LayoutPrefs {
  density: number;
  containerWidth: number;
  sidebarWidth: number;
  tableDensity: 'compact' | 'normal' | 'comfortable';
  rowHeight: number;
  zebraStriping: boolean;
  formSpacing: number;
}

export interface FeaturePrefs {
  iconSet: string;
  tableDefaults: {
    defaultSort: string;
    defaultColumns: string[];
  };
  compactSidebar: boolean;
}

export interface NavigationItem {
  label: string;
  visible: boolean;
  order: number;
}

export interface NavigationConfig {
  groups: Record<string, string>;
  items: Record<string, NavigationItem>;
}

export interface UiCustomization {
  schemaVersion: 1;
  branding: BrandingConfig;
  baseTokens: BaseTokens;
  componentOverrides: ComponentOverrides;
  layoutPrefs: LayoutPrefs;
  featurePrefs: FeaturePrefs;
  navigation: NavigationConfig;
}
