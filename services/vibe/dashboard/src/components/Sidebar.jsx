export default function Sidebar({ activePage, onNavigate, mobileOpen, onMobileToggle }) {
  const links = [
    { id: 'overview', icon: '\u2302', label: '\uC624\uBC84\uBDF0' },
    { id: 'signals', icon: '\u26A1', label: '\uC2DC\uADF8\uB110' },
    { id: 'portfolio', icon: '\uD83D\uDCBC', label: '\uD3EC\uD2B8\uD3F4\uB9AC\uC624' },
    { id: 'backtest', icon: '\uD83E\uDDEA', label: '\uBC31\uD14C\uC2A4\uD2B8' },
    { id: 'system', icon: '\u2699', label: '\uC2DC\uC2A4\uD15C' },
  ]

  const handleNav = (id) => {
    onNavigate(id)
    if (onMobileToggle) onMobileToggle(false)
  }

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="sidebar-overlay"
          onClick={() => onMobileToggle(false)}
        />
      )}
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-logo">
          <h1>VIBE</h1>
          <span>Investment Intelligence</span>
        </div>
        <nav>
          <ul className="sidebar-nav">
            {links.map(link => (
              <li key={link.id}>
                <a
                  href="#"
                  className={activePage === link.id ? 'active' : ''}
                  onClick={(e) => { e.preventDefault(); handleNav(link.id) }}
                >
                  <span>{link.icon}</span>
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
    </>
  )
}
