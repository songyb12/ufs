import { useState, useEffect } from 'react'
import { getHealth } from '../api'

const NAV_GROUPS = [
  {
    label: '데일리',
    items: [
      { id: 'overview', icon: '⌂', label: '오버뷰' },
      { id: 'action-plan', icon: '📋', label: '액션 플랜', accent: true },
      { id: 'signals', icon: '📡', label: '시그널' },
      { id: 'market-brief', icon: '📊', label: '시황 브리핑' },
    ],
  },
  {
    label: 'SOXL',
    items: [
      { id: 'soxl', icon: '💹', label: 'SOXL 분석', accent: true },
      { id: 'soxl-live', icon: '⚡', label: 'SOXL 실시간', accent: true },
    ],
  },
  {
    label: '시장 분석',
    items: [
      { id: 'macro', icon: '🌐', label: '매크로' },
      { id: 'screening', icon: '🔍', label: '스크리닝' },
      { id: 'fund-flow', icon: '💰', label: '자금흐름' },
      { id: 'geopolitical', icon: '🌍', label: '이란-미국 이슈' },
    ],
  },
  {
    label: '글로벌',
    items: [
      { id: 'carry-trade', icon: '💱', label: '캐리트레이드' },
      { id: 'forex-map', icon: '🗺', label: '환율 세계지도' },
      { id: 'guru', icon: '🎯', label: '구루 인사이트' },
    ],
  },
  {
    label: '포트폴리오',
    items: [
      { id: 'portfolio', icon: '💼', label: '포트폴리오' },
      { id: 'risk', icon: '🛡', label: '리스크' },
      { id: 'backtest', icon: '🧪', label: '백테스트' },
    ],
  },
  {
    label: '설정',
    defaultCollapsed: true,
    items: [
      { id: 'academy', icon: '🎓', label: '투자 아카데미' },
      { id: 'strategy', icon: '🔧', label: '전략 설정' },
      { id: 'data-admin', icon: '📋', label: '데이터 관리' },
      { id: 'system', icon: '⚙', label: '시스템' },
      { id: 'guide', icon: '📖', label: '사용 가이드' },
    ],
  },
]

export default function Sidebar({ activePage, onNavigate, mobileOpen, onMobileToggle }) {
  const [health, setHealth] = useState(null)
  const [collapsed, setCollapsed] = useState(() => {
    const init = {}
    NAV_GROUPS.forEach(g => { if (g.defaultCollapsed) init[g.label] = true })
    return init
  })

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
                  {'▼'}
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
