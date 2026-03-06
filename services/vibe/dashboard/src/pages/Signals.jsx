import { useState, useEffect } from 'react'
import { getSignalHistory, getSignalPerformance, exportSignalsCSV } from '../api'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'
import SymbolModal from '../components/SymbolModal'
import HelpButton from '../components/HelpButton'

export default function Signals({ onNavigate }) {
  const [signals, setSignals] = useState([])
  const [perf, setPerf] = useState(null)
  const [market, setMarket] = useState('')
  const [days, setDays] = useState(30)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedSymbol, setSelectedSymbol] = useState(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      getSignalHistory(market || null, days),
      getSignalPerformance(market || null),
    ])
      .then(([h, p]) => { setSignals(h.signals || []); setPerf(p); setError(null) })
      .catch(err => { console.error(err); setError(err.message) })
      .finally(() => setLoading(false))
  }, [market, days])

  // Daily signal count chart data
  const dailyCounts = {}
  signals.forEach(s => {
    const d = s.signal_date
    if (!dailyCounts[d]) dailyCounts[d] = { date: d, BUY: 0, SELL: 0, HOLD: 0 }
    dailyCounts[d][s.final_signal] = (dailyCounts[d][s.final_signal] || 0) + 1
  })
  const chartData = Object.values(dailyCounts).sort((a, b) => a.date.localeCompare(b.date))

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'\u26A1'} Signals</h2>
          <p className="subtitle">Signal history and performance tracking</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button className="btn btn-outline" onClick={() => exportSignalsCSV(signals)}>
            {'\uD83D\uDCE5'} Export CSV
          </button>
          <HelpButton section="signals" onNavigate={onNavigate} />
        </div>
      </div>

      {/* Filters */}
      <div className="filter-bar">
        <select value={market} onChange={e => setMarket(e.target.value)}>
          <option value="">All Markets</option>
          <option value="KR">KR</option>
          <option value="US">US</option>
        </select>
        <select value={days} onChange={e => setDays(Number(e.target.value))}>
          <option value={7}>7 Days</option>
          <option value={14}>14 Days</option>
          <option value={30}>30 Days</option>
          <option value={90}>90 Days</option>
        </select>
      </div>

      {/* Performance Cards */}
      {perf && (
        <div className="card-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
          <div className="card">
            <div className="card-label">Total Signals</div>
            <div className="card-value blue">{perf.total_signals}</div>
          </div>
          <div className="card">
            <div className="card-label">BUY</div>
            <div className="card-value green">{perf.buy_signals}</div>
          </div>
          <div className="card">
            <div className="card-label">SELL</div>
            <div className="card-value red">{perf.sell_signals}</div>
          </div>
          <div className="card">
            <div className="card-label">Hit Rate T+5</div>
            <div className={`card-value ${(perf.hit_rate_t5 || 0) >= 50 ? 'green' : 'yellow'}`}>
              {perf.hit_rate_t5 != null ? `${perf.hit_rate_t5.toFixed(1)}%` : 'N/A'}
            </div>
          </div>
          <div className="card">
            <div className="card-label">Hit Rate T+20</div>
            <div className={`card-value ${(perf.hit_rate_t20 || 0) >= 50 ? 'green' : 'yellow'}`}>
              {perf.hit_rate_t20 != null ? `${perf.hit_rate_t20.toFixed(1)}%` : 'N/A'}
            </div>
          </div>
        </div>
      )}

      {/* Signal Trend Chart */}
      {chartData.length > 1 && (
        <div className="chart-container">
          <h3>{'\uD83D\uDCC8'} Daily Signal Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155' }} />
              <Line type="monotone" dataKey="BUY" stroke="#22c55e" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="SELL" stroke="#ef4444" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="HOLD" stroke="#eab308" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Signal Table */}
      {error && (
        <div className="card" style={{ marginBottom: '1rem', borderColor: 'var(--red)', padding: '0.75rem 1.25rem', color: 'var(--red)' }}>
          Error: {error}
        </div>
      )}
      {loading ? (
        <div className="loading"><span className="spinner" /> Loading...</div>
      ) : (
        <div className="table-container">
          <div className="table-header">
            <h3>Signal History</h3>
            <span className="card-sub">{signals.length} signals</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Symbol</th>
                <th>Market</th>
                <th>Signal</th>
                <th>Score</th>
                <th>RSI</th>
                <th>Tech Score</th>
                <th>Macro</th>
                <th>Hard Limit</th>
                <th>Explanation</th>
              </tr>
            </thead>
            <tbody>
              {signals.length === 0 ? (
                <tr>
                  <td colSpan={10} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    해당 기간에 시그널 데이터가 없습니다. 파이프라인을 먼저 실행하세요.
                  </td>
                </tr>
              ) : signals.map((s) => (
                <tr key={`${s.symbol}-${s.market}-${s.signal_date}`}>
                  <td style={{ whiteSpace: 'nowrap' }}>{s.signal_date}</td>
                  <td
                    className="symbol-link"
                    onClick={() => setSelectedSymbol({ symbol: s.symbol, market: s.market })}
                  >
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
                  <td style={{ color: s.raw_score > 0 ? 'var(--green)' : s.raw_score < 0 ? 'var(--red)' : '' }}>
                    {s.raw_score?.toFixed(1)}
                  </td>
                  <td>{s.rsi_value?.toFixed(1)}</td>
                  <td>{s.technical_score?.toFixed(1)}</td>
                  <td>{s.macro_score?.toFixed(1)}</td>
                  <td>
                    {s.hard_limit_triggered
                      ? <span className="badge badge-sell">{'\uD83D\uDED1'}</span>
                      : '-'
                    }
                  </td>
                  <td style={{ maxWidth: 250, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    {s.explanation_rule || s.rationale?.slice(0, 80) || '-'}
                  </td>
                </tr>
              ))}
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
