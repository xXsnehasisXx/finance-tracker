import DashboardRounded from '@mui/icons-material/DashboardRounded'
import AccountBalanceWalletRounded from '@mui/icons-material/AccountBalanceWalletRounded'
import ReceiptLongRounded from '@mui/icons-material/ReceiptLongRounded'
import SavingsRounded from '@mui/icons-material/SavingsRounded'
import AnalyticsRounded from '@mui/icons-material/AnalyticsRounded'
import SmartToyRounded from '@mui/icons-material/SmartToyRounded'
import PersonRounded from '@mui/icons-material/PersonRounded'

// Every routed page, grouped for the sidebar. Paths must match the routes in App.jsx.
export const NAV_SECTIONS = [
  { label: 'Overview', items: [{ to: '/', label: 'Dashboard', icon: DashboardRounded }] },
  {
    label: 'Money',
    items: [
      { to: '/accounts', label: 'Accounts', icon: AccountBalanceWalletRounded },
      { to: '/transactions', label: 'Transactions', icon: ReceiptLongRounded },
      { to: '/budgets', label: 'Budgets', icon: SavingsRounded },
    ],
  },
  {
    label: 'Insights',
    items: [
      { to: '/analytics', label: 'Analytics', icon: AnalyticsRounded },
      { to: '/assistant', label: 'AI Assistant', icon: SmartToyRounded },
    ],
  },
  { label: 'Account', items: [{ to: '/profile', label: 'Profile', icon: PersonRounded }] },
]

export const pageTitleFor = (pathname) => {
  const items = NAV_SECTIONS.flatMap((s) => s.items)
  return items.find((i) => (i.to === '/' ? pathname === '/' : pathname.startsWith(i.to)))?.label ?? 'Finance Tracker'
}
