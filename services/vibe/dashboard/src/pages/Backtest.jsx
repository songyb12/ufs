import { useState, useEffect, useCallback } from 'react'
import { getBacktestResults, getBacktestDetail, triggerBacktest } from '../api'
import SymbolModal from '../components/SymbolModal'
import HelpButton from '../components/HelpButton'

export default function Backtest({ onNavigate }) {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedId, setExpandedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [triggerResult, setTriggerResult] = useState(null)
  const [selectedSymbol, setSelectedSymbol] = useState(null)

  const loadResults = useCallback(() => {
    setLoading(true)
    getBacktestResults(20)
      .then(data => { setResults(Array.isArray(data) ? data : []); setError(null) })
      .catch(err => { console.error(err); setError(err.message) })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadResults() }, [loadResults])

  const handleExpand = async (backtestId) => {
    if (expandedId === backtestId) {
      setExpandedId(null)
      setDetail(null)
      return
    }
    setExpandedId(backtestId)
    setDetailLoading(true)
    try {
      const d = await getBacktestDetail(backtestId)
      setDetail(d)
    } catch (err) {
      console.error(err)
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleTrigger = async (market) => {
    setTriggering(true)
    setTriggerResult(null)
    try {
      const r = await triggerBacktest({ market })
      setTriggerResult({ type: 'success', text: r.message || `${market} backtest started` })
      setTimeout(loadResults, 5000)
    } catch (err) {
      setTriggerResult({ type: 'error', text: `Failed: ${err.message}` })
    } finally {
      setTriggering(false)
    }
  }

  // Summary stats
  const completed = results.filter(r => r.status === 'completed')
  const bestHitRate = completed.length > 0
    ? Math.max(...completed.filter(r => r.hit_rate != null).map(r => r.hit_rate))
    : null
  const avgSharpe = completed.length > 0
    ? completed.filter(r => r.sharpe_ratio != null).reduce((sum, r) => sum + r.sharpe_ratio, 0) /
      Math.max(1, completed.filter(r => r.sharpe_ratio != null).length)
    : null

  if (loading) return <div className="loading"><span className="spinner" /> Loading...</div>
  if (error) return <div className="loading" style={{ color: 'var(--red)' }}>Error: {error}</div>

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'\uD83E\uDDEA'} Backtest</h2>
          <p className="subtitle">Backtest execution history and results</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className="btn btn-primary"
            onClick={() => handleTrigger('KR')}
            disabled={triggering}
          >
            {triggering ? '...' : 'Run KR'}
          </button>
          <button
            className="btn btn-primary"
            onClick={() => handleTrigger('US')}
            disabled={triggering}
          >
            {triggering ? '...' : 'Run US'}
          </button>
          <button className="btn btn-outline" onClick={loadResults}>
            {'\u21BB'} Refresh
          </button>
          <HelpButton section="backtest" onNavigate={onNavigate} />
        </div>
      </div>

      {/* Trigger Result */}
      {triggerResult && (
        <div className="card" style={{
          marginBottom: '1rem',
          borderColor: triggerResult.type === 'error' ? 'var(--red)' : 'var(--green)',
          padding: '0.75rem 1.25rem',
        }}>
          {triggerResult.type === 'error' ? '\u274C' : '\u2705'} {triggerResult.text}
        </div>
      )}

      {/* Summary Cards */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <div className="card">
          <div className="card-label">Total Runs</div>
          <div className="card-value blue">{results.length}</div>
          <div className="card-sub">{completed.length} completed</div>
        </div>
        <div className="card">
          <div className="card-label">Best Hit Rate</div>
          <div className={`card-value ${(bestHitRate || 0) >= 50 ? 'green' : 'yellow'}`}>
            {bestHitRate != null ? `${(bestHitRate * 100).toFixed(1)}%` : 'N/A'}
          </div>
        </div>
        <div className="card">
          <div className="card-label">Avg Sharpe</div>
          <div className={`card-value ${(avgSharpe || 0) >= 1 ? 'green' : 'yellow'}`}>
            {avgSharpe != null ? avgSharpe.toFixed(2) : 'N/A'}
          </div>
        </div>
      </div>

      {/* Results Table */}
      <div className="table-container">
        <div className="table-header">
          <h3>Backtest Results</h3>
          <span className="card-sub">{results.length} runs</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Market</th>
              <th>Period</th>
              <th>Status</th>
              <th>Trades</th>
              <th>Hit Rate</th>
              <th>Avg Return</th>
              <th>Sharpe</th>
              <th>Max DD</th>
            </tr>
          </thead>
          <tbody>
            {results.length === 0 && (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  No backtest runs yet. Click "Run KR" or "Run US" to start.
                </td>
              </tr>
            )}
            {results.map((r) => {
              const isExpanded = expandedId === r.backtest_id
              return (
                <tr key={r.backtest_id} style={{ cursor: 'pointer' }} onClick={() => handleExpand(r.backtest_id)}>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {r.backtest_id?.slice(0, 8)}...
                  </td>
                  <td>{r.market}</td>
                  <td style={{ whiteSpace: 'nowrap', fontSize: '0.75rem' }}>
                    {r.start_date} ~ {r.end_date}
                  </td>
                  <td>
                    <span className={`badge badge-${r.status}`}>{r.status}</span>
                  </td>
                  <td>{r.total_trades ?? '-'}</td>
                  <td style={{ color: (r.hit_rate || 0) >= 0.5 ? 'var(--green)' : 'var(--red)' }}>
                    {r.hit_rate != null ? `${(r.hit_rate * 100).toFixed(1)}%` : '-'}
                  </td>
                  <td style={{ color: (r.avg_return || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {r.avg_return != null ? `${(r.avg_return * 100).toFixed(2)}%` : '-'}
                  </td>
                  <td>{r.sharpe_ratio?.toFixed(2) ?? '-'}</td>
                  <td style={{ color: 'var(--red)' }}>
                    {r.max_drawdown != null ? `${(r.max_drawdown * 100).toFixed(1)}%` : '-'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Expanded Trade Detail */}
      {expandedId && (
        <div className="table-container">
          <div className="table-header">
            <h3>Trade Details — {expandedId.slice(0, 8)}...</h3>
            <button className="btn btn-outline btn-sm" onClick={() => { setExpandedId(null); setDetail(null) }}>
              Close
            </button>
          </div>
          {detailLoading ? (
            <div className="loading"><span className="spinner" /> Loading trades...</div>
          ) : detail?.trades?.length > 0 ? (
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Market</th>
                  <th>Entry</th>
                  <th>Entry Price</th>
                  <th>Exit</th>
                  <th>Exit Price</th>
                  <th>Return</th>
                  <th>Days</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {detail.trades.map((t, i) => (
                  <tr key={`trade-${i}`}>
                    <td
                      className="symbol-link"
                      onClick={(e) => { e.stopPropagation(); setSelectedSymbol({ symbol: t.symbol, market: t.market }) }}
                    >
                      <strong>{t.symbol}</strong>
                    </td>
                    <td>{t.market}</td>
                    <td style={{ whiteSpace: 'nowrap', fontSize: '0.75rem' }}>{t.entry_date}</td>
                    <td>{t.entry_price?.toLocaleString()}</td>
                    <td style={{ whiteSpace: 'nowrap', fontSize: '0.75rem' }}>{t.exit_date || '-'}</td>
                    <td>{t.exit_price?.toLocaleString() || '-'}</td>
                    <td style={{ color: (t.return_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                      {t.return_pct != null ? `${t.return_pct >= 0 ? '+' : ''}${t.return_pct.toFixed(2)}%` : '-'}
                    </td>
                    <td>{t.holding_days ?? '-'}</td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {t.exit_reason || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              No trade data available for this run.
            </div>
          )}
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
