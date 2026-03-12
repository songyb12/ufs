import { useState, useEffect, useCallback, useRef } from 'react'
import { getBacktestResults, getBacktestDetail, triggerBacktest } from '../api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell, Legend
} from 'recharts'
import SymbolModal from '../components/SymbolModal'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import { useToast } from '../components/Toast'

export default function Backtest({ onNavigate, refreshKey }) {
  const toast = useToast()
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedId, setExpandedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [triggering, setTriggering] = useState(false)
  const [triggerResult, setTriggerResult] = useState(null)
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])

  const loadResults = useCallback(() => {
    setLoading(true)
    getBacktestResults(20)
      .then(data => { setResults(Array.isArray(data) ? data : []); setError(null) })
      .catch(err => { console.error(err); setError(err.message); toast.error('백테스트 로드 실패: ' + err.message) })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadResults() }, [loadResults, refreshKey])

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
      toast.error('상세 조회 실패: ' + err.message)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleTrigger = async (market) => {
    setTriggering(true)
    setTriggerResult(null)
    try {
      const body = { market }
      if (startDate) body.start_date = startDate
      if (endDate) body.end_date = endDate
      const r = await triggerBacktest(body)
      setTriggerResult({ type: 'success', text: r.message || `${market} backtest started (${startDate || 'default'} ~ ${endDate || 'today'})` })
      toast.success(`${market} 백테스트 시작됨`)
      setTimeout(() => { if (mountedRef.current) loadResults() }, 5000)
    } catch (err) {
      setTriggerResult({ type: 'error', text: `Failed: ${err.message}` })
      toast.error('백테스트 실행 실패: ' + err.message)
    } finally {
      setTriggering(false)
    }
  }

  const applyPreset = (name) => {
    const today = new Date().toISOString().slice(0, 10)
    switch (name) {
      case 'bear2022': setStartDate('2022-01-01'); setEndDate('2022-12-31'); break
      case 'covid2020': setStartDate('2020-01-01'); setEndDate('2020-12-31'); break
      case 'recovery': setStartDate('2023-01-01'); setEndDate('2024-12-31'); break
      case 'full': setStartDate('2020-01-01'); setEndDate(today); break
      case 'recent1y': setStartDate(''); setEndDate(''); break
      default: break
    }
  }

  // Summary stats
  const completed = results.filter(r => r.status === 'completed')
  const hitRates = completed.filter(r => r.hit_rate != null).map(r => r.hit_rate)
  const bestHitRate = hitRates.length > 0 ? Math.max(...hitRates) : null
  const avgSharpe = completed.length > 0
    ? completed.filter(r => r.sharpe_ratio != null).reduce((sum, r) => sum + r.sharpe_ratio, 0) /
      Math.max(1, completed.filter(r => r.sharpe_ratio != null).length)
    : null

  if (loading) return <div className="loading"><span className="spinner" /> 로딩 중...</div>
  if (error) return <div className="loading" style={{ color: 'var(--red)' }}>오류: {error}</div>

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'🧪'} 백테스트</h2>
          <p className="subtitle">백테스트 실행 이력 및 성과 분석</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
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
            {'↻'} Refresh
          </button>
          <HelpButton section="backtest" onNavigate={onNavigate} />
        </div>
      </div>

      <PageGuide
        pageId="backtest"
        title="백테스트 사용법"
        steps={[
          'KR/US 선택 후 Run → 과거 데이터로 전략 검증',
          '기간 프리셋(코로나, 베어마켓 등) 활용',
          '총 수익률·승률 확인 → 전략 신뢰도 판단',
          '개별 거래 확인 → 어떤 종목에서 손실/수익 발생?',
        ]}
        color="#a855f7"
      />

      {/* Date Range & Presets */}
      <div className="card" style={{ marginBottom: '1rem', padding: '0.75rem 1rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>기간 설정:</span>
          <input
            type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
            style={{ padding: '0.3rem 0.5rem', borderRadius: '0.25rem', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: '0.8rem' }}
          />
          <span style={{ color: 'var(--text-muted)' }}>~</span>
          <input
            type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
            style={{ padding: '0.3rem 0.5rem', borderRadius: '0.25rem', background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: '0.8rem' }}
          />
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{startDate || endDate ? `${startDate || 'default'} ~ ${endDate || 'today'}` : '기본: 최근 1년'}</span>
        </div>
        <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
          {[
            ['recent1y', '최근 1년 (기본)'],
            ['bear2022', '2022 하락장'],
            ['covid2020', '2020 코로나'],
            ['recovery', '2023-24 회복기'],
            ['full', '전체 (2020~)'],
          ].map(([key, label]) => (
            <button
              key={key}
              className="btn btn-outline btn-sm"
              onClick={() => applyPreset(key)}
              style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
            >
              {label}
            </button>
          ))}
        </div>
        {startDate && (
          <p style={{ fontSize: '0.7rem', color: '#eab308', marginTop: '0.4rem' }}>
            {'⚠'} DB에 해당 기간의 가격 데이터가 있어야 합니다. 데이터가 없으면 trade 0건으로 나옵니다.
          </p>
        )}
      </div>

      {/* Trigger Result */}
      {triggerResult && (
        <div className="card" style={{
          marginBottom: '1rem',
          borderColor: triggerResult.type === 'error' ? 'var(--red)' : 'var(--green)',
          padding: '0.75rem 1.25rem',
        }}>
          {triggerResult.type === 'error' ? '❌' : '✅'} {triggerResult.text}
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
          <div className={`card-value ${(bestHitRate || 0) >= 0.5 ? 'green' : 'yellow'}`}>
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

      {/* Performance Comparison Chart */}
      {completed.length >= 2 && (() => {
        const chartData = completed.slice(0, 8).map(r => ({
          label: `${r.market} ${r.start_date?.slice(0, 4)}${r.start_date !== r.end_date ? '-' + r.end_date?.slice(2, 4) : ''}`,
          hitRate: r.hit_rate != null ? +(r.hit_rate * 100).toFixed(1) : 0,
          sharpe: r.sharpe_ratio != null ? +r.sharpe_ratio.toFixed(2) : 0,
          totalReturn: r.total_return != null ? +r.total_return.toFixed(1) : 0,
          trades: r.total_trades || 0,
        }))
        return (
          <div className="table-container" style={{ marginBottom: '1.5rem' }}>
            <div className="table-header">
              <h3>📊 백테스트 성과 비교</h3>
              <span className="card-sub">{completed.length} completed runs</span>
            </div>
            <div style={{ padding: '0.5rem 0' }}>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis
                    type="number"
                    tick={{ fill: '#94a3b8', fontSize: 10 }}
                  />
                  <YAxis
                    type="category"
                    dataKey="label"
                    tick={{ fill: '#94a3b8', fontSize: 10 }}
                    width={80}
                  />
                  <Tooltip
                    contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.8rem' }}
                    formatter={(v, name) => {
                      if (name === 'hitRate') return [`${v}%`, '적중률']
                      if (name === 'sharpe') return [v, 'Sharpe']
                      if (name === 'totalReturn') return [`${v}%`, '총수익률']
                      return [v, name]
                    }}
                  />
                  <Legend
                    formatter={(val) => val === 'hitRate' ? '적중률(%)' : val === 'sharpe' ? 'Sharpe' : '총수익률(%)'}
                    wrapperStyle={{ fontSize: '0.75rem' }}
                  />
                  <Bar dataKey="hitRate" fill="#22c55e" radius={[0, 3, 3, 0]} barSize={10}>
                    {chartData.map((d, i) => (
                      <Cell key={i} fill={d.hitRate >= 50 ? '#22c55e' : '#ef4444'} />
                    ))}
                  </Bar>
                  <Bar dataKey="sharpe" fill="#3b82f6" radius={[0, 3, 3, 0]} barSize={10} />
                  <Bar dataKey="totalReturn" fill="#eab308" radius={[0, 3, 3, 0]} barSize={10}>
                    {chartData.map((d, i) => (
                      <Cell key={i} fill={d.totalReturn >= 0 ? '#eab308' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )
      })()}

      {/* Results Table */}
      <div className="table-container">
        <div className="table-header">
          <h3>Backtest Results</h3>
          <span className="card-sub">{results.length} runs</span>
        </div>
        <table>
          <thead>
            <tr>
              <th className="hide-on-mobile">ID</th>
              <th>Market</th>
              <th>Period</th>
              <th>Status</th>
              <th>Trades</th>
              <th>Hit Rate</th>
              <th className="hide-on-tablet">Avg Return</th>
              <th className="hide-on-tablet">Sharpe</th>
              <th className="hide-on-tablet">Max DD</th>
              <th className="hide-on-tablet">Total Return</th>
              <th className="hide-on-tablet">Profit Factor</th>
              <th className="hide-on-tablet">Config</th>
            </tr>
          </thead>
          <tbody>
            {results.length === 0 && (
              <tr>
                <td colSpan={12} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  No backtest runs yet. Click "Run KR" or "Run US" to start.
                </td>
              </tr>
            )}
            {results.map((r) => {
              return (
                <tr key={r.backtest_id} style={{ cursor: 'pointer', background: expandedId === r.backtest_id ? 'rgba(59,130,246,0.08)' : 'transparent' }} onClick={() => handleExpand(r.backtest_id)}>
                  <td className="hide-on-mobile" style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                    {r.backtest_id?.slice(0, 8)}...
                  </td>
                  <td>{r.market}</td>
                  <td style={{ whiteSpace: 'nowrap', fontSize: '0.75rem' }}>
                    {r.start_date} ~ {r.end_date}
                  </td>
                  <td>
                    <span className={`badge badge-${r.status}`}>{r.status}</span>
                  </td>
                  <td>
                    {r.total_trades ?? '-'}
                    {r.total_trades != null && r.total_trades < 10 && r.total_trades > 0 && (
                      <span style={{ fontSize: '0.6rem', color: '#eab308', marginLeft: '0.25rem' }} title="통계적 유의성 부족">{'⚠'}</span>
                    )}
                  </td>
                  <td style={{ color: (r.hit_rate || 0) >= 0.5 ? 'var(--green)' : 'var(--red)' }}>
                    {r.hit_rate != null ? `${(r.hit_rate * 100).toFixed(1)}%` : '-'}
                  </td>
                  <td className="hide-on-tablet" style={{ color: (r.avg_return || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {r.avg_return != null ? `${r.avg_return >= 0 ? '+' : ''}${r.avg_return.toFixed(2)}%` : '-'}
                  </td>
                  <td className="hide-on-tablet">{r.sharpe_ratio?.toFixed(2) ?? '-'}</td>
                  <td className="hide-on-tablet" style={{ color: r.max_drawdown != null ? 'var(--red)' : 'var(--text-muted)' }}>
                    {r.max_drawdown != null ? `-${r.max_drawdown.toFixed(1)}%` : '-'}
                  </td>
                  <td className="hide-on-tablet" style={{ color: (r.total_return || 0) >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                    {r.total_return != null ? `${r.total_return >= 0 ? '+' : ''}${r.total_return.toFixed(1)}%` : '-'}
                  </td>
                  <td className="hide-on-tablet" style={{ color: (r.profit_factor || 0) >= 1.5 ? 'var(--green)' : 'var(--yellow)' }}>
                    {r.profit_factor != null ? r.profit_factor.toFixed(2) : '-'}
                  </td>
                  <td className="hide-on-tablet" style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                    {r.config_snapshot ? (
                      <span title={`Stop Loss: ${r.config_snapshot.BACKTEST_STOP_LOSS_PCT}%, Hold: ${r.config_snapshot.BACKTEST_TRADE_EXIT_DAYS}d, RSI Limit: ${r.config_snapshot.RSI_HARD_LIMIT}`}>
                        SL:{r.config_snapshot.BACKTEST_STOP_LOSS_PCT}% / {r.config_snapshot.BACKTEST_TRADE_EXIT_DAYS}d / RSI{r.config_snapshot.RSI_HARD_LIMIT}
                      </span>
                    ) : '-'}
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

          {/* Config Snapshot */}
          {detail?.run?.config_snapshot && typeof detail.run.config_snapshot === 'object' && (
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: '0.75rem', padding: '1rem', marginBottom: '0.5rem',
              background: 'var(--bg-primary)', borderRadius: '0.5rem',
            }}>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                  {'📊'} Scoring Weights
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', lineHeight: 1.6 }}>
                  Tech: <strong>{((detail.run?.config_snapshot?.WEIGHT_TECHNICAL || 0) * 100).toFixed(0)}%</strong>
                  {' / '}Macro: <strong>{((detail.run?.config_snapshot?.WEIGHT_MACRO || 0) * 100).toFixed(0)}%</strong>
                  <br />
                  Fund: <strong>{((detail.run?.config_snapshot?.WEIGHT_FUND_FLOW || 0) * 100).toFixed(0)}%</strong>
                  {' / '}Funda: <strong>{((detail.run?.config_snapshot?.WEIGHT_FUNDAMENTAL || 0) * 100).toFixed(0)}%</strong>
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                  {'🛑'} Hard Limits
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', lineHeight: 1.6 }}>
                  RSI Limit: <strong>{detail.run?.config_snapshot?.RSI_HARD_LIMIT}</strong>
                  <br />
                  Disparity: <strong>{detail.run?.config_snapshot?.DISPARITY_HARD_LIMIT}%</strong>
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                  {'🛒'} Buy Threshold
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', lineHeight: 1.6 }}>
                  KR RSI: <strong>&gt; {detail.run?.config_snapshot?.RSI_BUY_THRESHOLD_KR}</strong>
                  <br />
                  US RSI: <strong>&gt; {detail.run?.config_snapshot?.RSI_BUY_THRESHOLD_US}</strong>
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                  {'⏱'} Trade Rules
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', lineHeight: 1.6 }}>
                  Hold: <strong>{detail.run?.config_snapshot?.BACKTEST_TRADE_EXIT_DAYS}{'일'}</strong>
                  <br />
                  Stop Loss: <strong style={{ color: 'var(--red)' }}>{detail.run?.config_snapshot?.BACKTEST_STOP_LOSS_PCT}%</strong>
                </div>
              </div>
            </div>
          )}

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
