import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import { createAppTheme } from './theme.js'
import { PALETTES, THEME_STORAGE_KEY } from './themeConstants.js'

const ColorModeContext = createContext({ mode: 'dark', toggleMode: () => {}, setMode: () => {} })

// Mirrors the inline script in index.html so first paint and React agree.
function readStoredMode() {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch { /* storage unavailable (private mode) */ }
  return 'dark'
}

export function ColorModeProvider({ children }) {
  const [mode, setModeState] = useState(readStoredMode)
  const theme = useMemo(() => createAppTheme(mode), [mode])

  const setMode = useCallback((next) => {
    setModeState(next)
    try { localStorage.setItem(THEME_STORAGE_KEY, next) } catch { /* ignore */ }
  }, [])
  const toggleMode = useCallback(() => setMode(mode === 'dark' ? 'light' : 'dark'), [mode, setMode])

  useEffect(() => {
    document.documentElement.style.colorScheme = mode
    document.documentElement.style.backgroundColor = PALETTES[mode].background.default
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', PALETTES[mode].background.default)
  }, [mode])

  // Keep multiple tabs in sync.
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === THEME_STORAGE_KEY && (e.newValue === 'light' || e.newValue === 'dark')) setModeState(e.newValue)
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  const value = useMemo(() => ({ mode, toggleMode, setMode }), [mode, toggleMode, setMode])
  return (
    <ColorModeContext.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ColorModeContext.Provider>
  )
}

export const useColorMode = () => useContext(ColorModeContext)
