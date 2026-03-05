import { useState, useEffect } from 'react'
import { getSummary, getSignals } from '../api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie
} from 'recharts'

export default function Overview() {
  const [summary, setSummary] = useState(null)
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([getSummary(), getSignals()])
      .then(([s, sig]) => { setSummary(s); setSignals(sig); setError(null) })
      .catch(err => { console.error(err); setError(err.message) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading"><span className="spinner" /> Loading...</div>
  if (error) return <div className="loading" style={{ color: 'var(--red)' }}>Error: {error}</div>
  if (!summary) return <div className="loading">No data available</div>

  const { signals: sigCounts, portfolio, pipelines, data, hard_limit_count } = summary
  const totalSignals = (sigCounts.BUY || 0) + (sigCounts.SELL || 0) + (sigCounts.HOLD || 0)

  const pieData = [
    { name: 'BUY', value: sigCounts.BUY || 0, color: '#22c55e' },
    { name: 'SELL', value: sigCounts.SELL || 0, color: '#ef4444' },
    { name: 'HOLD', value: sigCounts.HOLD || 0, color: '#eab308' },
  ].filter(d => d.value > 0)

  // Top signals by score
  const topSignals = [...signals]
    .sort((a, b) => Math.abs(b.raw_score) - Math.abs(a.raw_score))
    .slice(0, 8)

  const barData = topSignals.map(s => ({
    name: s.name || s.symbol,
    score: s.raw_score,
    signal: s.final_signal,
  }))

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'\u2302'} Overview</h2>
          <p className="subtitle">
            Latest: {summary.latest_signal_date || 'N/A'}
          </p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="card-grid">
        <div className="card">
          <div className="card-label">BUY Signals</div>
          <div className="card-value green">{sigCounts.BUY || 0}</div>
          <div className="card-sub">out of {totalSignals} total</div>
        </div>
        <div className="card">
          <div className="card-label">SELL Signals</div>
          <div className="card-value red">{sigCounts.SELL || 0}</div>
          <div className="card-sub">out of {totalSignals} total</div>
        </div>
        <div className="card">
          <div className="card-label">Hard Limits</div>
          <div className="card-value yellow">{hard_limit_count}</div>
          <div className="card-sub">safety overrides</div>
        </div>
        <div className="card">
          <div className="card-label">Portfolio P&L</div>
          <div className={`card-value ${portfolio.total_pnl_pct >= 0 ? 'green' : 'red'}`}>
            {portfolio.total_pnl_pct >= 0 ? '+' : ''}{portfolio.total_pnl_pct}%
          </div>
          <div className="card-sub">{portfolio.holdings_count} holdings</div>
        </div>
        <div className="card">
          <div className="card-label">KR Pipeline</div>
          <div className="card-value blue" style={{ fontSize: '1rem' }}>
            <span className={`status-dot ${pipelines.KR.status === 'completed' ? 'green' : 'red'}`} />
            {pipelines.KR.status}
          </div>
          <div className="card-sub">{pipelines.KR.last_run ? new Date(pipelines.KR.last_run).toLocaleString('ko-KR') : 'never'}</div>
        </div>
        <div className="card">
          <div className="card-label">US Pipeline</div>
          <div className="card-value blue" style={{ fontSize: '1rem' }}>
            <span className={`status-dot ${pipelines.US.status === 'completed' ? 'green' : 'red'}`} />
            {pipelines.US.status}
          </div>
          <div className="card-sub">{pipelines.US.last_run ? new Date(pipelines.US.last_run).toLocaleString('ko-KR') : 'never'}</div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid-2">
        {/* Signal Distribution Pie */}
        <div className="chart-container">
          <h3>{'\uD83D\uDCC8'} Signal Distribution</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                dataKey="value"
                label={({ name, value }) => `${name}: ${value}`}
              >
                {pieData.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Top Signals Bar */}
        <div className="chart-container">
          <h3>{'\u26A1'} Top Signals by Score</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={barData} layout="vertical">
              <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis
                dataKey="name"
                type="category"
                width={80}
                tick={{ fill: '#94a3b8', fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155' }}
              />
              <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                {barData.map((entry) => (
                  <Cell
                    key={entry.name}
                    fill={entry.signal === 'BUY' ? '#22c55e' : entry.signal === 'SELL' ? '#ef4444' : '#eab308'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Latest Signals Table */}
      <div className="table-container">
        <div className="table-header">
          <h3>{'\u26A1'} Latest Signals</h3>
          <span className="card-sub">{signals.length} signals</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Market</th>
              <th>Signal</th>
              <th>Score</th>
              <th>RSI</th>
              <th>Hard Limit</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {signals.slice(0, 15).map((s) => (
              <tr key={`${s.symbol}-${s.market}-${s.signal_date}`}>
                <td>
                  <strong>{s.name || s.symbol}</strong>
                  <br />
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{s.symbol}</span>
                </td>
                <td>{s.market}</td>
                <td>
                  <span className={`badge badge-${s.final_signal?.toLowerCase()}`}>
                    {s.final_signal}
                  </span>
                </td>
                <td style={{ color: s.raw_score > 0 ? 'var(--green)' : s.raw_score < 0 ? 'var(--red)' : 'var(--text-secondary)' }}>
                  {s.raw_score?.toFixed(1)}
                </td>
                <td>{s.rsi_value?.toFixed(1)}</td>
                <td>
                  {s.hard_limit_triggered
                    ? <span className="badge badge-sell">YES</span>
                    : <span style={{ color: 'var(--text-muted)' }}>-</span>
                  }
                </td>
                <td>{s.confidence ? `${(s.confidence * 100).toFixed(0)}%` : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Data Stats */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <div className="card">
          <div className="card-label">Price Records</div>
          <div className="card-value blue">{data.prices.toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="card-label">Total Signals</div>
          <div className="card-value blue">{data.signals_total.toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="card-label">Watchlist</div>
          <div className="card-value blue">{data.watchlist}</div>
          <div className="card-sub">active symbols</div>
        </div>
      </div>
    </div>
  )
}
