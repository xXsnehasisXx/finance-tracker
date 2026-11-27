import { useState } from 'react'
import { Link as RouterLink, useLocation } from 'react-router-dom'
import AppBar from '@mui/material/AppBar'
import Avatar from '@mui/material/Avatar'
import Box from '@mui/material/Box'
import IconButton from '@mui/material/IconButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import Menu from '@mui/material/Menu'
import MenuItem from '@mui/material/MenuItem'
import Toolbar from '@mui/material/Toolbar'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import LogoutRounded from '@mui/icons-material/LogoutRounded'
import MenuOpenRounded from '@mui/icons-material/MenuOpenRounded'
import MenuRounded from '@mui/icons-material/MenuRounded'
import PersonRounded from '@mui/icons-material/PersonRounded'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { HEADER_HEIGHT } from '../../theme/themeConstants.js'
import { pageTitleFor } from './navConfig.js'
import ThemeToggle from './ThemeToggle.jsx'

export default function AppHeader({ onMenuClick, menuLabel, sidebarOpen }) {
  const { user, logout } = useAuth()
  const { pathname } = useLocation()
  const [anchor, setAnchor] = useState(null)
  const initial = (user?.name || user?.email || '?').charAt(0).toUpperCase()
  const firstName = user?.name?.split(' ')[0]

  return (
    <AppBar position="sticky" sx={{ bgcolor: 'background.paper', color: 'text.primary', borderBottom: 1, borderColor: 'divider', height: HEADER_HEIGHT, justifyContent: 'center' }}>
      <Toolbar sx={{ gap: 1, minHeight: `${HEADER_HEIGHT}px !important`, px: { xs: 1.5, sm: 3 } }}>
        <Tooltip title={menuLabel}>
          <IconButton edge="start" color="inherit" onClick={onMenuClick} aria-label={menuLabel}>
            {sidebarOpen ? <MenuOpenRounded /> : <MenuRounded />}
          </IconButton>
        </Tooltip>
        <Typography variant="h5" component="p" noWrap sx={{ flexGrow: 1 }}>{pageTitleFor(pathname)}</Typography>
        <Typography variant="body2" color="text.secondary" noWrap sx={{ display: { xs: 'none', sm: 'block' }, mr: 1 }}>Hello, {firstName}</Typography>
        <ThemeToggle />
        <Tooltip title="Account">
          <IconButton onClick={(e) => setAnchor(e.currentTarget)} aria-label="Open account menu" aria-haspopup="menu" aria-expanded={Boolean(anchor)} sx={{ p: 0.5 }}>
            <Avatar sx={{ width: 34, height: 34, fontSize: '0.9rem' }}>{initial}</Avatar>
          </IconButton>
        </Tooltip>
        <Menu anchorEl={anchor} open={Boolean(anchor)} onClose={() => setAnchor(null)} anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }} transformOrigin={{ vertical: 'top', horizontal: 'right' }}>
          <Box sx={{ px: 2, py: 1, maxWidth: 240 }}>
            <Typography variant="subtitle2" noWrap>{user?.name}</Typography>
            <Typography variant="caption" color="text.secondary" noWrap component="div">{user?.email}</Typography>
          </Box>
          <MenuItem component={RouterLink} to="/profile" onClick={() => setAnchor(null)}>
            <ListItemIcon><PersonRounded fontSize="small" /></ListItemIcon>Profile
          </MenuItem>
          <MenuItem onClick={() => { setAnchor(null); logout() }}>
            <ListItemIcon><LogoutRounded fontSize="small" /></ListItemIcon>Log out
          </MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  )
}
