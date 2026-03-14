import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import {
  ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ReferenceLine, Cell, Area,
} from 'recharts'
import {
  getSoxlLiveQuote, getSoxlIntraday, getSoxlLiveIndicators,
  getSoxlSectorCorrelation, getSoxlAlerts, createSoxlAlert, deleteSoxlAlert,
  getSoxlAiAnalysis, runSoxlBacktest, compareSoxlModes, generateSoxlStrategy,
  exportSoxlTradesCSV, getSoxlBacktestStats,
} from '../api'
import DataFreshness from '../components/DataFreshness'

// ── Helpers ──
const fmtPct = (v) => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
const fmtPrice = (v) => v == null ? '—' : `$${v.toFixed(2)}`
const fmtVol = (v) => {
  if (!v) return '—'
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`
  return v.toString()
}
const fmtTime = (ts) => {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
}

const rsiColor = (v) => {
  if (v == null) return '#94a3b8'
  if (v >= 70) return '#ef4444'
  if (v <= 30) return '#22c55e'
  return '#eab308'
}

const sessionColors = {
  '장중': '#22c55e',
  '프리마켓': '#eab308',
  '애프터마켓': '#f97316',
  '장마감': '#64748b',
  '주말': '#64748b',
}

// ── SSE + Polling Hook ──
function useSoxlLive(enabled) {
  const [quote, setQuote] = useState(null)
  const [connected, setConnected] = useState(false)
  const [lastReceivedAt, setLastReceivedAt] = useState(null)
  const esRef = useRef(null)
  const pollRef = useRef(null)

  useEffect(() => {
    if (!enabled) {
      // Disconnect but keep last quote
      if (esRef.current) {
        esRef.current.close()
        esRef.current = null
      }
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      setConnected(false)
      return
    }

    // Try SSE first
    const es = new EventSource('/soxl/live/stream')
    esRef.current = es

    es.addEventListener('price', (e) => {
      try {
        const data = JSON.parse(e.data)
        setQuote(data)
        setConnected(true)
        setLastReceivedAt(new Date())

        // Browser notification for alerts
        if (data.alerts?.length) {
          data.alerts.forEach(a => {
            if ('Notification' in window && Notification.permission === 'granted') {
              new Notification(`SOXL 알림: ${a.label || a.alert_type}`, {
                body: `$${a.current_price} — ${a.alert_type}: $${a.threshold}`,
                tag: `soxl-alert-${a.id}`,
              })
            }
          })
        }
      } catch { /* ignore parse errors */ }
    })

    es.onerror = () => {
      setConnected(false)
      // Fallback to polling
      if (!pollRef.current) {
        pollRef.current = setInterval(async () => {
          try {
            const q = await getSoxlLiveQuote()
            setQuote({ ...q, session: q.session || q.market_session, alerts: [] })
            setLastReceivedAt(new Date())
          } catch { /* silent */ }
        }, 15000)
      }
    }

    return () => {
      es.close()
      esRef.current = null
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [enabled])

  return { quote, connected, lastReceivedAt }
}

// ── Market Status Badge ──
function MarketBadge({ session }) {
  const color = sessionColors[session] || '#64748b'
  return (
    <span style={{
      fontSize: '0.65rem', fontWeight: 700, padding: '2px 8px', borderRadius: 9999,
      background: `${color}22`, color, border: `1px solid ${color}44`,
    }}>
      {session}
    </span>
  )
}

// ── Live Price Header ──
function LiveHeader({ quote, connected, sseEnabled, onToggleSSE, lastReceivedAt }) {
  const price = quote?.price || 0
  const change = quote?.change || 0
  const changePct = quote?.change_pct || 0
  const isUp = change >= 0

  const statusLabel = !sseEnabled ? 'PAUSED' : connected ? 'LIVE' : 'OFFLINE'
  const statusColor = !sseEnabled ? '#64748b' : connected ? '#22c55e' : '#ef4444'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
      padding: '16px 0', borderBottom: '1px solid var(--card-border)',
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <span style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)' }}>SOXL</span>
        <span style={{
          fontSize: '1.8rem', fontWeight: 700,
          color: isUp ? '#22c55e' : '#ef4444',
          transition: 'color 0.3s',
        }}>
          {fmtPrice(price)}
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{
          fontSize: '0.9rem', fontWeight: 600,
          color: isUp ? '#22c55e' : '#ef4444',
        }}>
          {isUp ? '▲' : '▼'} {fmtPct(changePct)}
        </span>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          ({isUp ? '+' : ''}{change?.toFixed(2) || '0.00'})
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto' }}>
        <MarketBadge session={quote?.session || '—'} />
        <span style={{
          width: 8, height: 8, borderRadius: '50%', background: statusColor,
          display: 'inline-block',
        }} />
        <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>
          {statusLabel}
        </span>
        <button
          onClick={onToggleSSE}
          style={{
            fontSize: '0.6rem', padding: '2px 8px', borderRadius: 4,
            background: sseEnabled ? '#64748b22' : '#22c55e22',
            color: sseEnabled ? '#94a3b8' : '#22c55e',
            border: `1px solid ${sseEnabled ? '#64748b44' : '#22c55e44'}`,
            cursor: 'pointer', fontWeight: 600,
          }}
        >
          {sseEnabled ? '⏸ 일시정지' : '▶ 재연결'}
        </button>
        {!sseEnabled && lastReceivedAt && (
          <DataFreshness updatedAt={lastReceivedAt} compact />
        )}
      </div>
    </div>
  )
}

// ── KPI Strip ──
function LiveKpiStrip({ indicators }) {
  if (!indicators) return null
  const items = [
    { label: 'RSI', value: indicators.rsi_14?.toFixed(1), color: rsiColor(indicators.rsi_14) },
    { label: 'MACD', value: indicators.macd?.toFixed(3), color: indicators.macd > 0 ? '#22c55e' : '#ef4444' },
    { label: 'VWAP', value: indicators.vwap ? fmtPrice(indicators.vwap) : '—', color: 'var(--text-primary)' },
    { label: 'BB상단', value: indicators.bb_upper ? fmtPrice(indicators.bb_upper) : '—', color: '#f97316' },
    { label: 'BB하단', value: indicators.bb_lower ? fmtPrice(indicators.bb_lower) : '—', color: '#3b82f6' },
    { label: 'MA5', value: indicators.ma_5 ? fmtPrice(indicators.ma_5) : '—', color: '#eab308' },
    { label: 'MA20', value: indicators.ma_20 ? fmtPrice(indicators.ma_20) : '—', color: '#22d3ee' },
  ]
  return (
    <div style={{
      display: 'flex', gap: 8, overflowX: 'auto', padding: '12px 0',
      borderBottom: '1px solid var(--card-border)',
    }}>
      {items.map(i => (
        <div key={i.label} className="card" style={{
          minWidth: 80, padding: '8px 12px', textAlign: 'center', flex: '0 0 auto',
        }}>
          <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginBottom: 2 }}>{i.label}</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: i.color }}>{i.value || '—'}</div>
        </div>
      ))}
    </div>
  )
}

// ── Intraday Chart ──
function IntradayChart({ candles, resolution, source }) {
  const data = useMemo(() => {
    if (!candles?.length) return []
    // Filter out incomplete candles (volume=0 at the end)
    const filtered = candles.filter((c, i) => i < candles.length - 1 || c.volume > 0)
    return filtered.map(c => ({
      time: fmtTime(c.time),
      open: c.open, high: c.high, low: c.low, close: c.close,
      volume: c.volume,
      bodyBottom: Math.min(c.open, c.close),
      bodyHeight: Math.abs(c.close - c.open),
      isGreen: c.close >= c.open,
      wickHigh: c.high - Math.max(c.open, c.close),
      wickLow: Math.min(c.open, c.close) - c.low,
    }))
  }, [candles])

  if (!data.length) {
    return (
      <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
        인트라데이 데이터 없음 (장 시간 외)
      </div>
    )
  }

  const minPrice = Math.min(...data.map(d => d.low)) * 0.998
  const maxPrice = Math.max(...data.map(d => d.high)) * 1.002

  return (
    <div className="card" style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <h3 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
          📊 인트라데이 차트 ({resolution}분봉)
        </h3>
        <span style={{ fontSize: '0.55rem', color: 'var(--text-muted)', padding: '2px 6px', borderRadius: 4, background: 'var(--bg-secondary)' }}>
          {data.length}개 · {source || 'live'}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={350}>
        <ComposedChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
          <XAxis dataKey="time" tick={{ fontSize: 10 }} interval={Math.floor(data.length / 8)} />
          <YAxis domain={[minPrice, maxPrice]} tick={{ fontSize: 10 }} tickFormatter={v => `$${v.toFixed(0)}`} />
          <Tooltip
            contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--card-border)', fontSize: 11 }}
            formatter={(v, name) => [typeof v === 'number' ? `$${v.toFixed(2)}` : v, name]}
          />
          <Line type="monotone" dataKey="close" stroke="#3b82f6" dot={false} strokeWidth={1.5} name="종가" />
          <Bar dataKey="volume" fill="#3b82f680" yAxisId="vol" opacity={0.3} />
          <YAxis yAxisId="vol" orientation="right" tick={false} width={0} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Sector Correlation ──
function SectorCorrelation({ sectorData }) {
  if (!sectorData) return null

  return (
    <div className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: 12, color: 'var(--text-primary)' }}>
        🔗 섹터 상관관계
      </h3>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>SOXL</span>
        <span style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
          {fmtPrice(sectorData.soxl?.price)}
        </span>
        <span style={{
          fontSize: '0.8rem', fontWeight: 600,
          color: (sectorData.soxl?.change_pct || 0) >= 0 ? '#22c55e' : '#ef4444',
        }}>
          {fmtPct(sectorData.soxl?.change_pct)}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 8 }}>
        {sectorData.etfs?.map(etf => {
          const isUp = (etf.change_pct || 0) >= 0
          const corrColor = etf.correlation == null ? '#64748b'
            : etf.correlation > 0.7 ? '#22c55e'
              : etf.correlation > 0.3 ? '#eab308'
                : '#ef4444'
          return (
            <div key={etf.symbol} className="card" style={{ padding: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontWeight: 700, fontSize: '0.8rem' }}>{etf.symbol}</span>
                {etf.correlation != null && (
                  <span style={{ fontSize: '0.6rem', color: corrColor, fontWeight: 700 }}>
                    ρ={etf.correlation.toFixed(2)}
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>{fmtPrice(etf.price)}</div>
              <div style={{ fontSize: '0.75rem', color: isUp ? '#22c55e' : '#ef4444' }}>
                {fmtPct(etf.change_pct)}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Alert Management ──
function AlertManager({ alerts, onRefresh }) {
  const [type, setType] = useState('price_above')
  const [threshold, setThreshold] = useState('')
  const [label, setLabel] = useState('')
  const [loading, setLoading] = useState(false)

  const handleCreate = async () => {
    if (!threshold) return
    setLoading(true)
    try {
      await createSoxlAlert({ alert_type: type, threshold: parseFloat(threshold), label })
      setThreshold('')
      setLabel('')
      onRefresh()
    } catch (e) {
      alert('알림 생성 실패: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await deleteSoxlAlert(id)
      onRefresh()
    } catch (e) {
      alert('삭제 실패: ' + e.message)
    }
  }

  const typeLabels = {
    price_above: '가격 이상 도달',
    price_below: '가격 이하 도달',
    change_pct: '등락률 초과',
  }

  return (
    <div className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: 12, color: 'var(--text-primary)' }}>
        🔔 가격 알림
      </h3>

      {/* Create form */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <select value={type} onChange={e => setType(e.target.value)}
          style={{ padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--card-border)', fontSize: '0.75rem' }}>
          <option value="price_above">가격 이상</option>
          <option value="price_below">가격 이하</option>
          <option value="change_pct">등락률 %</option>
        </select>
        <input type="number" step="0.01" placeholder="임계값" value={threshold}
          onChange={e => setThreshold(e.target.value)}
          style={{ width: 90, padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--card-border)', fontSize: '0.75rem' }} />
        <input type="text" placeholder="메모 (선택)" value={label}
          onChange={e => setLabel(e.target.value)}
          style={{ width: 120, padding: '6px 10px', borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--card-border)', fontSize: '0.75rem' }} />
        <button onClick={handleCreate} disabled={loading || !threshold}
          className="btn btn-primary" style={{ fontSize: '0.75rem', padding: '6px 14px' }}>
          {loading ? '...' : '알림 추가'}
        </button>
      </div>

      {/* Alert list */}
      {alerts?.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {alerts.map(a => (
            <div key={a.id} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '8px 12px', borderRadius: 8,
              background: a.active ? 'var(--bg-secondary)' : 'var(--bg-secondary)88',
              opacity: a.active ? 1 : 0.5,
              border: '1px solid var(--card-border)',
            }}>
              <div>
                <span style={{ fontSize: '0.7rem', color: 'var(--accent)', fontWeight: 700 }}>
                  {typeLabels[a.alert_type] || a.alert_type}
                </span>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, marginLeft: 8 }}>
                  ${a.threshold}
                </span>
                {a.label && <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginLeft: 8 }}>{a.label}</span>}
                {a.triggered_at && (
                  <span style={{ fontSize: '0.6rem', color: '#22c55e', marginLeft: 8 }}>✓ 발동</span>
                )}
              </div>
              <button onClick={() => handleDelete(a.id)}
                style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '0.8rem' }}>
                ✕
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center', padding: 20 }}>
          설정된 알림이 없습니다
        </div>
      )}
    </div>
  )
}

// ── AI Macro Analysis Component ──
function MacroAiAnalysis() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleAnalyze = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getSoxlAiAnalysis()
      if (data.status === 'error') {
        setError(data.message)
      } else {
        setResult(data)
      }
    } catch (e) {
      setError(e.message || 'AI 분석 요청 실패')
    }
    setLoading(false)
  }

  const snap = result?.context_snapshot || {}
  const signalColor = { BUY: '#22c55e', SELL: '#ef4444', HOLD: '#eab308', STRONG_BUY: '#00e676', STRONG_SELL: '#ff1744' }

  return (
    <div className="card" style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h3 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
          🤖 AI 매크로/지정학 종합 분석
        </h3>
        <button onClick={handleAnalyze} disabled={loading}
          className="btn btn-primary" style={{ fontSize: '0.75rem', padding: '6px 16px' }}>
          {loading ? '⏳ 분석 중...' : '🤖 AI 종합 분석 요청'}
        </button>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <div style={{ fontSize: '2rem', marginBottom: 12 }}>🔄</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            AI 분석 생성 중... (10~20초 소요)
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 4 }}>
            기술적 지표 + 매크로 + 지정학 데이터를 종합 분석합니다
          </div>
        </div>
      )}

      {error && (
        <div style={{
          padding: 16, borderRadius: 8, background: '#ef444420', border: '1px solid #ef4444',
          color: '#ef4444', fontSize: '0.8rem', marginBottom: 12,
        }}>
          ⚠️ {error}
        </div>
      )}

      {result && !loading && (
        <>
          {/* Context Snapshot KPIs */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
            gap: 8, marginBottom: 16,
          }}>
            {[
              { label: '현재가', value: snap.price ? `$${snap.price.toFixed(2)}` : '—', sub: snap.change_pct != null ? `${snap.change_pct >= 0 ? '+' : ''}${snap.change_pct.toFixed(2)}%` : '', color: snap.change_pct >= 0 ? '#22c55e' : '#ef4444' },
              { label: 'RSI-14', value: snap.rsi != null ? snap.rsi.toFixed(1) : '—', color: snap.rsi >= 70 ? '#ef4444' : snap.rsi <= 30 ? '#22c55e' : '#eab308' },
              { label: '시그널', value: snap.signal || '—', color: signalColor[snap.signal] || '#94a3b8' },
              { label: 'VIX', value: snap.vix != null ? snap.vix.toFixed(1) : '—', color: snap.vix >= 30 ? '#ef4444' : snap.vix >= 20 ? '#eab308' : '#22c55e' },
              { label: 'WTI', value: snap.oil != null ? `$${snap.oil.toFixed(0)}` : '—', color: snap.oil >= 100 ? '#ef4444' : '#94a3b8' },
              { label: 'Gold', value: snap.gold != null ? `$${snap.gold.toFixed(0)}` : '—' },
              { label: 'DXY', value: snap.dxy != null ? snap.dxy.toFixed(1) : '—' },
              { label: 'F&G', value: snap.fear_greed != null ? snap.fear_greed.toFixed(0) : '—', color: snap.fear_greed <= 25 ? '#ef4444' : snap.fear_greed >= 75 ? '#22c55e' : '#eab308' },
              { label: '지정학', value: `${snap.geo_events_count || 0}건` },
            ].map((kpi, i) => (
              <div key={i} style={{
                padding: '8px 10px', borderRadius: 8, background: 'var(--bg-secondary)',
                border: '1px solid var(--card-border)', textAlign: 'center',
              }}>
                <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginBottom: 2 }}>{kpi.label}</div>
                <div style={{ fontSize: '0.85rem', fontWeight: 700, color: kpi.color || 'var(--text-primary)' }}>
                  {kpi.value}
                </div>
                {kpi.sub && <div style={{ fontSize: '0.6rem', color: kpi.color }}>{kpi.sub}</div>}
              </div>
            ))}
          </div>

          {/* Correlations */}
          {snap.correlations && Object.keys(snap.correlations).length > 0 && (
            <div style={{
              display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap',
            }}>
              {Object.entries(snap.correlations).map(([sym, val]) => (
                <span key={sym} style={{
                  fontSize: '0.65rem', padding: '3px 8px', borderRadius: 4,
                  background: 'var(--bg-secondary)', border: '1px solid var(--card-border)',
                  color: val >= 0.7 ? '#22c55e' : val >= 0.4 ? '#eab308' : '#ef4444',
                }}>
                  vs {sym}: {val.toFixed(3)}
                </span>
              ))}
            </div>
          )}

          {/* AI Analysis Text */}
          <div style={{
            padding: 16, borderRadius: 8, background: 'var(--bg-secondary)',
            border: '1px solid var(--card-border)',
            fontSize: '0.8rem', lineHeight: 1.7, color: 'var(--text-primary)',
            whiteSpace: 'pre-wrap',
          }}>
            {result.analysis}
          </div>

          {/* Footer: model & timestamp */}
          <div style={{
            display: 'flex', justifyContent: 'space-between', marginTop: 10,
            fontSize: '0.6rem', color: 'var(--text-muted)',
          }}>
            <span>모델: {result.model}</span>
            <span>생성: {new Date(result.generated_at).toLocaleString('ko-KR')}</span>
          </div>
        </>
      )}

      {!result && !loading && !error && (
        <div style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
          <div style={{ fontSize: '1.5rem', marginBottom: 8 }}>📊</div>
          <div>기술적 지표, 매크로 환경, 지정학 리스크를 종합한 AI 분석을 생성합니다</div>
          <div style={{ fontSize: '0.7rem', marginTop: 6 }}>
            포함 데이터: RSI/MACD/BB · VIX/금리/유가 · 이란-미국 분쟁 · 반도체 리스크 · 섹터 상관
          </div>
        </div>
      )}
    </div>
  )
}

// ── SOXL Backtest Tab ──
const MODE_INFO = {
  A: { label: 'Technical Only', desc: 'RSI/MACD/BB/StochRSI/ADX 기술적 지표', color: '#3b82f6' },
  B: { label: 'Tech + Macro', desc: '+ VIX/금리/유가 매크로 게이팅', color: '#8b5cf6' },
  C: { label: 'Tech + Macro + Geo', desc: '+ 지정학 리스크 스코어', color: '#f59e0b' },
  D: { label: 'Full', desc: '+ 변동성 스케일링 + 레버리지 decay + 슬리피지', color: '#22c55e' },
}

const EXIT_LABELS = {
  stop_loss: '손절', take_profit: '익절', trailing_stop: '트레일링',
  rsi_exit: 'RSI 과매수', disparity_exit: '이격도', macd_dead_cross: 'MACD 데드크로스',
  time_exit: '보유 만기', geo_risk_exit: '지정학', backtest_end: '기간 종료',
  rsi_divergence: 'RSI 다이버전스', gap_down_exit: '갭 다운',
}

const DATE_PRESETS = [
  { label: '3개월', months: 3 },
  { label: '6개월', months: 6 },
  { label: '1년', months: 12 },
  { label: '2년', months: 24 },
  { label: '3년', months: 36 },
]

function SoxlBacktestTab() {
  const [mode, setMode] = useState('D')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [comparing, setComparing] = useState(false)
  const [result, setResult] = useState(null)
  const [compareResult, setCompareResult] = useState(null)
  const [error, setError] = useState(null)
  const [showExtended, setShowExtended] = useState(false)
  const [tradeFilter, setTradeFilter] = useState('all')
  const [sortCol, setSortCol] = useState(null)
  const [sortDir, setSortDir] = useState('asc')
  const abortRef = useRef(null)

  const applyPreset = (months) => {
    const end = new Date()
    const start = new Date()
    start.setMonth(start.getMonth() - months)
    setEndDate(end.toISOString().slice(0, 10))
    setStartDate(start.toISOString().slice(0, 10))
  }

  const handleRun = async () => {
    if (abortRef.current) abortRef.current.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setLoading(true); setError(null)
    try {
      const body = { mode }
      if (startDate) body.start_date = startDate
      if (endDate) body.end_date = endDate
      const data = await runSoxlBacktest(body, { signal: ctrl.signal })
      if (data.status === 'failed') setError(data.error)
      else setResult(data)
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message)
    }
    setLoading(false)
  }

  const handleCompare = async () => {
    if (abortRef.current) abortRef.current.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setComparing(true); setError(null)
    try {
      const body = {}
      if (startDate) body.start_date = startDate
      if (endDate) body.end_date = endDate
      const data = await compareSoxlModes(body, { signal: ctrl.signal })
      setCompareResult(data)
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message)
    }
    setComparing(false)
  }

  const handleExportCSV = () => {
    if (result?.trades?.length) {
      exportSoxlTradesCSV(result.trades, result.mode, result.period)
    }
  }

  const fmtPctSafe = (v) => v == null ? '—' : `${(v * 100).toFixed(1)}%`
  const fmtNum = (v, d = 2) => v == null ? '—' : v.toFixed(d)

  // Filtered and sorted trades
  const filteredTrades = useMemo(() => {
    if (!result?.trades) return []
    let trades = result.trades
    if (tradeFilter === 'wins') trades = trades.filter(t => (t.return_pct || 0) > 0)
    else if (tradeFilter === 'losses') trades = trades.filter(t => (t.return_pct || 0) <= 0)
    else if (tradeFilter !== 'all') trades = trades.filter(t => t.exit_reason === tradeFilter)

    if (sortCol) {
      trades = [...trades].sort((a, b) => {
        const va = a[sortCol] ?? 0
        const vb = b[sortCol] ?? 0
        return sortDir === 'asc' ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1)
      })
    }
    return trades
  }, [result?.trades, tradeFilter, sortCol, sortDir])

  const handleSort = (col) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('desc') }
  }

  return (
    <div className="card" style={{ padding: 16 }}>
      <h3 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: 12, color: 'var(--text-primary)' }}>
        🧪 SOXL 백테스트
      </h3>

      {/* Mode selector */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
        {Object.entries(MODE_INFO).map(([m, info]) => (
          <button key={m} onClick={() => setMode(m)}
            className={mode === m ? 'btn btn-primary' : 'btn btn-secondary'}
            style={{ fontSize: '0.65rem', padding: '5px 10px' }}
            title={info.desc}>
            {m}: {info.label}
          </button>
        ))}
      </div>

      {/* Date range selector with presets */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>기간:</label>
        <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
          style={{ fontSize: '0.7rem', padding: '4px 8px', borderRadius: 4, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--card-border)' }} />
        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>~</span>
        <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
          style={{ fontSize: '0.7rem', padding: '4px 8px', borderRadius: 4, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '1px solid var(--card-border)' }} />
      </div>
      <div style={{ display: 'flex', gap: 4, marginBottom: 12, flexWrap: 'wrap' }}>
        {DATE_PRESETS.map(p => (
          <button key={p.months} onClick={() => applyPreset(p.months)}
            className="btn btn-secondary"
            style={{ fontSize: '0.6rem', padding: '3px 8px' }}>
            {p.label}
          </button>
        ))}
        <button onClick={() => { setStartDate(''); setEndDate('') }}
          className="btn btn-secondary"
          style={{ fontSize: '0.6rem', padding: '3px 8px', color: 'var(--text-muted)' }}>
          초기화
        </button>
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <button onClick={handleRun} disabled={loading || comparing}
          className="btn btn-primary" style={{ fontSize: '0.75rem', padding: '6px 16px' }}>
          {loading ? '⏳ 실행 중...' : `🧪 모드 ${mode} 백테스트`}
        </button>
        <button onClick={handleCompare} disabled={loading || comparing}
          className="btn btn-secondary" style={{ fontSize: '0.75rem', padding: '6px 16px' }}>
          {comparing ? '⏳ 비교 중...' : '📊 4모드 비교'}
        </button>
        {(loading || comparing) && (
          <button onClick={() => abortRef.current?.abort()}
            style={{ fontSize: '0.65rem', padding: '4px 10px', background: '#ef444420', color: '#ef4444', border: '1px solid #ef4444', borderRadius: 4, cursor: 'pointer' }}>
            취소
          </button>
        )}
      </div>

      {error && (
        <div style={{ padding: 12, borderRadius: 8, background: '#ef444420', border: '1px solid #ef4444', color: '#ef4444', fontSize: '0.8rem', marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)} style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', fontSize: '0.9rem' }}>✕</button>
        </div>
      )}

      {/* Compare results */}
      {compareResult && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, marginBottom: 8, color: 'var(--text-primary)', display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
            📊 모드 비교 ({compareResult.period})
            {compareResult.best_mode && (
              <span style={{ padding: '2px 8px', borderRadius: 4, background: '#22c55e20', color: '#22c55e', fontSize: '0.65rem' }}>
                최고수익: 모드 {compareResult.best_mode}
              </span>
            )}
            {compareResult.best_risk_adjusted && compareResult.best_risk_adjusted !== compareResult.best_mode && (
              <span style={{ padding: '2px 8px', borderRadius: 4, background: '#3b82f620', color: '#3b82f6', fontSize: '0.65rem' }}>
                최적샤프: 모드 {compareResult.best_risk_adjusted}
              </span>
            )}
            {compareResult.best_sortino && compareResult.best_sortino !== compareResult.best_risk_adjusted && (
              <span style={{ padding: '2px 8px', borderRadius: 4, background: '#8b5cf620', color: '#8b5cf6', fontSize: '0.65rem' }}>
                Sortino: 모드 {compareResult.best_sortino}
              </span>
            )}
            {compareResult.benchmark_return != null && (
              <span style={{ padding: '2px 8px', borderRadius: 4, background: '#64748b20', color: '#64748b', fontSize: '0.65rem' }}>
                B&H: {compareResult.benchmark_return >= 0 ? '+' : ''}{compareResult.benchmark_return.toFixed(1)}%
              </span>
            )}
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', fontSize: '0.7rem', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--card-border)' }}>
                  {['모드', '거래수', '적중률', '총수익', 'Alpha', '샤프', 'Sortino', '최대DD', 'P.Factor', 'Decay'].map(h => (
                    <th key={h} style={{ padding: '6px 8px', textAlign: 'right', color: 'var(--text-muted)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {compareResult.comparison?.map(r => (
                  <tr key={r.mode} style={{
                    borderBottom: '1px solid var(--card-border)',
                    background: r.mode === compareResult.best_mode ? '#22c55e10' : 'transparent',
                  }}>
                    <td style={{ padding: '6px 8px', fontWeight: 700, color: MODE_INFO[r.mode]?.color }}>
                      {r.mode}: {r.mode_label}
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}>{r.trades_count}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}>{fmtPctSafe(r.metrics?.hit_rate)}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', color: (r.metrics?.total_return || 0) >= 0 ? '#22c55e' : '#ef4444' }}>
                      {fmtPctSafe(r.metrics?.total_return)}
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', color: (r.alpha_vs_benchmark || 0) >= 0 ? '#22c55e' : '#ef4444' }}>
                      {r.alpha_vs_benchmark != null ? `${r.alpha_vs_benchmark >= 0 ? '+' : ''}${r.alpha_vs_benchmark.toFixed(1)}%` : '—'}
                    </td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}>{fmtNum(r.metrics?.sharpe_ratio)}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}>{fmtNum(r.metrics?.sortino_ratio)}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', color: '#ef4444' }}>{fmtPctSafe(r.metrics?.max_drawdown)}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right' }}>{fmtNum(r.metrics?.profit_factor)}</td>
                    <td style={{ padding: '6px 8px', textAlign: 'right', color: '#f59e0b' }}>{fmtNum(r.leverage_decay_total, 1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Single run result */}
      {result && result.status === 'completed' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 700 }}>
              모드 {result.mode} 결과 ({result.period})
              {result.benchmark_return != null && (
                <span style={{ marginLeft: 8, fontSize: '0.65rem', color: '#64748b', fontWeight: 400 }}>
                  B&H: {result.benchmark_return >= 0 ? '+' : ''}{result.benchmark_return.toFixed(1)}%
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              <button onClick={() => setShowExtended(v => !v)}
                className="btn btn-secondary" style={{ fontSize: '0.6rem', padding: '3px 8px' }}>
                {showExtended ? '요약' : '상세'}
              </button>
              <button onClick={handleExportCSV}
                className="btn btn-secondary" style={{ fontSize: '0.6rem', padding: '3px 8px' }}>
                📥 CSV
              </button>
            </div>
          </div>

          {/* Metrics cards - basic */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(80px, 1fr))', gap: 6, marginBottom: 12 }}>
            {[
              { label: '거래수', value: result.metrics?.total_trades },
              { label: '적중률', value: fmtPctSafe(result.metrics?.hit_rate) },
              { label: '총수익', value: fmtPctSafe(result.metrics?.total_return), color: (result.metrics?.total_return || 0) >= 0 ? '#22c55e' : '#ef4444' },
              { label: '샤프', value: fmtNum(result.metrics?.sharpe_ratio) },
              { label: 'Sortino', value: fmtNum(result.metrics?.sortino_ratio) },
              { label: '최대DD', value: fmtPctSafe(result.metrics?.max_drawdown), color: '#ef4444' },
              { label: 'P.Factor', value: fmtNum(result.metrics?.profit_factor) },
              { label: 'Decay', value: `${fmtNum(result.leverage_decay_total, 1)}%`, color: '#f59e0b' },
              ...(showExtended ? [
                { label: 'CAGR', value: result.metrics?.cagr != null ? `${result.metrics.cagr.toFixed(1)}%` : '—' },
                { label: 'Calmar', value: fmtNum(result.metrics?.calmar_ratio) },
                { label: '평균승', value: result.metrics?.avg_win != null ? `+${result.metrics.avg_win.toFixed(1)}%` : '—', color: '#22c55e' },
                { label: '평균패', value: result.metrics?.avg_loss != null ? `-${result.metrics.avg_loss.toFixed(1)}%` : '—', color: '#ef4444' },
                { label: '기대값', value: result.metrics?.expectancy != null ? `${result.metrics.expectancy.toFixed(2)}%` : '—' },
                { label: '회수율', value: fmtNum(result.metrics?.recovery_factor) },
                { label: '연승', value: result.metrics?.max_consecutive_wins || 0, color: '#22c55e' },
                { label: '연패', value: result.metrics?.max_consecutive_losses || 0, color: '#ef4444' },
                { label: '중간값', value: result.metrics?.median_return != null ? `${result.metrics.median_return.toFixed(1)}%` : '—' },
                { label: '최고', value: result.metrics?.best_trade != null ? `+${result.metrics.best_trade.toFixed(1)}%` : '—', color: '#22c55e' },
                { label: '최악', value: result.metrics?.worst_trade != null ? `${result.metrics.worst_trade.toFixed(1)}%` : '—', color: '#ef4444' },
                { label: 'Ulcer', value: fmtNum(result.metrics?.ulcer_index) },
                { label: '평균보유', value: result.metrics?.avg_holding_days != null ? `${result.metrics.avg_holding_days.toFixed(0)}일` : '—' },
              ] : []),
            ].map((m, i) => (
              <div key={i} style={{ padding: '5px 6px', borderRadius: 6, background: 'var(--bg-secondary)', border: '1px solid var(--card-border)', textAlign: 'center' }}>
                <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>{m.label}</div>
                <div style={{ fontSize: '0.75rem', fontWeight: 700, color: m.color || 'var(--text-primary)' }}>{m.value}</div>
              </div>
            ))}
          </div>

          {/* Exit reason stats */}
          {showExtended && result.exit_reason_stats?.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>퇴출 사유별 통계</div>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {result.exit_reason_stats.map((s, i) => (
                  <span key={i} style={{
                    fontSize: '0.6rem', padding: '3px 8px', borderRadius: 4,
                    background: 'var(--bg-secondary)', border: '1px solid var(--card-border)',
                    color: s.avg_return >= 0 ? '#22c55e' : '#ef4444',
                  }}>
                    {EXIT_LABELS[s.reason] || s.reason}: {s.count}건
                    ({(s.win_rate * 100).toFixed(0)}% 승)
                    avg {s.avg_return >= 0 ? '+' : ''}{s.avg_return.toFixed(1)}%
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Monthly returns heatmap */}
          {showExtended && result.monthly_returns?.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>월별 수익률</div>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {result.monthly_returns.map((m, i) => (
                  <div key={i} style={{
                    padding: '4px 6px', borderRadius: 4, textAlign: 'center', minWidth: 60,
                    background: m.return_pct >= 5 ? '#22c55e30' : m.return_pct >= 0 ? '#22c55e15' : m.return_pct >= -5 ? '#ef444415' : '#ef444430',
                    border: '1px solid var(--card-border)',
                  }}>
                    <div style={{ fontSize: '0.5rem', color: 'var(--text-muted)' }}>{m.month.slice(2)}</div>
                    <div style={{ fontSize: '0.65rem', fontWeight: 700, color: m.return_pct >= 0 ? '#22c55e' : '#ef4444' }}>
                      {m.return_pct >= 0 ? '+' : ''}{m.return_pct.toFixed(1)}%
                    </div>
                    <div style={{ fontSize: '0.45rem', color: 'var(--text-muted)' }}>{m.trade_count}건</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Equity curve */}
          {result.equity_curve?.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>
                에퀴티 커브
                {result.benchmark_return != null && <span style={{ marginLeft: 8, fontSize: '0.6rem' }}>($100 시작)</span>}
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <ComposedChart data={result.equity_curve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--card-border)" />
                  <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={d => d.slice(5)}
                    interval={Math.max(1, Math.floor(result.equity_curve.length / 10))} />
                  <YAxis tick={{ fontSize: 9 }} domain={['auto', 'auto']} tickFormatter={v => `$${v}`} />
                  <Tooltip
                    contentStyle={{ fontSize: '0.7rem', background: 'var(--bg-primary)', border: '1px solid var(--card-border)' }}
                    formatter={(v) => [`$${v}`, '에퀴티']}
                    labelFormatter={l => `날짜: ${l}`} />
                  <Area type="monotone" dataKey="equity" fill="#22c55e10" stroke="#22c55e" strokeWidth={2} />
                  <ReferenceLine y={100} stroke="#64748b" strokeDasharray="3 3" label={{ value: '기준', fontSize: 9, fill: '#64748b' }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Drawdown periods */}
          {showExtended && result.drawdown_periods?.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>드로다운 기간 (Top 5)</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {result.drawdown_periods.map((dd, i) => (
                  <div key={i} style={{
                    padding: '4px 8px', borderRadius: 4, fontSize: '0.6rem',
                    background: '#ef444415', border: '1px solid #ef444444',
                  }}>
                    <span style={{ color: '#ef4444', fontWeight: 700 }}>-{dd.depth_pct.toFixed(1)}%</span>
                    <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>
                      {dd.start_date?.slice(5)} ~ {dd.end_date?.slice(5)} ({dd.duration_trades}건)
                    </span>
                    {dd.recovered && <span style={{ color: '#22c55e', marginLeft: 4 }}>✓회복</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Trade list */}
          {result.trades?.length > 0 && (
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 4 }}>
                <span>
                  트레이드 ({filteredTrades.length}/{result.trades.length}건)
                  <span style={{ marginLeft: 8, color: '#22c55e' }}>
                    승: {result.trades.filter(t => (t.return_pct || 0) > 0).length}
                  </span>
                  <span style={{ marginLeft: 4, color: '#ef4444' }}>
                    패: {result.trades.filter(t => (t.return_pct || 0) <= 0).length}
                  </span>
                </span>
                <div style={{ display: 'flex', gap: 3 }}>
                  {[
                    { key: 'all', label: '전체' },
                    { key: 'wins', label: '승' },
                    { key: 'losses', label: '패' },
                    ...Object.entries(EXIT_LABELS).map(([k, v]) => ({ key: k, label: v })),
                  ].map(f => (
                    <button key={f.key} onClick={() => setTradeFilter(f.key)}
                      style={{
                        fontSize: '0.55rem', padding: '2px 6px', borderRadius: 3, cursor: 'pointer',
                        background: tradeFilter === f.key ? 'var(--accent)' : 'var(--bg-secondary)',
                        color: tradeFilter === f.key ? '#fff' : 'var(--text-muted)',
                        border: '1px solid var(--card-border)',
                      }}>
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>
              <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                <table style={{ width: '100%', fontSize: '0.65rem', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--card-border)', position: 'sticky', top: 0, background: 'var(--bg-primary)', zIndex: 1 }}>
                      {[
                        { key: 'entry_date', label: '진입일' },
                        { key: 'entry_rsi', label: 'RSI' },
                        { key: 'entry_vix', label: 'VIX' },
                        { key: 'entry_geo_score', label: 'Geo' },
                        { key: 'exit_date', label: '퇴출일' },
                        { key: 'exit_reason', label: '사유' },
                        { key: 'return_pct', label: '수익' },
                        { key: 'return_pct_with_decay', label: 'w/Decay' },
                        { key: 'holding_days', label: '일수' },
                        { key: 'position_size_mult', label: '배율' },
                      ].map(h => (
                        <th key={h.key} onClick={() => handleSort(h.key)}
                          style={{ padding: '4px 6px', textAlign: 'right', color: 'var(--text-muted)', cursor: 'pointer', userSelect: 'none' }}>
                          {h.label}{sortCol === h.key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTrades.map((t, i) => (
                      <tr key={i} style={{
                        borderBottom: '1px solid var(--card-border)',
                        background: (t.return_pct || 0) > 0 ? '#22c55e08' : (t.return_pct || 0) < 0 ? '#ef444408' : 'transparent',
                      }}>
                        <td style={{ padding: '4px 6px' }}>{t.entry_date?.slice(5)}</td>
                        <td style={{ padding: '4px 6px', textAlign: 'right', color: rsiColor(t.entry_rsi) }}>{t.entry_rsi || '—'}</td>
                        <td style={{ padding: '4px 6px', textAlign: 'right' }}>{t.entry_vix || '—'}</td>
                        <td style={{ padding: '4px 6px', textAlign: 'right' }}>{t.entry_geo_score || '—'}</td>
                        <td style={{ padding: '4px 6px' }}>{t.exit_date?.slice(5)}</td>
                        <td style={{ padding: '4px 6px', fontSize: '0.6rem' }}>
                          {EXIT_LABELS[t.exit_reason] || t.exit_reason}
                        </td>
                        <td style={{ padding: '4px 6px', textAlign: 'right', fontWeight: 600, color: (t.return_pct || 0) >= 0 ? '#22c55e' : '#ef4444' }}>
                          {t.return_pct?.toFixed(1)}%
                        </td>
                        <td style={{ padding: '4px 6px', textAlign: 'right', color: (t.return_pct_with_decay || 0) >= 0 ? '#22c55e' : '#ef4444' }}>
                          {t.return_pct_with_decay?.toFixed(1)}%
                        </td>
                        <td style={{ padding: '4px 6px', textAlign: 'right' }}>{t.holding_days}</td>
                        <td style={{ padding: '4px 6px', textAlign: 'right', color: 'var(--text-muted)' }}>×{t.position_size_mult || 1}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {!result && !compareResult && !loading && !comparing && !error && (
        <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-muted)', fontSize: '0.75rem' }}>
          <div style={{ fontSize: '1.2rem', marginBottom: 8 }}>🧪</div>
          <div>SOXL 전용 백테스트를 실행합니다</div>
          <div style={{ fontSize: '0.65rem', marginTop: 4 }}>
            4가지 전략 모드: A(기술적) → B(+매크로) → C(+지정학) → D(풀+레버리지 decay)
          </div>
          <div style={{ fontSize: '0.6rem', marginTop: 4, color: 'var(--text-muted)' }}>
            지표: RSI/MACD/BB/StochRSI/ADX/OBV · 트레일링 스탑 · 쿨다운 · VIX 단계별 · BB 스퀴즈 · ATR 스탑 · Kelly 사이징
          </div>
        </div>
      )}
    </div>
  )
}

// ── AI Strategy Tab ──
function SoxlAiStrategyTab() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showRaw, setShowRaw] = useState(false)
  const [copied, setCopied] = useState(false)
  const abortRef = useRef(null)

  const handleGenerate = async () => {
    if (abortRef.current) abortRef.current.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setLoading(true); setError(null)
    try {
      const data = await generateSoxlStrategy({}, { signal: ctrl.signal })
      if (data.status === 'error') setError(data.message)
      else setResult(data)
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message)
    }
    setLoading(false)
  }

  const handleCopy = () => {
    if (result?.strategy) {
      navigator.clipboard.writeText(result.strategy).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
    }
  }

  const signalColor = { BUY: '#22c55e', SELL: '#ef4444', HOLD: '#eab308', STRONG_BUY: '#00e676', STRONG_SELL: '#ff1744' }
  const ctx = result?.current_context || {}

  return (
    <div className="card" style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
          🎯 AI 최적 전략 생성
        </h3>
        <div style={{ display: 'flex', gap: 4 }}>
          {loading && (
            <button onClick={() => abortRef.current?.abort()}
              style={{ fontSize: '0.65rem', padding: '4px 10px', background: '#ef444420', color: '#ef4444', border: '1px solid #ef4444', borderRadius: 4, cursor: 'pointer' }}>
              취소
            </button>
          )}
          <button onClick={handleGenerate} disabled={loading}
            className="btn btn-primary" style={{ fontSize: '0.75rem', padding: '6px 16px' }}>
            {loading ? '⏳ 생성 중...' : '🎯 전략 생성'}
          </button>
        </div>
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <div style={{ fontSize: '2rem', marginBottom: 12 }}>🤖</div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            AI 전략 생성 중... (15~30초)
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 4 }}>
            백테스트 결과 + 현재 시장 + 지정학 리스크 + 52주 위치를 종합 분석합니다
          </div>
        </div>
      )}

      {error && (
        <div style={{ padding: 12, borderRadius: 8, background: '#ef444420', border: '1px solid #ef4444', color: '#ef4444', fontSize: '0.8rem', marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>⚠️ {error}</span>
          <button onClick={handleGenerate} style={{ background: '#ef4444', color: '#fff', border: 'none', borderRadius: 4, padding: '3px 10px', cursor: 'pointer', fontSize: '0.65rem' }}>
            재시도
          </button>
        </div>
      )}

      {result && !loading && (
        <>
          {/* Backtest summary badges */}
          {result.backtest_summary?.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>참조 백테스트</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {result.backtest_summary.map((bt, i) => (
                  <span key={i} style={{
                    fontSize: '0.6rem', padding: '3px 8px', borderRadius: 4,
                    background: 'var(--bg-secondary)', border: '1px solid var(--card-border)',
                    color: MODE_INFO[bt.mode]?.color || 'var(--text-primary)',
                  }}>
                    모드{bt.mode}: {bt.hit_rate != null ? `${(bt.hit_rate * 100).toFixed(0)}%` : '—'} 적중
                    / {bt.total_return != null ? `${(bt.total_return * 100).toFixed(0)}%` : '—'} 수익
                    {bt.decay > 0 ? ` / Decay ${bt.decay.toFixed(1)}%` : ''}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Win/Loss streak info */}
          {result.trade_streaks && (result.trade_streaks.max_consecutive_wins > 0 || result.trade_streaks.max_consecutive_losses > 0) && (
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <span style={{ fontSize: '0.6rem', padding: '2px 8px', borderRadius: 4, background: '#22c55e15', color: '#22c55e' }}>
                최대 연승: {result.trade_streaks.max_consecutive_wins}회
              </span>
              <span style={{ fontSize: '0.6rem', padding: '2px 8px', borderRadius: 4, background: '#ef444415', color: '#ef4444' }}>
                최대 연패: {result.trade_streaks.max_consecutive_losses}회
              </span>
            </div>
          )}

          {/* Current context snapshot */}
          {ctx && (
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(75px, 1fr))',
              gap: 5, marginBottom: 12,
            }}>
              {[
                { label: '현재가', value: ctx.price ? `$${ctx.price.toFixed(2)}` : '—' },
                { label: '1일 변동', value: ctx.price_1d_change != null ? `${ctx.price_1d_change >= 0 ? '+' : ''}${ctx.price_1d_change.toFixed(1)}%` : '—',
                  color: (ctx.price_1d_change || 0) >= 0 ? '#22c55e' : '#ef4444' },
                { label: '52주 위치', value: ctx.pct_from_52w_high != null ? `${ctx.pct_from_52w_high.toFixed(0)}%` : '—',
                  color: (ctx.pct_from_52w_high || 0) >= -10 ? '#22c55e' : (ctx.pct_from_52w_high || 0) >= -30 ? '#eab308' : '#ef4444' },
                { label: 'VIX', value: ctx.macro?.vix?.toFixed(1) || '—',
                  color: (ctx.macro?.vix || 0) >= 30 ? '#ef4444' : (ctx.macro?.vix || 0) >= 20 ? '#eab308' : '#22c55e' },
                { label: 'WTI', value: ctx.macro?.wti ? `$${ctx.macro.wti.toFixed(0)}` : '—' },
                { label: 'Gold', value: ctx.macro?.gold ? `$${ctx.macro.gold.toFixed(0)}` : '—' },
                { label: 'DXY', value: ctx.macro?.dxy?.toFixed(1) || '—' },
                { label: 'F&G', value: ctx.macro?.fear_greed?.toFixed(0) || '—',
                  color: (ctx.macro?.fear_greed || 50) <= 25 ? '#ef4444' : (ctx.macro?.fear_greed || 50) >= 75 ? '#22c55e' : '#eab308' },
                { label: '시그널', value: ctx.signal?.signal || '—',
                  color: signalColor[ctx.signal?.signal] || '#94a3b8' },
                { label: '지정학', value: `${ctx.geo_events?.length || 0}건` },
              ].map((kpi, i) => (
                <div key={i} style={{
                  padding: '4px 6px', borderRadius: 4, textAlign: 'center',
                  background: 'var(--bg-secondary)', border: '1px solid var(--card-border)',
                }}>
                  <div style={{ fontSize: '0.5rem', color: 'var(--text-muted)' }}>{kpi.label}</div>
                  <div style={{ fontSize: '0.7rem', fontWeight: 700, color: kpi.color || 'var(--text-primary)' }}>{kpi.value}</div>
                </div>
              ))}
            </div>
          )}

          {/* Strategy text */}
          <div style={{
            padding: 16, borderRadius: 8, background: 'var(--bg-secondary)',
            border: '1px solid var(--card-border)',
            fontSize: '0.8rem', lineHeight: 1.7, color: 'var(--text-primary)',
            whiteSpace: 'pre-wrap',
            maxHeight: showRaw ? 'none' : 600, overflowY: showRaw ? 'visible' : 'auto',
          }}>
            {result.strategy}
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, fontSize: '0.6rem', color: 'var(--text-muted)', flexWrap: 'wrap', gap: 4 }}>
            <div>
              <span>모델: {result.model}</span>
              <span style={{ marginLeft: 12 }}>생성: {new Date(result.generated_at).toLocaleString('ko-KR')}</span>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button onClick={handleCopy}
                style={{ background: 'transparent', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: '0.6rem' }}>
                {copied ? '✓ 복사됨' : '📋 복사'}
              </button>
              <button onClick={() => setShowRaw(!showRaw)}
                style={{ background: 'transparent', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: '0.6rem' }}>
                {showRaw ? '접기' : '전체 보기'}
              </button>
            </div>
          </div>
        </>
      )}

      {!result && !loading && !error && (
        <div style={{ textAlign: 'center', padding: 30, color: 'var(--text-muted)', fontSize: '0.8rem' }}>
          <div style={{ fontSize: '1.5rem', marginBottom: 8 }}>🎯</div>
          <div>백테스트 결과 + 현재 시장 데이터를 종합하여</div>
          <div>AI가 최적 SOXL 트레이딩 전략을 생성합니다</div>
          <div style={{ fontSize: '0.65rem', marginTop: 8, color: 'var(--text-muted)' }}>
            💡 먼저 "백테스트" 탭에서 4모드 비교를 실행하면 더 정확한 전략이 생성됩니다
          </div>
          <div style={{ fontSize: '0.6rem', marginTop: 4, color: 'var(--text-muted)' }}>
            포함: 진입/퇴출 조건 · 포지션 사이징 · 리스크 관리 · 시나리오 분석 · 보유 기간 · 52주 위치 · 연승/연패 패턴
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Component ──
export default function SoxlLive({ onNavigate }) {
  const [tab, setTab] = useState('chart')
  const [resolution, setResolution] = useState('1')
  const [intraday, setIntraday] = useState(null)
  const [indicators, setIndicators] = useState(null)
  const [sector, setSector] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [sseEnabled, setSseEnabled] = useState(true)
  const intervalRef = useRef(null)

  const { quote, connected, lastReceivedAt } = useSoxlLive(sseEnabled)

  // Request notification permission
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  // Fetch supplementary data
  const fetchData = useCallback(async () => {
    try {
      const [ind, sec, alt] = await Promise.all([
        getSoxlLiveIndicators().catch(() => null),
        getSoxlSectorCorrelation().catch(() => null),
        getSoxlAlerts().catch(() => ({ alerts: [] })),
      ])
      setIndicators(ind)
      setSector(sec)
      setAlerts(alt?.alerts || [])
    } catch { /* silent */ }
    setLoading(false)
  }, [])

  const fetchIntraday = useCallback(async () => {
    try {
      const data = await getSoxlIntraday(resolution, 390)
      setIntraday(data)
    } catch { /* silent */ }
  }, [resolution])

  // Initial load + periodic refresh
  useEffect(() => {
    fetchData()
    fetchIntraday()

    // Refresh indicators/sector every 60s, intraday every 30s
    intervalRef.current = setInterval(() => {
      fetchData()
      fetchIntraday()
    }, 30000)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [fetchData, fetchIntraday])

  // Refetch intraday when resolution changes
  useEffect(() => { fetchIntraday() }, [resolution, fetchIntraday])

  const tabs = [
    { id: 'chart', label: '📊 실시간 차트' },
    { id: 'sector', label: '🔗 섹터 상관' },
    { id: 'alerts', label: '🔔 알림 설정' },
    { id: 'ai', label: '🤖 AI 분석' },
    { id: 'backtest', label: '🧪 백테스트' },
    { id: 'strategy', label: '🎯 AI 전략' },
  ]

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <h2 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
          ⚡ SOXL 실시간
        </h2>
        <button className="btn btn-secondary" style={{ fontSize: '0.7rem', padding: '4px 10px' }}
          onClick={() => onNavigate?.('soxl')}>
          📈 데일리 분석 →
        </button>
      </div>

      {/* Live price ticker */}
      <LiveHeader
        quote={quote} connected={connected}
        sseEnabled={sseEnabled} onToggleSSE={() => setSseEnabled(v => !v)}
        lastReceivedAt={lastReceivedAt}
      />

      {/* KPI strip */}
      <LiveKpiStrip indicators={indicators} />

      {/* Tab navigation */}
      <div style={{ display: 'flex', gap: 4, padding: '12px 0', borderBottom: '1px solid var(--card-border)' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={tab === t.id ? 'btn btn-primary' : 'btn btn-secondary'}
            style={{ fontSize: '0.75rem', padding: '6px 14px' }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ paddingTop: 16 }}>
        {tab === 'chart' && (
          <>
            <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
              {['1', '5'].map(r => (
                <button key={r} onClick={() => setResolution(r)}
                  className={resolution === r ? 'btn btn-primary' : 'btn btn-secondary'}
                  style={{ fontSize: '0.7rem', padding: '4px 12px' }}>
                  {r}분
                </button>
              ))}
            </div>
            <IntradayChart candles={intraday?.candles} resolution={resolution} source={intraday?.source} />
          </>
        )}
        {tab === 'sector' && <SectorCorrelation sectorData={sector} />}
        {tab === 'alerts' && <AlertManager alerts={alerts} onRefresh={fetchData} />}
        {tab === 'ai' && <MacroAiAnalysis />}
        {tab === 'backtest' && <SoxlBacktestTab />}
        {tab === 'strategy' && <SoxlAiStrategyTab />}
      </div>
    </div>
  )
}
