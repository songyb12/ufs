import { useState } from 'react'
import Sidebar from './components/Sidebar'
import Overview from './pages/Overview'
import Signals from './pages/Signals'
import Portfolio from './pages/Portfolio'
import System from './pages/System'

function App() {
  const [page, setPage] = useState('overview')
  const [mobileOpen, setMobileOpen] = useState(false)

  const renderPage = () => {
    switch (page) {
      case 'overview': return <Overview />
      case 'signals': return <Signals />
      case 'portfolio': return <Portfolio />
      case 'system': return <System />
      default: return <Overview />
    }
  }

  return (
    <>
      <Sidebar
        activePage={page}
        onNavigate={setPage}
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
        {renderPage()}
      </main>
    </>
  )
}

export default App
