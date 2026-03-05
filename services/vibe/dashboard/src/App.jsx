import { useState, Component } from 'react'
import LoginGate from './components/LoginGate'
import Sidebar from './components/Sidebar'
import Overview from './pages/Overview'
import Signals from './pages/Signals'
import Portfolio from './pages/Portfolio'
import Backtest from './pages/Backtest'
import MarketBrief from './pages/MarketBrief'
import System from './pages/System'
import Guide from './pages/Guide'

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

function App() {
  const [page, setPage] = useState('overview')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [guideSection, setGuideSection] = useState(null)

  const navigateTo = (target, section) => {
    if (target === 'guide' && section) {
      setGuideSection(section)
    }
    setPage(target)
  }

  const renderPage = () => {
    switch (page) {
      case 'overview': return <Overview onNavigate={navigateTo} />
      case 'signals': return <Signals onNavigate={navigateTo} />
      case 'portfolio': return <Portfolio onNavigate={navigateTo} />
      case 'backtest': return <Backtest onNavigate={navigateTo} />
      case 'market-brief': return <MarketBrief onNavigate={navigateTo} />
      case 'system': return <System onNavigate={navigateTo} />
      case 'guide': return <Guide onNavigate={navigateTo} initialSection={guideSection} />
      default: return <Overview onNavigate={navigateTo} />
    }
  }

  return (
    <LoginGate>
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
        <ErrorBoundary>
          {renderPage()}
        </ErrorBoundary>
      </main>
    </LoginGate>
  )
}

export default App
