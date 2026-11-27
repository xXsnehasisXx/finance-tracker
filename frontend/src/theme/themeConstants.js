// Single source of truth for design tokens. Change colours, radii and layout sizes here.
export const THEME_STORAGE_KEY = 'finance-tracker:theme-mode'
export const SIDEBAR_STORAGE_KEY = 'finance-tracker:sidebar-collapsed'

export const SIDEBAR_WIDTH = 264
export const SIDEBAR_COLLAPSED_WIDTH = 76
export const HEADER_HEIGHT = 64

export const RADIUS = { sm: 8, md: 12, lg: 16 }

export const FONT_FAMILY = '"Inter", "Roboto", system-ui, -apple-system, "Segoe UI", sans-serif'

// Brand accent: refined amber. `dark` is used for accent text on light surfaces (contrast).
export const BRAND = { main: '#F5B301', light: '#FFD54F', dark: '#9A6B00', contrastText: '#1A1400' }

export const PALETTES = {
  dark: {
    background: { default: '#0B0B0C', paper: '#151517', raised: '#1C1C1F' },
    divider: '#2A2A2E',
    text: { primary: '#F4F4F5', secondary: '#A1A1AA' },
    primary: { main: BRAND.main, light: BRAND.light, dark: BRAND.dark, contrastText: BRAND.contrastText },
    success: { main: '#4ADE80', contrastText: '#052E16' },
    warning: { main: '#FB923C', contrastText: '#2A1000' },
    error: { main: '#F87171', contrastText: '#2A0505' },
    info: { main: '#60A5FA', contrastText: '#06203F' },
  },
  light: {
    background: { default: '#F6F5F1', paper: '#FFFFFF', raised: '#FAF9F6' },
    divider: '#E7E5DF',
    text: { primary: '#1C1917', secondary: '#57534E' },
    primary: { main: BRAND.main, light: BRAND.light, dark: BRAND.dark, contrastText: BRAND.contrastText },
    success: { main: '#15803D', contrastText: '#FFFFFF' },
    warning: { main: '#C2410C', contrastText: '#FFFFFF' },
    error: { main: '#DC2626', contrastText: '#FFFFFF' },
    info: { main: '#2563EB', contrastText: '#FFFFFF' },
  },
}

// Category colours used by charts and category dots; readable on both dark and light surfaces.
export const CATEGORY_COLORS = {
  food: '#F97316',
  transport: '#3B82F6',
  utilities: '#8B5CF6',
  entertainment: '#EC4899',
  health: '#10B981',
  salary: '#14B8A6',
  other: '#94A3B8',
}
