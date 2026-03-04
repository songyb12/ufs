import { useState, useEffect } from 'react'
import { getSummary, getPortfolioScenarios } from '../api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from 'recharts'

export default function Portfolio() {
  const [summary, setSummary] = useState(null)
  const [scenarios, setScenarios] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getSummary(), getPortfolioScenarios()])
      .then(([s, sc]) => { setSummary(s); setScenarios(sc) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading"><span className="spinner" /> Loading...</div>

  const positions = summary?.portfolio?.positions || []
  const pnlPct = summary?.portfolio?.total_pnl_pct || 0

  // P&L chart data
  const pnlData = positions.map(p => ({
    name: p.name || p.symbol,
    pnl: p.pnl_pct,
    market: p.market,
  })).sort((a, b) => b.pnl - a.pnl)

  const held = scenarios?.held_scenarios || {}
  const entry = scenarios?.entry_scenarios || {}

  const formatKRW = (v) => {
    if (v >= 1000000) return `${(v / 10000).toFixed(0)}${'\uB9CC'}`
    return v?.toLocaleString() || '-'
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'\uD83D\uDCBC'} Portfolio</h2>
          <p className="subtitle">{positions.length} holdings</p>
        </div>
        <div className={`card-value ${pnlPct >= 0 ? 'green' : 'red'}`} style={{ fontSize: '1.5rem' }}>
          {pnlPct >= 0 ? '+' : ''}{pnlPct}% Total
        </div>
      </div>

      {/* P&L Bar Chart */}
      {pnlData.length > 0 && (
        <div className="chart-container">
          <h3>P&L by Position (%)</h3>
          <ResponsiveContainer width="100%" height={Math.max(200, pnlData.length * 32)}>
            <BarChart data={pnlData} layout="vertical" margin={{ left: 20 }}>
              <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }}
                tickFormatter={v => `${v > 0 ? '+' : ''}${v}%`} />
              <YAxis dataKey="name" type="category" width={100}
                tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155' }}
                formatter={v => [`${v.toFixed(2)}%`, 'P&L']}
              />
              <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
                {pnlData.map((entry, i) => (
                  <Cell key={i} fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Holdings Table */}
      <div className="table-container">
        <div className="table-header">
          <h3>Current Holdings</h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Market</th>
              <th>Entry Price</th>
              <th>Current</th>
              <th>P&L</th>
              <th>Size</th>
              <th>Scenario</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p, i) => {
              const sc = held[p.symbol]
              return (
                <tr key={i}>
                  <td>
                    <strong>{p.name || p.symbol}</strong>
                    <br />
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{p.symbol}</span>
                  </td>
                  <td>{p.market}</td>
                  <td>{p.market === 'KR' ? `\u20A9${p.entry_price?.toLocaleString()}` : `$${p.entry_price?.toFixed(2)}`}</td>
                  <td>{p.market === 'KR' ? `\u20A9${p.current_price?.toLocaleString()}` : `$${p.current_price?.toFixed(2)}`}</td>
                  <td>
                    <span style={{ color: p.pnl_pct >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                      {p.pnl_pct >= 0 ? '+' : ''}{p.pnl_pct}%
                    </span>
                  </td>
                  <td>{p.position_size}</td>
                  <td style={{ maxWidth: 250, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    {sc?.scenario_rule || '-'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Entry Opportunities */}
      {Object.keys(entry).length > 0 && (
        <div className="table-container">
          <div className="table-header">
            <h3>{'\uD83C\uDD95'} Entry Opportunities (BUY signals, not held)</h3>
          </div>
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Market</th>
                <th>Current Price</th>
                <th>Target</th>
                <th>Stop Loss</th>
                <th>R:R</th>
                <th>Scenario</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(entry).map(([sym, sc], i) => {
                let targets = {}
                try { targets = typeof sc.target_prices_json === 'string' ? JSON.parse(sc.target_prices_json) : (sc.target_prices_json || {}) } catch {}
                return (
                  <tr key={i}>
                    <td><strong>{sym}</strong></td>
                    <td>{sc.market}</td>
                    <td>{sc.current_price?.toLocaleString()}</td>
                    <td style={{ color: 'var(--green)' }}>{targets.target_10?.toLocaleString() || '-'}</td>
                    <td style={{ color: 'var(--red)' }}>{targets.stop_loss?.toLocaleString() || '-'}</td>
                    <td>{targets.rr_ratio?.toFixed(1) || '-'}</td>
                    <td style={{ maxWidth: 250, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {sc.scenario_rule || '-'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
