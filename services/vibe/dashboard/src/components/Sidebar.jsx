import { useState, useEffect } from 'react'
import { getHealth } from '../api'

const NAV_GROUPS = [
  {
    label: '핵심',
    items: [
      { id: 'overview', icon: '\u2302', label: '오버뷰' },
      { id: 'action-plan', icon: '\uD83D\uDCCB', label: '액션 플랜', accent: true },
      { id: 'soxl', icon: '\uD83D\uDCB9', label: 'SOXL', accent: true },
      { id: 'geopolitical', icon: '\uD83C\uDF0D', label: '이란-미국 이슈' },
    ],
  },
  {
    label: '분석',
    items: [
      { id: 'signals', icon: '\u26A1', label: '시그널' },
      { id: 'macro', icon: '\uD83C\uDF10', label: '매크로' },
      { id: 'fund-flow', icon: '\uD83D\uDCB0', label: '자금흐름' },
      { id: 'screening', icon: '\uD83D\uDD0D', label: '스크리닝' },
      { id: 'guru', icon: '\uD83C\uDFAF', label: '구루 인사이트' },
    ],
  },
  {
    label: '포트폴리오',
    items: [
      { id: 'portfolio', icon: '\uD83D\uDCBC', label: '포트폴리오' },
      { id: 'risk', icon: '\uD83D\uDEE1', label: '리스크' },
      { id: 'backtest', icon: '\uD83E\uDDEA', label: '백테스트' },
    ],
  },
  {
    label: '학습·리포트',
    items: [
      { id: 'market-brief', icon: '\uD83D\uDCCA', label: '시황 브리핑' },
      { id: 'academy', icon: '\uD83C\uDF93', label: '투자 아카데미' },
    ],
  },
  {
    label: '관리',
    items: [
      { id: 'strategy', icon: '\uD83D\uDD27', label: '전략 설정' },
      { id: 'system', icon: '\u2699', label: '시스템' },
      { id: 'guide', icon: '\uD83D\uDCD6', label: '사용 가이드' },
    ],
  },
]

export default function Sidebar({ activePage, onNavigate, mobileOpen, onMobileToggle }) {
  const [health, setHealth] = useState(null)
  const [collapsed, setCollapsed] = useState({})

  useEffect(() => {
    getHealth()
      .then(h => setHealth(h))
      .catch(() => setHealth(null))
  }, [])

  const handleNav = (id) => {
    onNavigate(id)
    if (onMobileToggle) onMobileToggle(false)
  }

  const toggleGroup = (label) => {
    setCollapsed(prev => ({ ...prev, [label]: !prev[label] }))
  }

  return (
    <>
      {mobileOpen && (
        <div
          className="sidebar-overlay"
          onClick={() => onMobileToggle?.(false)}
        />
      )}
      <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-logo">
          <h1>VIBE</h1>
          <span>Investment Intelligence</span>
        </div>
        <nav style={{ flex: 1, overflowY: 'auto' }}>
          {NAV_GROUPS.map((group) => (
            <div key={group.label} style={{ marginBottom: '0.25rem' }}>
              <div
                className="sidebar-group-header"
                onClick={() => toggleGroup(group.label)}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '0.4rem 1.5rem 0.25rem',
                  cursor: 'pointer', userSelect: 'none',
                }}
              >
                <span style={{
                  fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase',
                  letterSpacing: '0.08em', color: 'var(--text-muted)',
                }}>
                  {group.label}
                </span>
                <span style={{
                  fontSize: '0.6rem', color: 'var(--text-muted)',
                  transform: collapsed[group.label] ? 'rotate(-90deg)' : 'rotate(0)',
                  transition: 'transform 0.15s',
                }}>
                  {'\u25BC'}
                </span>
              </div>
              {!collapsed[group.label] && (
                <ul className="sidebar-nav">
                  {group.items.map(link => (
                    <li key={link.id}>
                      <a
                        href="#"
                        className={`${activePage === link.id ? 'active' : ''} ${link.accent ? 'nav-accent' : ''}`}
                        onClick={(e) => { e.preventDefault(); handleNav(link.id) }}
                      >
                        <span>{link.icon}</span>
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-status">
            <span className={`status-dot ${health?.status === 'healthy' ? 'green' : 'red'}`} />
            <span>{health?.status === 'healthy' ? 'Online' : 'Offline'}</span>
          </div>
          <span className="sidebar-version">v{health?.version || '...'}</span>
        </div>
      </aside>
    </>
  )
}
