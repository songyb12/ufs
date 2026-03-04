import { useState } from 'react'
import Sidebar from './components/Sidebar'
import Overview from './pages/Overview'
import Signals from './pages/Signals'
import Portfolio from './pages/Portfolio'
import System from './pages/System'

function App() {
  const [page, setPage] = useState('overview')

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
      <Sidebar activePage={page} onNavigate={setPage} />
      <main className="main-content">
        {renderPage()}
      </main>
    </>
  )
}

export default App
