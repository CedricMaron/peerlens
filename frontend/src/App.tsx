import { useCallback, useEffect, useState } from 'react'
import { NavLink, Route, Routes, Link } from 'react-router-dom'
import { api } from './api'
import { formatCost, formatTokens } from './components/common'
import BranchPage from './pages/BranchPage'
import PaperPage from './pages/PaperPage'
import ResearchHome from './pages/ResearchHome'
import SettingsPage from './pages/SettingsPage'
import UsagePage from './pages/UsagePage'
import type { ProviderSettings, UsageSummary } from './types'

/** Lets any page ask the header to refresh its usage figures after AI calls. */
export const USAGE_REFRESH_EVENT = 'peerlens:usage-changed'
export function notifyUsageChanged() {
  window.dispatchEvent(new Event(USAGE_REFRESH_EVENT))
}

function TopBar() {
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [provider, setProvider] = useState<ProviderSettings | null>(null)

  const refresh = useCallback(() => {
    api.getUsageSummary().then(setUsage).catch(() => setUsage(null))
    api.getProvider().then(setProvider).catch(() => setProvider(null))
  }, [])

  useEffect(() => {
    refresh()
    window.addEventListener(USAGE_REFRESH_EVENT, refresh)
    return () => window.removeEventListener(USAGE_REFRESH_EVENT, refresh)
  }, [refresh])

  return (
    <header className="topbar">
      <Link to="/" className="brand">
        Peer<span>Lens</span>
      </Link>
      <nav className="nav">
        <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>
          Research
        </NavLink>
        <NavLink to="/usage" className={({ isActive }) => (isActive ? 'active' : '')}>
          Usage
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => (isActive ? 'active' : '')}>
          Settings
        </NavLink>
      </nav>
      <div className="topbar-right">
        {provider && (
          <span className={`provider-chip${provider.configured ? '' : ' warn'}`}>
            {provider.configured ? (
              <>
                {provider.provider} · {provider.model}
              </>
            ) : (
              <Link to="/settings">No AI provider configured</Link>
            )}
          </span>
        )}
        {usage && usage.calls > 0 && (
          <Link to="/usage" className="usage-chip" title={`${usage.calls} AI calls`}>
            Tokens {formatTokens(usage.total_tokens)} · {formatCost(usage.estimated_cost)}
            {usage.cost_is_partial ? '+' : ''}
          </Link>
        )}
      </div>
    </header>
  )
}

export default function App() {
  return (
    <div className="app">
      <TopBar />
      <Routes>
        <Route path="/" element={<ResearchHome />} />
        <Route path="/branches/:branchId" element={<BranchPage />} />
        <Route path="/papers/:paperId" element={<PaperPage />} />
        <Route path="/usage" element={<UsagePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route
          path="*"
          element={
            <main className="page">
              <div className="empty">
                Page not found. <Link to="/">Back to Research</Link>
              </div>
            </main>
          }
        />
      </Routes>
    </div>
  )
}
