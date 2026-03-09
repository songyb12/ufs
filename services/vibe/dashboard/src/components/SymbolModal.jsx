import { useState, useEffect } from 'react'
import { getPriceChart, getSignalHistory } from '../api'
import {
  ComposedChart, Line, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'

export default function SymbolModal({ symbol, market, onClose }) {
  const [priceData, setPriceData] = useState([])
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [days, setDays] = useState(60)

  useEffect(() => {
    if (!symbol) return
    setLoading(true)
    Promise.all([
      getPriceChart(symbol, market, days),
      getSignalHistory(market, 90, symbol),
    ])
      .then(([priceRes, sigRes]) => {
        setPriceData(priceRes.data || [])
        setSignals(sigRes.signals || [])
        setError(null)
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [symbol, market, days])

  // ESC key handler
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  if (!symbol) return null

  const latest = priceData.length > 0 ? priceData[priceData.length - 1] : null
  const latestSignal = signals.length > 0 ? signals[0] : null

  const formatPrice = (v) => {
    if (v == null) return '-'
    return market === 'KR' ? v.toLocaleString() : v.toFixed(2)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 700 }}>
              {latestSignal?.name || symbol}
            </h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              {symbol} &middot; <span className={`badge badge-${market === 'KR' ? 'buy' : 'hold'}`}>{market}</span>
            </span>
          </div>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        {loading ? (
          <div className="loading"><span className="spinner" /> Loading...</div>
        ) : error ? (
          <div style={{ color: 'var(--red)', padding: '1rem' }}>Error: {error}</div>
        ) : (
          <>
            {/* Day selector */}
            <div className="filter-bar" style={{ marginBottom: '0.75rem' }}>
              {[30, 60, 120, 200].map(d => (
                <button
                  key={d}
                  className={`btn btn-sm ${days === d ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => setDays(d)}
                >
                  {d}D
                </button>
              ))}
            </div>

            {/* Price + Volume Chart */}
            {priceData.length > 0 && (
              <div style={{ marginBottom: '1.25rem' }}>
                <ResponsiveContainer width="100%" height={300}>
                  <ComposedChart data={priceData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis
                      dataKey="trade_date"
                      tick={{ fill: '#94a3b8', fontSize: 10 }}
                      tickFormatter={v => v?.slice(5)}
                    />
                    <YAxis
                      yAxisId="price"
                      domain={['auto', 'auto']}
                      tick={{ fill: '#94a3b8', fontSize: 10 }}
                      tickFormatter={v => v != null ? (market === 'KR' ? (v / 1000).toFixed(0) + 'k' : v.toFixed(0)) : ''}
                    />
                    <YAxis
                      yAxisId="volume"
                      orientation="right"
                      tick={{ fill: '#475569', fontSize: 9 }}
                      tickFormatter={v => v != null ? (v >= 1000000 ? `${(v / 1000000).toFixed(0)}M` : `${(v / 1000).toFixed(0)}K`) : ''}
                      domain={[0, dataMax => dataMax * 3]}
                    />
                    <Tooltip
                      contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.8rem' }}
                      formatter={(v, name) => {
                        if (name === 'volume') return [v >= 1000000 ? `${(v / 1000000).toFixed(1)}M` : `${(v / 1000).toFixed(0)}K`, '거래량']
                        return [formatPrice(v), name === 'close' ? '종가' : name === 'high' ? '고가' : name === 'low' ? '저가' : name]
                      }}
                      labelFormatter={(l) => l}
                    />
                    <Bar
                      yAxisId="volume"
                      dataKey="volume"
                      fill="rgba(59,130,246,0.15)"
                      radius={[1, 1, 0, 0]}
                    />
                    <Line
                      yAxisId="price"
                      type="monotone"
                      dataKey="close"
                      stroke="var(--accent)"
                      strokeWidth={2}
                      dot={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Key Indicators */}
            <div className="card-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: '1.25rem' }}>
              <div className="card" style={{ padding: '0.75rem' }}>
                <div className="card-label">Latest Close</div>
                <div className="card-value blue" style={{ fontSize: '1.25rem' }}>
                  {market === 'KR' ? '\u20A9' : '$'}{formatPrice(latest?.close)}
                </div>
                <div className="card-sub">{latest?.trade_date}</div>
              </div>
              <div className="card" style={{ padding: '0.75rem' }}>
                <div className="card-label">RSI</div>
                <div className={`card-value ${(latestSignal?.rsi_value || 0) > 65 ? 'red' : (latestSignal?.rsi_value || 0) > 50 ? 'yellow' : 'green'}`} style={{ fontSize: '1.25rem' }}>
                  {latestSignal?.rsi_value?.toFixed(1) || 'N/A'}
                </div>
              </div>
              <div className="card" style={{ padding: '0.75rem' }}>
                <div className="card-label">Volume</div>
                <div className="card-value blue" style={{ fontSize: '1.25rem' }}>
                  {latest?.volume ? (latest.volume >= 1000000 ? `${(latest.volume / 1000000).toFixed(1)}M` : `${(latest.volume / 1000).toFixed(0)}K`) : 'N/A'}
                </div>
              </div>
            </div>

            {/* Recent Signals Table */}
            {signals.length > 0 && (
              <div className="table-container" style={{ marginBottom: 0 }}>
                <div className="table-header">
                  <h3>Recent Signals</h3>
                  <span className="card-sub">{signals.length} signals</span>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Signal</th>
                      <th>Score</th>
                      <th>RSI</th>
                      <th>Rationale</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signals.slice(0, 10).map((s, i) => (
                      <tr key={`${s.signal_date}-${i}`}>
                        <td style={{ whiteSpace: 'nowrap' }}>{s.signal_date}</td>
                        <td>
                          <span className={`badge badge-${s.final_signal?.toLowerCase()}`}>
                            {s.final_signal}
                          </span>
                        </td>
                        <td style={{ color: s.raw_score > 0 ? 'var(--green)' : s.raw_score < 0 ? 'var(--red)' : '' }}>
                          {s.raw_score?.toFixed(1)}
                        </td>
                        <td>{s.rsi_value?.toFixed(1)}</td>
                        <td style={{ maxWidth: 200, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                          {s.explanation_rule || s.rationale?.slice(0, 60) || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {signals.length === 0 && (
              <div style={{ padding: '1rem', color: 'var(--text-muted)', textAlign: 'center' }}>
                No signal data for this symbol
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
