import { useState, useCallback, useRef, Component } from 'react'
import LoginGate from './components/LoginGate'
import { ToastProvider, useToast } from './components/Toast'
import Sidebar from './components/Sidebar'
import { refreshPrices } from './api'
import Overview from './pages/Overview'
import Signals from './pages/Signals'
import Portfolio from './pages/Portfolio'
import Backtest from './pages/Backtest'
import MarketBrief from './pages/MarketBrief'
import Macro from './pages/Macro'
import FundFlow from './pages/FundFlow'
import Screening from './pages/Screening'
import Risk from './pages/Risk'
import System from './pages/System'
import Guru from './pages/Guru'
import ActionPlan from './pages/ActionPlan'
import Academy from './pages/Academy'
import Strategy from './pages/Strategy'
import Guide from './pages/Guide'
import Soxl from './pages/Soxl'
import Geopolitical from './pages/Geopolitical'

// M14: Error Boundary to catch render crashes
class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '2rem',
          textAlign: 'center',
          color: 'var(--text-secondary)',
        }}>
          <h2 style={{ color: 'var(--red)', marginBottom: '1rem' }}>
            {'\u26A0'} Something went wrong
          </h2>
          <p style={{ marginBottom: '1rem' }}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
          <button
            className="btn btn-primary"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            {'\u21BB'} Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

// ── Global Refresh Bar ──
function GlobalRefreshBar({ onRefresh, refreshing, lastRefreshed }) {
  const timeStr = lastRefreshed
    ? lastRefreshed.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
    : null

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '0.5rem',
      padding: '0.4rem 0.75rem', marginBottom: '0.75rem',
      background: 'var(--bg-secondary)', borderRadius: '0.5rem',
      border: '1px solid var(--border)', fontSize: '0.75rem',
    }}>
      <button
        className="btn btn-primary"
        onClick={onRefresh}
        disabled={refreshing}
        style={{ padding: '0.3rem 0.75rem', fontSize: '0.75rem', whiteSpace: 'nowrap' }}
      >
        {refreshing ? '\u23F3 갱신 중...' : '\u21BB 전체 갱신'}
      </button>
      <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
        가격 + 현재 페이지 데이터 갱신
      </span>
      {timeStr && (
        <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: '0.7rem' }}>
          {'\u23F0'} {timeStr}
        </span>
      )}
    </div>
  )
}

function App() {
  const [page, setPage] = useState('overview')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [guideSection, setGuideSection] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [globalRefreshing, setGlobalRefreshing] = useState(false)
  const [lastRefreshed, setLastRefreshed] = useState(null)
  const toastRef = useRef(null)

  const navigateTo = (target, section) => {
    if (target === 'guide' && section) {
      setGuideSection(section)
    } else {
      setGuideSection(null)
    }
    setPage(target)
    window.scrollTo({ top: 0, behavior: 'instant' })
  }

  const handleGlobalRefresh = useCallback(async () => {
    setGlobalRefreshing(true)
    try {
      const res = await refreshPrices('ALL')
      const rows = res.total_rows || 0
      setRefreshKey(k => k + 1)
      setLastRefreshed(new Date())
      if (toastRef.current) toastRef.current.success(`전체 갱신 완료 (가격 ${rows}건)`)
    } catch (err) {
      setRefreshKey(k => k + 1)
      if (toastRef.current) toastRef.current.warn(`가격 갱신 실패, 페이지 데이터만 갱신됨`)
    } finally {
      setGlobalRefreshing(false)
    }
  }, [])

  const renderPage = () => {
    const props = { onNavigate: navigateTo, refreshKey }
    switch (page) {
      case 'overview': return <Overview {...props} />
      case 'signals': return <Signals {...props} />
      case 'portfolio': return <Portfolio {...props} />
      case 'backtest': return <Backtest {...props} />
      case 'market-brief': return <MarketBrief {...props} />
      case 'macro': return <Macro {...props} />
      case 'fund-flow': return <FundFlow {...props} />
      case 'screening': return <Screening {...props} />
      case 'risk': return <Risk {...props} />
      case 'guru': return <Guru {...props} />
      case 'action-plan': return <ActionPlan {...props} />
      case 'academy': return <Academy {...props} />
      case 'strategy': return <Strategy {...props} />
      case 'system': return <System {...props} />
      case 'soxl': return <Soxl {...props} />
      case 'geopolitical': return <Geopolitical {...props} />
      case 'guide': return <Guide onNavigate={navigateTo} initialSection={guideSection} />
      default: return <Overview {...props} />
    }
  }

  return (
    <LoginGate>
      <ToastProvider toastRef={toastRef}>
        <Sidebar
          activePage={page}
          onNavigate={navigateTo}
          mobileOpen={mobileOpen}
          onMobileToggle={setMobileOpen}
        />
        <main className="main-content">
          <button
            className="mobile-menu-btn"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="메뉴"
          >
            {'\u2630'}
          </button>
          <GlobalRefreshBar
            onRefresh={handleGlobalRefresh}
            refreshing={globalRefreshing}
            lastRefreshed={lastRefreshed}
          />
          <ErrorBoundary key={page}>
            {renderPage()}
          </ErrorBoundary>
        </main>
      </ToastProvider>
    </LoginGate>
  )
}

export default App
