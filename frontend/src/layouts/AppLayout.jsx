import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'

const NAV = [
  ['/', 'Dashboard', '📊'],
  ['/accounts', 'Accounts', '🏦'],
  ['/transactions', 'Transactions', '💸'],
  ['/budgets', 'Budgets', '🎯'],
  ['/analytics', 'Analytics', '📈'],
  ['/assistant', 'AI Assistant', '🤖'],
  ['/profile', 'Profile', '👤'],
]

export default function AppLayout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  return (
    <div className="shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="brand">💰 Finance Tracker</div>
        <nav>
          {NAV.map(([to, label, icon]) => (
            <NavLink key={to} to={to} end={to === '/'} onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
              <span aria-hidden="true">{icon}</span> {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="muted small">{user?.email}</div>
          <button className="btn btn-ghost btn-block" onClick={logout}>Log out</button>
        </div>
      </aside>
      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setOpen(true)} aria-label="Open menu">☰</button>
          <span className="greeting">Hello, {user?.name?.split(' ')[0]}</span>
        </header>
        <main className="content"><Outlet /></main>
      </div>
    </div>
  )
}
