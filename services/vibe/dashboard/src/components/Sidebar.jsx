export default function Sidebar({ activePage, onNavigate }) {
  const links = [
    { id: 'overview', icon: '\u2302', label: '\uC624\uBC84\uBDF0' },
    { id: 'signals', icon: '\u26A1', label: '\uC2DC\uADF8\uB110' },
    { id: 'portfolio', icon: '\uD83D\uDCBC', label: '\uD3EC\uD2B8\uD3F4\uB9AC\uC624' },
    { id: 'system', icon: '\u2699', label: '\uC2DC\uC2A4\uD15C' },
  ]

  return (
    <aside className="sidebar">
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
                onClick={(e) => { e.preventDefault(); onNavigate(link.id) }}
              >
                <span>{link.icon}</span>
                {link.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}
