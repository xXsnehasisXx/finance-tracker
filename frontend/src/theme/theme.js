import { alpha, createTheme } from '@mui/material/styles'
import { FONT_FAMILY, PALETTES, RADIUS } from './themeConstants.js'

// Accent colour that stays readable as *text/icons* on the current surface.
export const accentColor = (theme) => (theme.palette.mode === 'dark' ? theme.palette.primary.main : theme.palette.primary.dark)

export function createAppTheme(mode) {
  const p = PALETTES[mode]
  const isDark = mode === 'dark'
  const accent = isDark ? p.primary.main : p.primary.dark
  const scrollThumb = isDark ? '#3F3F46' : '#C9C5BB'

  return createTheme({
    palette: { mode, ...p },
    shape: { borderRadius: RADIUS.md },
    spacing: 8,
    typography: {
      fontFamily: FONT_FAMILY,
      h1: { fontSize: '1.75rem', fontWeight: 700, letterSpacing: '-0.02em' },
      h2: { fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.01em' },
      h3: { fontSize: '1.25rem', fontWeight: 650 },
      h4: { fontSize: '1.125rem', fontWeight: 650 },
      h5: { fontSize: '1rem', fontWeight: 650 },
      h6: { fontSize: '0.9375rem', fontWeight: 650 },
      subtitle1: { fontWeight: 600 },
      subtitle2: { fontWeight: 600, fontSize: '0.8125rem' },
      body2: { fontSize: '0.875rem' },
      overline: { fontWeight: 600, letterSpacing: '0.08em', lineHeight: 1.6 },
      button: { textTransform: 'none', fontWeight: 600 },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          html: { colorScheme: mode },
          body: { scrollbarColor: `${scrollThumb} transparent`, transition: 'background-color 200ms ease, color 200ms ease' },
          '*::-webkit-scrollbar': { width: 10, height: 10 },
          '*::-webkit-scrollbar-thumb': { backgroundColor: scrollThumb, borderRadius: 8, border: `2px solid ${p.background.default}` },
          '*::-webkit-scrollbar-track': { backgroundColor: 'transparent' },
          '@media (prefers-reduced-motion: reduce)': {
            '*, *::before, *::after': { animationDuration: '0.01ms !important', transitionDuration: '0.01ms !important', scrollBehavior: 'auto !important' },
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: { borderRadius: RADIUS.sm, minHeight: 40, paddingInline: 18, transition: 'background-color 150ms ease, border-color 150ms ease, color 150ms ease' },
          sizeSmall: { minHeight: 34 },
          sizeLarge: { minHeight: 48 },
        },
        variants: [
          { props: { variant: 'contained', color: 'primary' }, style: { '&:hover': { backgroundColor: p.primary.light } } },
          { props: { variant: 'outlined', color: 'primary' }, style: { color: accent, borderColor: alpha(accent, 0.5) } },
          { props: { variant: 'text', color: 'primary' }, style: { color: accent } },
        ],
      },
      MuiIconButton: { styleOverrides: { root: { borderRadius: RADIUS.sm, transition: 'background-color 150ms ease, color 150ms ease' } } },
      MuiPaper: { defaultProps: { elevation: 0 }, styleOverrides: { root: { backgroundImage: 'none' } } },
      MuiCard: {
        defaultProps: { variant: 'outlined' },
        styleOverrides: {
          root: { borderRadius: RADIUS.lg, borderColor: p.divider, boxShadow: isDark ? 'none' : '0 1px 2px rgba(28, 25, 23, 0.04)' },
        },
      },
      MuiCardContent: { styleOverrides: { root: { padding: 20, '&:last-child': { paddingBottom: 20 } } } },
      MuiDialog: { styleOverrides: { paper: { borderRadius: RADIUS.lg, border: `1px solid ${p.divider}`, backgroundImage: 'none' } } },
      MuiDialogTitle: { styleOverrides: { root: { fontSize: '1.125rem', fontWeight: 700 } } },
      MuiDrawer: { styleOverrides: { paper: { backgroundImage: 'none', borderColor: p.divider } } },
      MuiAppBar: { defaultProps: { elevation: 0, color: 'inherit' }, styleOverrides: { root: { backgroundImage: 'none' } } },
      MuiMenu: { styleOverrides: { paper: { border: `1px solid ${p.divider}`, borderRadius: RADIUS.md, marginTop: 4 } } },
      MuiTooltip: {
        defaultProps: { arrow: true },
        styleOverrides: {
          tooltip: {
            backgroundColor: isDark ? p.background.raised : '#292524',
            color: isDark ? p.text.primary : '#FAFAF9',
            border: isDark ? `1px solid ${p.divider}` : 'none',
            fontSize: '0.75rem',
            fontWeight: 500,
          },
          arrow: { color: isDark ? p.background.raised : '#292524' },
        },
      },
      MuiTextField: { defaultProps: { variant: 'outlined', fullWidth: true } },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            borderRadius: RADIUS.sm,
            backgroundColor: isDark ? alpha('#FFFFFF', 0.03) : p.background.paper,
            '& .MuiOutlinedInput-notchedOutline': { borderColor: isDark ? '#3A3A40' : '#D6D3CB' },
            '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: isDark ? '#52525B' : '#A8A29E' },
          },
        },
      },
      MuiInputLabel: { styleOverrides: { root: { '&.Mui-focused': { color: accent } } } },
      MuiTableCell: {
        styleOverrides: {
          root: { borderBottomColor: p.divider, paddingBlock: 14 },
          head: {
            fontSize: '0.75rem',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            color: p.text.secondary,
            backgroundColor: p.background.paper,
            whiteSpace: 'nowrap',
          },
        },
      },
      MuiTableRow: { styleOverrides: { root: { '&:last-child td': { borderBottom: 0 } } } },
      MuiChip: { styleOverrides: { root: { fontWeight: 600, borderRadius: 8 } } },
      MuiLinearProgress: {
        styleOverrides: {
          root: { height: 10, borderRadius: 999, backgroundColor: isDark ? '#2A2A2E' : '#ECE9E1' },
          bar: { borderRadius: 999 },
        },
      },
      MuiAlert: { styleOverrides: { root: { borderRadius: RADIUS.md, alignItems: 'center' } } },
      MuiDivider: { styleOverrides: { root: { borderColor: p.divider } } },
      MuiAvatar: { styleOverrides: { root: { backgroundColor: alpha(p.primary.main, 0.18), color: accent, fontWeight: 700 } } },
      MuiPagination: { defaultProps: { color: 'primary', shape: 'rounded' } },
      MuiSwitch: { defaultProps: { color: 'primary' } },
      MuiLink: { defaultProps: { underline: 'hover' }, styleOverrides: { root: { color: accent, fontWeight: 600 } } },
    },
  })
}
