import { NavLink, useLocation } from 'react-router-dom'
import { alpha } from '@mui/material/styles'
import Avatar from '@mui/material/Avatar'
import Box from '@mui/material/Box'
import Divider from '@mui/material/Divider'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import Stack from '@mui/material/Stack'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import AccountBalanceRounded from '@mui/icons-material/AccountBalanceRounded'
import LogoutRounded from '@mui/icons-material/LogoutRounded'
import { useAuth } from '../../contexts/AuthContext.jsx'
import { NAV_SECTIONS } from './navConfig.js'

// One interactive navigation tile. Active state comes from the router, so it persists when the pointer leaves.
const tileSx = (collapsed) => (theme) => {
  const accent = theme.palette.mode === 'dark' ? theme.palette.primary.main : theme.palette.primary.dark
  return {
    position: 'relative',
    height: 44,
    minHeight: 44,
    borderRadius: 2.5,
    px: collapsed ? 0 : 1.5,
    justifyContent: collapsed ? 'center' : 'flex-start',
    color: theme.palette.text.secondary,
    transition: theme.transitions.create(['background-color', 'color'], { duration: 150 }),
    '& .MuiListItemIcon-root': { minWidth: collapsed ? 0 : 40, justifyContent: 'center', color: 'inherit', transition: theme.transitions.create('color', { duration: 150 }) },
    '&:hover': { backgroundColor: alpha(theme.palette.text.primary, 0.07), color: theme.palette.text.primary },
    '&.Mui-selected': {
      backgroundColor: alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.16 : 0.22),
      color: accent,
      '&:hover': { backgroundColor: alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.22 : 0.3) },
      '&::before': { content: '""', position: 'absolute', left: 0, top: 10, bottom: 10, width: 3, borderRadius: 3, backgroundColor: theme.palette.primary.main },
    },
    '&.Mui-focusVisible': { outline: `2px solid ${accent}`, outlineOffset: -2, backgroundColor: alpha(theme.palette.text.primary, 0.07) },
    '& .MuiListItemText-primary': { fontWeight: 600, fontSize: '0.9375rem', whiteSpace: 'nowrap' },
  }
}

function NavTile({ item, collapsed, onNavigate }) {
  const { pathname } = useLocation()
  const active = item.to === '/' ? pathname === '/' : pathname === item.to || pathname.startsWith(`${item.to}/`)
  const Icon = item.icon
  return (
    <Tooltip title={collapsed ? item.label : ''} placement="right">
      <ListItemButton component={NavLink} to={item.to} end={item.to === '/'} selected={active} onClick={onNavigate}
        aria-label={collapsed ? item.label : undefined} aria-current={active ? 'page' : undefined} sx={tileSx(collapsed)}>
        <ListItemIcon><Icon /></ListItemIcon>
        {!collapsed && <ListItemText primary={item.label} />}
      </ListItemButton>
    </Tooltip>
  )
}

export default function Sidebar({ collapsed = false, onNavigate }) {
  const { user, logout } = useAuth()
  const initial = (user?.name || user?.email || '?').charAt(0).toUpperCase()

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', bgcolor: 'background.paper' }}>
      <Stack direction="row" spacing={1.5} sx={{ height: 64, px: collapsed ? 0 : 2.5, alignItems: 'center', justifyContent: collapsed ? 'center' : 'flex-start', flexShrink: 0 }}>
        <Box aria-hidden="true" sx={{ width: 36, height: 36, borderRadius: 2.5, display: 'grid', placeItems: 'center', flexShrink: 0, bgcolor: 'primary.main', color: 'primary.contrastText' }}>
          <AccountBalanceRounded fontSize="small" />
        </Box>
        {!collapsed && <Typography variant="h5" component="span" noWrap>Finance Tracker</Typography>}
      </Stack>
      <Divider />

      <Box component="nav" aria-label="Main navigation" sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', px: 1.5, py: 2 }}>
        {NAV_SECTIONS.map((section, i) => (
          <Box key={section.label} sx={{ mb: 2 }}>
            {collapsed
              ? i > 0 && <Divider sx={{ mb: 1.5 }} />
              : <Typography variant="overline" color="text.secondary" sx={{ px: 1.5, display: 'block', mb: 0.5 }}>{section.label}</Typography>}
            <List disablePadding sx={{ display: 'grid', gap: 0.5 }}>
              {section.items.map((item) => <NavTile key={item.to} item={item} collapsed={collapsed} onNavigate={onNavigate} />)}
            </List>
          </Box>
        ))}
      </Box>

      <Divider />
      <Box sx={{ p: 1.5, display: 'grid', gap: 1, flexShrink: 0 }}>
        {!collapsed && (
          <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', px: 0.5, minWidth: 0 }}>
            <Avatar sx={{ width: 34, height: 34, fontSize: '0.9rem' }}>{initial}</Avatar>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="subtitle2" noWrap>{user?.name}</Typography>
              <Typography variant="caption" color="text.secondary" noWrap component="div">{user?.email}</Typography>
            </Box>
          </Stack>
        )}
        <Tooltip title={collapsed ? 'Log out' : ''} placement="right">
          <ListItemButton onClick={logout} aria-label="Log out" sx={tileSx(collapsed)}>
            <ListItemIcon><LogoutRounded /></ListItemIcon>
            {!collapsed && <ListItemText primary="Log out" />}
          </ListItemButton>
        </Tooltip>
      </Box>
    </Box>
  )
}
