import { useColorMode } from '../../theme/ThemeContext.jsx'
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import DarkMode from '@mui/icons-material/DarkMode'
import LightMode from '@mui/icons-material/LightMode'

export default function ThemeToggle({ sx }) {
  const { mode, toggleMode } = useColorMode()
  const label = mode === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'
  return (
    <Tooltip title={label}>
      <IconButton onClick={toggleMode} aria-label={label} color="inherit" sx={sx}>
        {mode === 'dark' ? <LightMode /> : <DarkMode />}
      </IconButton>
    </Tooltip>
  )
}
