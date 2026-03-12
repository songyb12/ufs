import { useState, useEffect } from 'react'
import { useToast } from '../components/Toast'
import { getIranUsDashboard } from '../api'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts'

const IMPACT_COLOR = {
  severe_negative: '#ff1744',
  negative: '#ff5252',
  neutral: '#ffeb3b',
  positive: '#00e676',
}

const DIR_STYLE = {
  up: { bg: 'rgba(0,230,118,0.1)', color: '#00e676', icon: '⬆' },
  down: { bg: 'rgba(255,23,68,0.1)', color: '#ff1744', icon: '⬇' },
}

const MAG_LABEL = { very_high: '극심', high: '강', medium: '중', low: '약' }

export default function Geopolitical({ onNavigate, refreshKey }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  const toast = useToast()

  useEffect(() => {
    setLoading(true)
    getIranUsDashboard()
      .then(d => setData(d))
      .catch(err => toast.error('지정학 데이터 로드 실패: ' + err.message))
      .finally(() => setLoading(false))
  }, [refreshKey])

  if (loading) return <div className="loading">⏳ 지정학 데이터 로딩...</div>
  if (!data) return <div className="loading">⚠ 데이터를 불러올 수 없습니다</div>

  const tabs = [
    { id: 'overview', label: '타임라인' },
    { id: 'sectors', label: '섹터 영향' },
    { id: 'semi', label: '반도체 리스크' },
    { id: 'strategy', label: '대응 전략' },
  ]

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div>
          <h2>🌍 {data.event_name}</h2>
          <p style={{ color: 'var(--text-muted)', margin: '0.25rem 0 0' }}>
            상태: <span style={{ color: '#ff5252', fontWeight: 700 }}>{data.status}</span> &mdash;
            개전 {data.start_date} &middot; {data.days_elapsed}일차
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => onNavigate('soxl')}>
          💹 SOXL 페이지 →
        </button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.25rem', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
        {tabs.map(t => (
          <button key={t.id} className={`btn ${activeTab === t.id ? 'btn-primary' : ''}`}
            style={{ padding: '0.4rem 1rem', fontSize: '0.8rem' }}
            onClick={() => setActiveTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && <OverviewTab data={data} />}
      {activeTab === 'sectors' && <SectorTab data={data} />}
      {activeTab === 'semi' && <SemiTab data={data} />}
      {activeTab === 'strategy' && <StrategyTab data={data} />}
    </div>
  )
}

/* ── Overview Tab (Timeline + Macro + Market Impact) ── */
function OverviewTab({ data }) {
  const { timeline, market_impact, macro_snapshot, live_data } = data

  return (
    <>
      {/* Macro Snapshot */}
      {macro_snapshot && (
        <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', marginBottom: '1rem' }}>
          <MiniCard label="VIX" value={macro_snapshot.vix?.toFixed(1)} color={macro_snapshot.vix > 30 ? 'var(--red)' : 'var(--yellow)'} />
          <MiniCard label="WTI 원유" value={macro_snapshot.wti_crude ? `$${macro_snapshot.wti_crude.toFixed(1)}` : '-'} color="var(--red)" />
          <MiniCard label="금" value={macro_snapshot.gold ? `$${macro_snapshot.gold.toFixed(0)}` : '-'} color="#ffd700" />
          <MiniCard label="USD/KRW" value={macro_snapshot.usd_krw?.toFixed(0)} color="var(--text-primary)" />
          <MiniCard label="DXY" value={macro_snapshot.dxy?.toFixed(1)} color="var(--text-primary)" />
        </div>
      )}

      {/* Timeline */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3>📅 분쟁 타임라인</h3>
        <div style={{ marginTop: '0.75rem' }}>
          {timeline?.map((t, i) => (
            <div key={i} style={{
              display: 'flex', gap: '0.75rem', padding: '0.6rem 0',
              borderBottom: i < timeline.length - 1 ? '1px solid var(--border)' : 'none',
            }}>
              <div style={{ minWidth: '90px', fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                {t.date}
              </div>
              <div style={{
                width: '10px', height: '10px', borderRadius: '50%', marginTop: '4px', flexShrink: 0,
                background: IMPACT_COLOR[t.impact] || 'var(--text-muted)',
              }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{t.event}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>{t.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Market Impact Summary */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3>📉 주요 시장 영향</h3>
        <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', marginTop: '0.75rem', gap: '0.75rem' }}>
          {market_impact && Object.entries(market_impact).map(([key, m]) => (
            <div key={key} style={{
              padding: '0.75rem', background: 'var(--bg-secondary)', borderRadius: '0.5rem',
              borderLeft: `3px solid ${m.change_pct?.startsWith('+') ? 'var(--green)' : 'var(--red)'}`,
            }}>
              <div style={{ fontWeight: 700, marginBottom: '0.25rem' }}>{m.title}</div>
              {m.before && <div style={{ fontSize: '0.75rem' }}>전: {m.before} → 후: {m.after}</div>}
              {m.change_pct && <div style={{ fontWeight: 700, color: m.change_pct.startsWith('+') ? 'var(--green)' : 'var(--red)' }}>{m.change_pct}</div>}
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>{m.detail}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Live Price Charts */}
      {live_data && Object.keys(live_data).length > 0 && (
        <div className="card">
          <h3>📈 주요 ETF 추이 (30일)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} tickFormatter={d => d?.slice(5)}
                type="category" allowDuplicatedCategory={false} />
              <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} domain={['auto', 'auto']} />
              <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8 }} />
              <Legend />
              {Object.entries(live_data).map(([sym, prices], idx) => {
                const colors = ['#6366f1', '#f59e0b', '#10b981']
                // Normalize to % change from first
                const base = prices[0]?.close || 1
                const normalized = prices.map(p => ({ date: p.date, [sym]: ((p.close - base) / base * 100).toFixed(2) }))
                return <Line key={sym} data={normalized} dataKey={sym} name={sym} stroke={colors[idx % colors.length]}
                  dot={false} strokeWidth={2} type="monotone" />
              })}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </>
  )
}

/* ── Sector Impact Tab ── */
function SectorTab({ data }) {
  const { sector_impact } = data
  const winners = sector_impact?.filter(s => s.direction === 'up') || []
  const losers = sector_impact?.filter(s => s.direction === 'down') || []

  return (
    <>
      {/* Winners */}
      <div className="card" style={{ marginBottom: '1rem', borderLeft: '4px solid var(--green)' }}>
        <h3>⬆️ 수혜 섹터</h3>
        <div style={{ marginTop: '0.5rem' }}>
          {winners.map((s, i) => <SectorRow key={i} s={s} />)}
        </div>
      </div>

      {/* Losers */}
      <div className="card" style={{ borderLeft: '4px solid var(--red)' }}>
        <h3>⬇️ 피해 섹터</h3>
        <div style={{ marginTop: '0.5rem' }}>
          {losers.map((s, i) => <SectorRow key={i} s={s} />)}
        </div>
      </div>
    </>
  )
}

function SectorRow({ s }) {
  const d = DIR_STYLE[s.direction] || DIR_STYLE.down
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '0.75rem',
      padding: '0.6rem 0.5rem', borderBottom: '1px solid var(--border)',
    }}>
      <span style={{
        padding: '0.15rem 0.4rem', borderRadius: '0.25rem', fontSize: '0.7rem', fontWeight: 700,
        background: d.bg, color: d.color,
      }}>
        {d.icon} {MAG_LABEL[s.magnitude] || s.magnitude}
      </span>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{s.sector}</div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{s.reason}</div>
      </div>
      {s.tickers?.length > 0 && (
        <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
          {s.tickers.map(t => (
            <span key={t} style={{
              padding: '0.1rem 0.4rem', background: 'var(--bg-secondary)',
              borderRadius: '0.25rem', fontSize: '0.65rem', fontWeight: 600,
            }}>{t}</span>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── Semiconductor Risk Tab ── */
function SemiTab({ data }) {
  const { semiconductor_risks, soxl_specific } = data
  const sevColor = { critical: '#ff1744', high: '#ff5252', medium: '#ff9800', low: '#ffeb3b' }

  return (
    <>
      {/* SOXL Specific */}
      {soxl_specific && (
        <div className="card" style={{ marginBottom: '1rem', borderLeft: '4px solid #ff1744', background: 'rgba(255,23,68,0.03)' }}>
          <h3>💹 SOXL 직접 영향</h3>
          <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', lineHeight: 1.8 }}>
            <p><b>요약:</b> {soxl_specific.impact_summary}</p>
            <p><b>핵심 레벨:</b> {soxl_specific.key_level}</p>
            <p><b>회복 조건:</b> {soxl_specific.recovery_condition}</p>
          </div>
        </div>
      )}

      {/* Semiconductor Risks */}
      <div className="card">
        <h3>⚠️ 반도체 공급망 리스크</h3>
        <div style={{ marginTop: '0.5rem' }}>
          {semiconductor_risks?.map((r, i) => (
            <div key={i} style={{
              display: 'flex', gap: '0.75rem', padding: '0.6rem 0',
              borderBottom: i < semiconductor_risks.length - 1 ? '1px solid var(--border)' : 'none',
            }}>
              <span style={{
                padding: '0.15rem 0.5rem', borderRadius: '0.25rem', fontSize: '0.7rem', fontWeight: 700,
                background: `${sevColor[r.severity]}20`, color: sevColor[r.severity],
                minWidth: '50px', textAlign: 'center', height: 'fit-content',
              }}>
                {r.severity.toUpperCase()}
              </span>
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{r.risk}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.1rem' }}>{r.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

/* ── Strategy Tab (Hedging + Precedents + Key Variables) ── */
function StrategyTab({ data }) {
  const { hedging_strategies, historical_precedents, key_variables } = data

  return (
    <>
      {/* Key Variables to Monitor */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3>🔍 핵심 모니터링 변수</h3>
        <div className="table-container" style={{ marginTop: '0.5rem' }}>
          <table className="table" style={{ width: '100%' }}>
            <thead>
              <tr><th>변수</th><th>현재</th><th style={{ color: 'var(--green)' }}>강세 시나리오</th><th style={{ color: 'var(--red)' }}>약세 시나리오</th></tr>
            </thead>
            <tbody>
              {key_variables?.map((v, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600 }}>{v.variable}</td>
                  <td>{v.current}</td>
                  <td style={{ color: 'var(--green)', fontSize: '0.8rem' }}>{v.bullish}</td>
                  <td style={{ color: 'var(--red)', fontSize: '0.8rem' }}>{v.bearish}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Hedging Strategies */}
      <div className="card" style={{ marginBottom: '1rem', borderLeft: '4px solid var(--accent)' }}>
        <h3>🛡️ 헤징 전략</h3>
        <div style={{ marginTop: '0.5rem' }}>
          {hedging_strategies?.map((h, i) => (
            <div key={i} style={{ padding: '0.5rem 0', borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontWeight: 700, fontSize: '0.85rem' }}>{h.strategy}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>{h.rationale}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Historical Precedents */}
      <div className="card">
        <h3>📚 역사적 선례</h3>
        <div style={{ marginTop: '0.5rem' }}>
          {historical_precedents?.map((h, i) => (
            <div key={i} style={{
              padding: '0.75rem', marginBottom: '0.5rem', background: 'var(--bg-secondary)',
              borderRadius: '0.5rem', borderLeft: '3px solid var(--accent)',
            }}>
              <div style={{ fontWeight: 700, marginBottom: '0.25rem' }}>{h.event}</div>
              <div style={{ display: 'flex', gap: '1rem', fontSize: '0.8rem' }}>
                <span>하락: <b style={{ color: 'var(--red)' }}>{h.market_decline}</b></span>
                <span>회복: <b style={{ color: 'var(--green)' }}>{h.recovery}</b></span>
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>핵심: {h.key_factor}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

/* ── Helpers ── */
function MiniCard({ label, value, color }) {
  return (
    <div className="card" style={{ textAlign: 'center', padding: '0.6rem 0.5rem' }}>
      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>{label}</div>
      <div style={{ fontSize: '1rem', fontWeight: 700, color: color || 'var(--text-primary)' }}>{value ?? '-'}</div>
    </div>
  )
}
