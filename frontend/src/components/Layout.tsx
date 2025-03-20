import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useTheme } from '../theme/ThemeProvider'
import { api } from '../api'
import { useAsync } from '../lib/hooks'

interface NavItem {
  to: string
  label: string
  icon: string
  group: string
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Overview', icon: '◧', group: 'Monitor' },
  { to: '/runs', label: 'Runs', icon: '▶', group: 'Monitor' },
  { to: '/runs/new', label: 'New evaluation', icon: '＋', group: 'Monitor' },
  { to: '/evidence', label: 'Evidence', icon: '❑', group: 'Monitor' },
  { to: '/compare', label: 'Compare', icon: '⇄', group: 'Analyse' },
  { to: '/drift', label: 'Drift', icon: '◈', group: 'Analyse' },
  { to: '/regressions', label: 'Regressions', icon: '⚠', group: 'Analyse' },
  { to: '/metrics', label: 'Metrics', icon: '∑', group: 'Analyse' },
  { to: '/gates', label: 'Gate policies', icon: '⛨', group: 'Configure' },
  { to: '/datasets', label: 'Datasets', icon: '☰', group: 'Configure' },
  { to: '/applications', label: 'Applications', icon: '⬡', group: 'Configure' },
  { to: '/providers', label: 'Providers', icon: '⚙', group: 'Configure' },
  { to: '/reports', label: 'Reports', icon: '⎙', group: 'Configure' },
  { to: '/system', label: 'System', icon: '⛭', group: 'Configure' },
]

const GROUP_ORDER = ['Monitor', 'Analyse', 'Configure']

function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()
  return (
    <button
      type="button"
      className="btn btn-icon theme-toggle"
      onClick={toggleTheme}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
    >
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}

export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const { theme } = useTheme()
  const health = useAsync(() => api.health(), [])

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>

      <header className="topbar">
        <div className="topbar-left">
          <button
            type="button"
            className="btn btn-icon menu-toggle"
            onClick={() => setMenuOpen((open) => !open)}
            aria-expanded={menuOpen}
            aria-controls="primary-navigation"
            aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          >
            ☰
          </button>
          <div className="brand">
            <span className="brand-mark" aria-hidden="true">
              RQ
            </span>
            <span className="brand-text">
              <strong>RAG Quality Monitor</strong>
              <small>evaluation &amp; drift control</small>
            </span>
          </div>
        </div>
        <div className="topbar-right">
          <span className={`api-status api-status-${health.error ? 'offline' : 'online'}`}>
            <span className="dot" aria-hidden="true" />
            {health.error ? 'API offline' : `API ${health.data?.version ?? '…'}`}
          </span>
          <ThemeToggle />
        </div>
      </header>

      <div className="app-body">
        {menuOpen && (
          <div className="nav-scrim" onClick={() => setMenuOpen(false)} role="presentation" aria-hidden="true" />
        )}
        <nav
          id="primary-navigation"
          className={`sidebar${menuOpen ? ' sidebar-open' : ''}`}
          aria-label="Primary navigation"
        >
          {GROUP_ORDER.map((group) => (
            <div className="nav-group" key={group}>
              <span className="nav-group-title">{group}</span>
              <ul>
                {NAV_ITEMS.filter((item) => item.group === group).map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.to === '/' || item.to === '/runs'}
                      className={({ isActive }) => `nav-link${isActive ? ' nav-link-active' : ''}`}
                    >
                      <span className="nav-icon" aria-hidden="true">
                        {item.icon}
                      </span>
                      <span>{item.label}</span>
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <main id="main-content" className="main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>

      <footer className="app-footer">
        <span>RAG Quality Monitor · {theme} theme</span>
        <span>Metrics are observations, not proof. Always read the evidence.</span>
      </footer>
    </div>
  )
}
