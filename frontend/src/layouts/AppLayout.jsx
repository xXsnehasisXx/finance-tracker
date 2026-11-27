import { useCallback, useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { useMediaQuery } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import Box from '@mui/material/Box'
import Drawer from '@mui/material/Drawer'
import AppHeader from '../components/layout/AppHeader.jsx'
import Sidebar from '../components/layout/Sidebar.jsx'
import { SIDEBAR_COLLAPSED_WIDTH, SIDEBAR_STORAGE_KEY, SIDEBAR_WIDTH } from '../theme/themeConstants.js'

const readCollapsed = () => {
  try { return localStorage.getItem(SIDEBAR_STORAGE_KEY) === '1' } catch { return false }
}

export default function AppLayout() {
  const theme = useTheme()
  const isDesktop = useMediaQuery(theme.breakpoints.up('md'))
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => { if (isDesktop) setMobileOpen(false) }, [isDesktop])

  const toggle = useCallback(() => {
    if (!isDesktop) return setMobileOpen((o) => !o)
    setCollapsed((c) => {
      try { localStorage.setItem(SIDEBAR_STORAGE_KEY, c ? '0' : '1') } catch { /* ignore */ }
      return !c
    })
  }, [isDesktop])

  const width = collapsed ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH
  const menuLabel = isDesktop ? (collapsed ? 'Expand sidebar' : 'Collapse sidebar') : 'Open navigation menu'

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      <Box component="aside" sx={{ display: { xs: 'none', md: 'block' }, width, flexShrink: 0, transition: theme.transitions.create('width', { duration: 200 }) }}>
        <Drawer variant="permanent" open sx={{ '& .MuiDrawer-paper': { width, boxSizing: 'border-box', borderRight: 1, borderColor: 'divider', overflowX: 'hidden', transition: theme.transitions.create('width', { duration: 200 }) } }}>
          <Sidebar collapsed={collapsed} />
        </Drawer>
      </Box>
      <Drawer variant="temporary" open={mobileOpen} onClose={() => setMobileOpen(false)} ModalProps={{ keepMounted: true }}
        sx={{ display: { xs: 'block', md: 'none' }, '& .MuiDrawer-paper': { width: SIDEBAR_WIDTH, maxWidth: '85vw', boxSizing: 'border-box' } }}>
        <Sidebar onNavigate={() => setMobileOpen(false)} />
      </Drawer>

      <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <AppHeader onMenuClick={toggle} menuLabel={menuLabel} sidebarOpen={isDesktop ? !collapsed : mobileOpen} />
        <Box component="main" sx={{ flex: 1, width: '100%', maxWidth: 1360, mx: 'auto', p: { xs: 2, sm: 3, lg: 4 }, minWidth: 0 }}>
          <Outlet />
        </Box>
      </Box>
    </Box>
  )
}
