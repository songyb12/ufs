import { useState, useEffect, useCallback } from 'react'
import { getRiskPortfolio, getRiskEvents, seedRiskEvents, getRiskSectors } from '../api'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid
} from 'recharts'
import SymbolModal from '../components/SymbolModal'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import { useToast } from '../components/Toast'

const SECTOR_COLORS = [
  '#3b82f6', '#22c55e', '#eab308', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#06b6d4',
  '#a855f7', '#10b981', '#f43f5e', '#84cc16',
]

const EVENT_ICONS = {
  fomc: '🏦', holiday: '🎉', options_expiry: '📅',
  earnings: '📊', cpi: '💰', employment: '👥',
  default: '🔔',
}

export default function Risk({ onNavigate, refreshKey }) {
  const toast = useToast()
  const [riskData, setRiskData] = useState(null)
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [market, setMarket] = useState('')
  const [eventMarket, setEventMarket] = useState('KR')
  const [daysAhead, setDaysAhead] = useState(30)
  const [seeding, setSeeding] = useState(false)
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [sectorRisk, setSectorRisk] = useState(null)

  const loadData = useCallback(() => {
    setLoading(true)
    Promise.all([
      getRiskPortfolio(market || null),
      getRiskEvents(eventMarket, daysAhead),
      getRiskSectors().catch(() => null),
    ])
      .then(([risk, evt, sr]) => {
        setRiskData(risk)
        setEvents(evt.events || [])
        setSectorRisk(sr)
        setError(null)
      })
      .catch(err => { console.error(err); setError(err.message); toast.error('리스크 데이터 로드 실패: ' + err.message) })
      .finally(() => setLoading(false))
  }, [market, eventMarket, daysAhead])

  useEffect(() => { loadData() }, [loadData, refreshKey])

  const handleSeedEvents = async () => {
    setSeeding(true)
    try {
      const r = await seedRiskEvents()
      toast.success(`${r.seeded}개 이벤트 시딩 완료`)
      loadData()
    } catch (err) {
      toast.error('이벤트 시딩 실패: ' + err.message)
    } finally {
      setSeeding(false)
    }
  }

  // Sector exposure chart data
  const sectorData = riskData?.sector_exposure
    ? Object.entries(riskData.sector_exposure)
        .map(([name, value]) => ({ name, value: +(Number(value) || 0).toFixed(1) }))
        .sort((a, b) => b.value - a.value)
    : []

  // Market concentration (top 5 positions by size)
  const positions = riskData?.positions || []
  const totalValue = positions.reduce((sum, p) => sum + (p.position_size || 0), 0)
  const top5 = [...positions]
    .sort((a, b) => (b.position_size || 0) - (a.position_size || 0))
    .slice(0, 5)
  const top5Pct = totalValue > 0
    ? top5.reduce((sum, p) => sum + (p.position_size || 0), 0) / totalValue * 100
    : 0

  // Concentration data for bar chart
  const concData = top5.map(p => ({
    name: p.name || p.symbol,
    weight: totalValue > 0 ? +((p.position_size || 0) / totalValue * 100).toFixed(1) : 0,
    pnl: p.pnl_pct || 0,
  }))

  // Events grouped by type — use local date string for correct timezone handling
  const todayStr = new Date().toLocaleDateString('en-CA') // YYYY-MM-DD format
  const upcomingEvents = events
    .filter(e => e.event_date >= todayStr)
    .sort((a, b) => (a.event_date || '').localeCompare(b.event_date || ''))

  const pastEvents = events
    .filter(e => e.event_date < todayStr)
    .sort((a, b) => (b.event_date || '').localeCompare(a.event_date || ''))
    .slice(0, 10)

  if (loading) return <div className="loading"><span className="spinner" /> 로딩 중...</div>

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'🛡'} 리스크 대시보드</h2>
          <p className="subtitle">포트폴리오 리스크 분석 및 이벤트 캘린더</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-outline" onClick={loadData}>{'↻'} Refresh</button>
          <HelpButton section="risk" onNavigate={onNavigate} />
        </div>
      </div>

      <PageGuide
        pageId="risk"
        title="이 페이지에서 확인할 것"
        steps={[
          '섹터 집중도 → 한 섹터 40% 이상이면 분산 필요',
          'VaR (Value at Risk) → 최대 예상 손실액',
          '이벤트 캘린더 → FOMC/CPI 등 주요 일정 대비',
          '상관관계 → 보유 종목끼리 동조화 여부',
        ]}
        color="#ef4444"
      />

      {error && (
        <div className="card" style={{ marginBottom: '1rem', borderColor: 'var(--red)', padding: '0.75rem 1.25rem', color: 'var(--red)' }}>
          Error: {error}
        </div>
      )}

      {/* Risk Summary Cards */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <div className="card">
          <div className="card-label">총 포지션</div>
          <div className="card-value blue">{riskData?.total_positions || 0}</div>
          <div className="card-sub">{market || '전체'} 마켓</div>
        </div>
        <div className="card">
          <div className="card-label">섹터 수</div>
          <div className="card-value blue">{sectorData.length}</div>
          <div className="card-sub">분산도</div>
        </div>
        <div className="card">
          <div className="card-label">Top 5 집중도</div>
          <div className={`card-value ${top5Pct > 70 ? 'red' : top5Pct > 50 ? 'yellow' : 'green'}`}>
            {top5Pct.toFixed(1)}%
          </div>
          <div className="card-sub">{top5Pct > 70 ? '고위험' : top5Pct > 50 ? '보통' : '분산 양호'}</div>
        </div>
        <div className="card">
          <div className="card-label">예정 이벤트</div>
          <div className="card-value yellow">{upcomingEvents.length}</div>
          <div className="card-sub">향후 {daysAhead}일</div>
        </div>
      </div>

      {/* Market Filter */}
      <div className="filter-bar">
        <select value={market} onChange={e => setMarket(e.target.value)}>
          <option value="">All Markets</option>
          <option value="KR">KR</option>
          <option value="US">US</option>
        </select>
      </div>

      {/* Charts Row */}
      <div className="grid-2">
        {/* Sector Exposure Pie */}
        <div className="chart-container">
          <h3>{'🎯'} Sector Exposure</h3>
          {sectorData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={sectorData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={95}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}%`}
                  labelLine={{ stroke: '#94a3b8' }}
                >
                  {sectorData.map((entry, idx) => (
                    <Cell key={entry.name} fill={SECTOR_COLORS[idx % SECTOR_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.8rem' }}
                  formatter={(v) => [`${v}%`, 'Exposure']}
                />
                <Legend
                  wrapperStyle={{ fontSize: '0.7rem' }}
                  formatter={(val) => val.length > 12 ? val.slice(0, 10) + '..' : val}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              포트폴리오에 포지션이 없습니다
            </div>
          )}
        </div>

        {/* Position Concentration Bar */}
        <div className="chart-container">
          <h3>{'📊'} Top 5 Position Weight</h3>
          {concData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={concData} layout="vertical" margin={{ left: 10, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 10 }} unit="%" />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: '#94a3b8', fontSize: 10 }}
                  width={90}
                  tickFormatter={v => v?.length > 12 ? v.slice(0, 10) + '..' : v}
                />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.8rem' }}
                  formatter={(v, name) => [
                    name === 'weight' ? `${v}%` : `${(v ?? 0) >= 0 ? '+' : ''}${(v ?? 0).toFixed(1)}%`,
                    name === 'weight' ? '비중' : 'P&L'
                  ]}
                />
                <Legend formatter={(val) => val === 'weight' ? '비중(%)' : 'P&L(%)'} wrapperStyle={{ fontSize: '0.75rem' }} />
                <Bar dataKey="weight" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={12} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 260, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              포지션 데이터 없음
            </div>
          )}
        </div>
      </div>

      {/* Event Calendar Section */}
      <div className="table-container">
        <div className="table-header">
          <h3>{'📅'} Event Calendar</h3>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <select value={eventMarket} onChange={e => setEventMarket(e.target.value)}
              style={{ padding: '0.3rem 0.5rem', borderRadius: '0.25rem', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: '0.8rem' }}>
              <option value="KR">KR</option>
              <option value="US">US</option>
            </select>
            <select value={daysAhead} onChange={e => setDaysAhead(Number(e.target.value))}
              style={{ padding: '0.3rem 0.5rem', borderRadius: '0.25rem', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: '0.8rem' }}>
              <option value={7}>7 Days</option>
              <option value={14}>14 Days</option>
              <option value={30}>30 Days</option>
              <option value={90}>90 Days</option>
            </select>
            <button className="btn btn-outline btn-sm" onClick={handleSeedEvents} disabled={seeding}>
              {seeding ? '⏳...' : '🌱 Seed Events'}
            </button>
          </div>
        </div>

        {/* Upcoming Events */}
        {upcomingEvents.length > 0 ? (
          <div style={{ padding: '0.75rem 1.25rem' }}>
            <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
              Upcoming ({upcomingEvents.length})
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {upcomingEvents.map((e, idx) => {
                const daysUntil = Math.ceil((new Date(e.event_date + 'T00:00:00') - new Date(todayStr + 'T00:00:00')) / (1000 * 60 * 60 * 24))
                const icon = EVENT_ICONS[e.event_type] || EVENT_ICONS.default
                return (
                  <div key={`upcoming-${idx}`} style={{
                    display: 'flex', alignItems: 'center', gap: '0.75rem',
                    padding: '0.5rem 0.75rem', borderRadius: '0.5rem',
                    background: daysUntil <= 3 ? 'rgba(239,68,68,0.08)' : daysUntil <= 7 ? 'rgba(234,179,8,0.06)' : 'transparent',
                    border: '1px solid var(--border)',
                  }}>
                    <span style={{ fontSize: '1.25rem' }}>{icon}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                        {e.event_name || e.event_type}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                        {e.description || e.event_type}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontSize: '0.8rem', fontWeight: 600, color: daysUntil <= 3 ? 'var(--red)' : daysUntil <= 7 ? 'var(--yellow)' : 'var(--text-secondary)' }}>
                        {daysUntil === 0 ? 'TODAY' : daysUntil === 1 ? 'Tomorrow' : `D-${daysUntil}`}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{e.event_date}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ) : (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            {daysAhead}일 이내 예정된 이벤트가 없습니다. "Seed Events"를 클릭하여 이벤트를 등록하세요.
          </div>
        )}

        {/* Past Events */}
        {pastEvents.length > 0 && (
          <div style={{ padding: '0.75rem 1.25rem', borderTop: '1px solid var(--border)' }}>
            <h4 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
              Recent Past ({pastEvents.length})
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
              {pastEvents.map((e, idx) => {
                const icon = EVENT_ICONS[e.event_type] || EVENT_ICONS.default
                return (
                  <div key={`past-${idx}`} style={{
                    display: 'flex', alignItems: 'center', gap: '0.75rem',
                    padding: '0.375rem 0.75rem', opacity: 0.6,
                    fontSize: '0.8rem',
                  }}>
                    <span>{icon}</span>
                    <span style={{ flex: 1 }}>{e.event_name || e.event_type}</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>{e.event_date}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Position Detail Table */}
      {positions.length > 0 && (
        <div className="table-container">
          <div className="table-header">
            <h3>Position Risk Detail</h3>
            <span className="card-sub">{positions.length} positions</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th className="hide-on-mobile">Sector</th>
                <th>Weight</th>
                <th>P&L</th>
                <th className="hide-on-tablet">Entry</th>
                <th className="hide-on-tablet">Current</th>
                <th className="hide-on-mobile">Size</th>
              </tr>
            </thead>
            <tbody>
              {[...positions]
                .sort((a, b) => (b.position_size || 0) - (a.position_size || 0))
                .map((p, idx) => {
                  const weight = totalValue > 0 ? ((p.position_size || 0) / totalValue * 100) : 0
                  const pnl = p.pnl_pct || 0
                  return (
                    <tr key={`${p.symbol}-${p.market}-${idx}`}
                      style={{ background: pnl <= -7 ? 'rgba(239,68,68,0.08)' : pnl <= -5 ? 'rgba(234,179,8,0.05)' : 'transparent' }}>
                      <td
                        className="symbol-link"
                        onClick={() => setSelectedSymbol({ symbol: p.symbol, market: p.market })}
                      >
                        <strong>{p.name || p.symbol}</strong>
                        <br />
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{p.symbol} ({p.market})</span>
                      </td>
                      <td className="hide-on-mobile" style={{ fontSize: '0.8rem' }}>{p.sector || '-'}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <div style={{ width: 40, height: 6, borderRadius: 3, background: 'var(--bg-primary)', overflow: 'hidden' }}>
                            <div style={{ width: `${Math.min(100, weight)}%`, height: '100%', background: 'var(--accent)', borderRadius: 3 }} />
                          </div>
                          <span style={{ fontSize: '0.8rem' }}>{weight.toFixed(1)}%</span>
                        </div>
                      </td>
                      <td style={{ color: pnl >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                        {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%
                      </td>
                      <td className="hide-on-tablet">{p.entry_price?.toLocaleString() || '-'}</td>
                      <td className="hide-on-tablet">{p.current_price != null ? (p.market === 'KR' ? Math.round(p.current_price) : p.current_price).toLocaleString() : '-'}</td>
                      <td className="hide-on-mobile" style={{ fontSize: '0.8rem' }}>
                        {(p.position_size || 0).toLocaleString()}
                      </td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        </div>
      )}

      {selectedSymbol && (
        <SymbolModal
          symbol={selectedSymbol.symbol}
          market={selectedSymbol.market}
          onClose={() => setSelectedSymbol(null)}
        />
      )}
    </div>
  )
}
