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
  up: { bg: 'rgba(0,230,118,0.1)', color: '#00e676', icon: '\u2B06' },
  down: { bg: 'rgba(255,23,68,0.1)', color: '#ff1744', icon: '\u2B07' },
}

const MAG_LABEL = { very_high: '\uADF9\uC2EC', high: '\uAC15', medium: '\uC911', low: '\uC57D' }

export default function Geopolitical({ onNavigate, refreshKey }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  const toast = useToast()

  useEffect(() => {
    setLoading(true)
    getIranUsDashboard()
      .then(d => setData(d))
      .catch(err => toast.error('\uC9C0\uC815\uD559 \uB370\uC774\uD130 \uB85C\uB4DC \uC2E4\uD328: ' + err.message))
      .finally(() => setLoading(false))
  }, [refreshKey])

  if (loading) return <div className="loading">\u23F3 \uC9C0\uC815\uD559 \uB370\uC774\uD130 \uB85C\uB529...</div>
  if (!data) return <div className="loading">\u26A0 \uB370\uC774\uD130\uB97C \uBD88\uB7EC\uC62C \uC218 \uC5C6\uC2B5\uB2C8\uB2E4</div>

  const tabs = [
    { id: 'overview', label: '\uD0C0\uC784\uB77C\uC778' },
    { id: 'sectors', label: '\uC139\uD130 \uC601\uD5A5' },
    { id: 'semi', label: '\uBC18\uB3C4\uCCB4 \uB9AC\uC2A4\uD06C' },
    { id: 'strategy', label: '\uB300\uC751 \uC804\uB7B5' },
  ]

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div>
          <h2>\uD83C\uDF0D {data.event_name}</h2>
          <p style={{ color: 'var(--text-muted)', margin: '0.25rem 0 0' }}>
            \uC0C1\uD0DC: <span style={{ color: '#ff5252', fontWeight: 700 }}>{data.status}</span> &mdash;
            \uAC1C\uC804 {data.start_date} &middot; {data.days_elapsed}\uC77C\uCC28
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => onNavigate('soxl')}>
          \uD83D\uDCB9 SOXL \uD398\uC774\uC9C0 \u2192
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
          <MiniCard label="WTI \uC6D0\uC720" value={macro_snapshot.wti_crude ? `$${macro_snapshot.wti_crude.toFixed(1)}` : '-'} color="var(--red)" />
          <MiniCard label="\uAE08" value={macro_snapshot.gold ? `$${macro_snapshot.gold.toFixed(0)}` : '-'} color="#ffd700" />
          <MiniCard label="USD/KRW" value={macro_snapshot.usd_krw?.toFixed(0)} color="var(--text-primary)" />
          <MiniCard label="DXY" value={macro_snapshot.dxy?.toFixed(1)} color="var(--text-primary)" />
        </div>
      )}

      {/* Timeline */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3>\uD83D\uDCC5 \uBD84\uC7C1 \uD0C0\uC784\uB77C\uC778</h3>
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
        <h3>\uD83D\uDCC9 \uC8FC\uC694 \uC2DC\uC7A5 \uC601\uD5A5</h3>
        <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', marginTop: '0.75rem', gap: '0.75rem' }}>
          {market_impact && Object.entries(market_impact).map(([key, m]) => (
            <div key={key} style={{
              padding: '0.75rem', background: 'var(--bg-secondary)', borderRadius: '0.5rem',
              borderLeft: `3px solid ${m.change_pct?.startsWith('+') ? 'var(--green)' : 'var(--red)'}`,
            }}>
              <div style={{ fontWeight: 700, marginBottom: '0.25rem' }}>{m.title}</div>
              {m.before && <div style={{ fontSize: '0.75rem' }}>\uC804: {m.before} \u2192 \uD6C4: {m.after}</div>}
              {m.change_pct && <div style={{ fontWeight: 700, color: m.change_pct.startsWith('+') ? 'var(--green)' : 'var(--red)' }}>{m.change_pct}</div>}
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>{m.detail}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Live Price Charts */}
      {live_data && Object.keys(live_data).length > 0 && (
        <div className="card">
          <h3>\uD83D\uDCC8 \uC8FC\uC694 ETF \uCD94\uC774 (30\uC77C)</h3>
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
        <h3>\u2B06\uFE0F \uC218\uD61C \uC139\uD130</h3>
        <div style={{ marginTop: '0.5rem' }}>
          {winners.map((s, i) => <SectorRow key={i} s={s} />)}
        </div>
      </div>

      {/* Losers */}
      <div className="card" style={{ borderLeft: '4px solid var(--red)' }}>
        <h3>\u2B07\uFE0F \uD53C\uD574 \uC139\uD130</h3>
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
          <h3>\uD83D\uDCB9 SOXL \uC9C1\uC811 \uC601\uD5A5</h3>
          <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', lineHeight: 1.8 }}>
            <p><b>\uC694\uC57D:</b> {soxl_specific.impact_summary}</p>
            <p><b>\uD575\uC2EC \uB808\uBCA8:</b> {soxl_specific.key_level}</p>
            <p><b>\uD68C\uBCF5 \uC870\uAC74:</b> {soxl_specific.recovery_condition}</p>
          </div>
        </div>
      )}

      {/* Semiconductor Risks */}
      <div className="card">
        <h3>\u26A0\uFE0F \uBC18\uB3C4\uCCB4 \uACF5\uAE09\uB9DD \uB9AC\uC2A4\uD06C</h3>
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
        <h3>\uD83D\uDD0D \uD575\uC2EC \uBAA8\uB2C8\uD130\uB9C1 \uBCC0\uC218</h3>
        <div className="table-container" style={{ marginTop: '0.5rem' }}>
          <table className="table" style={{ width: '100%' }}>
            <thead>
              <tr><th>\uBCC0\uC218</th><th>\uD604\uC7AC</th><th style={{ color: 'var(--green)' }}>\uAC15\uC138 \uC2DC\uB098\uB9AC\uC624</th><th style={{ color: 'var(--red)' }}>\uC57D\uC138 \uC2DC\uB098\uB9AC\uC624</th></tr>
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
        <h3>\uD83D\uDEE1\uFE0F \uD5E4\uC9D5 \uC804\uB7B5</h3>
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
        <h3>\uD83D\uDCDA \uC5ED\uC0AC\uC801 \uC120\uB840</h3>
        <div style={{ marginTop: '0.5rem' }}>
          {historical_precedents?.map((h, i) => (
            <div key={i} style={{
              padding: '0.75rem', marginBottom: '0.5rem', background: 'var(--bg-secondary)',
              borderRadius: '0.5rem', borderLeft: '3px solid var(--accent)',
            }}>
              <div style={{ fontWeight: 700, marginBottom: '0.25rem' }}>{h.event}</div>
              <div style={{ display: 'flex', gap: '1rem', fontSize: '0.8rem' }}>
                <span>\uD558\uB77D: <b style={{ color: 'var(--red)' }}>{h.market_decline}</b></span>
                <span>\uD68C\uBCF5: <b style={{ color: 'var(--green)' }}>{h.recovery}</b></span>
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>\uD575\uC2EC: {h.key_factor}</div>
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
