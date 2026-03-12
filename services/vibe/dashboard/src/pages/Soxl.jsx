import { useState, useEffect, useMemo, useCallback } from 'react'
import { useToast } from '../components/Toast'
import { getSoxlDashboard, getSoxlLevels } from '../api'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  ComposedChart, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine, ReferenceArea, Legend, Brush,
  Cell,
} from 'recharts'

/* ── Constants ── */
const SIGNAL_COLORS = {
  BUY: 'var(--green)', SELL: 'var(--red)', HOLD: 'var(--yellow)',
  STRONG_BUY: '#00e676', STRONG_SELL: '#ff1744',
}
const STANCE_EMOJI = {
  STRONG_BUY: '🟢', BUY: '🟢', SELL: '🔴',
  STRONG_SELL: '🔴', HOLD: '🟡',
}
const PERIOD_OPTIONS = [
  { value: 30, label: '1M' },
  { value: 60, label: '2M' },
  { value: 90, label: '3M' },
  { value: 180, label: '6M' },
  { value: 365, label: '1Y' },
]

export default function Soxl({ onNavigate, refreshKey }) {
  const [data, setData] = useState(null)
  const [levels, setLevels] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  const [days, setDays] = useState(90)
  const toast = useToast()

  const fetchData = useCallback((d) => {
    setLoading(true)
    Promise.all([getSoxlDashboard(d), getSoxlLevels()])
      .then(([dd, l]) => { setData(dd); setLevels(l) })
      .catch(err => toast.error('SOXL 데이터 로드 실패: ' + err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { fetchData(days) }, [refreshKey, days])

  if (loading) return <LoadingSkeleton />
  if (!data) return (
    <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
      <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📊</div>
      <h3>SOXL 데이터가 없습니다</h3>
      <p style={{ color: 'var(--text-muted)', margin: '0.5rem 0 1rem' }}>
        Watchlist에 SOXL을 추가하고 파이프라인을 실행해주세요.
      </p>
      <button className="btn btn-primary" onClick={() => onNavigate('data-admin')}>
        📋 데이터 관리 →
      </button>
    </div>
  )

  const { prices, technicals, signals, performance, strategy } = data
  const tabs = [
    { id: 'overview', label: '오버뷰', icon: '📊' },
    { id: 'charts', label: '차트 분석', icon: '📈' },
    { id: 'strategy', label: '매매 전략', icon: '🎯' },
    { id: 'signals', label: '시그널 이력', icon: '⚡' },
  ]

  return (
    <div>
      {/* Header */}
      <div className="page-header" style={{ marginBottom: '0.75rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <h2 style={{ margin: 0 }}>💹 SOXL</h2>
            {performance?.current_price && (
              <span style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                ${performance.current_price.toFixed(2)}
              </span>
            )}
            {performance?.change_1d != null && (
              <span style={{
                fontSize: '0.85rem', fontWeight: 600,
                color: performance.change_1d >= 0 ? 'var(--green)' : 'var(--red)',
              }}>
                {performance.change_1d >= 0 ? '▲' : '▼'} {fmtPct(performance.change_1d)}
              </span>
            )}
            {strategy && (
              <StanceBadge stance={strategy.stance} />
            )}
          </div>
          <p style={{ color: 'var(--text-muted)', margin: '0.25rem 0 0', fontSize: '0.75rem' }}>
            Direxion Daily Semiconductor Bull 3X &mdash; {data.asset_type}
            {data.updated_at && (
              <span style={{ marginLeft: '0.75rem', opacity: 0.7 }}>
                {new Date(data.updated_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })} 업데이트
              </span>
            )}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {/* Period Selector */}
          <div style={{ display: 'flex', gap: '0.15rem', background: 'var(--bg-secondary)', borderRadius: '0.5rem', padding: '0.15rem' }}>
            {PERIOD_OPTIONS.map(p => (
              <button key={p.value}
                className={`btn ${days === p.value ? 'btn-primary' : ''}`}
                style={{ padding: '0.25rem 0.5rem', fontSize: '0.7rem', minWidth: '2rem' }}
                onClick={() => setDays(p.value)}>
                {p.label}
              </button>
            ))}
          </div>
          <button className="btn btn-primary" onClick={() => onNavigate('geopolitical')}
            style={{ fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}>
            🌍 이란 이슈 →
          </button>
        </div>
      </div>

      {/* Quick KPI Strip */}
      <QuickKpiStrip performance={performance} technicals={technicals} />

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: '0.25rem', marginBottom: '1rem',
        borderBottom: '2px solid var(--border)', paddingBottom: '0',
      }}>
        {tabs.map(t => (
          <button key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{
              padding: '0.5rem 1rem', fontSize: '0.8rem', fontWeight: 600,
              background: 'none', border: 'none', cursor: 'pointer',
              color: activeTab === t.id ? 'var(--accent)' : 'var(--text-muted)',
              borderBottom: activeTab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: '-2px', transition: 'all 0.15s',
            }}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && <OverviewTab data={data} levels={levels} onNavigate={onNavigate} signals={signals} />}
      {activeTab === 'charts' && <ChartsTab technicals={technicals} prices={prices} levels={levels} signals={signals} />}
      {activeTab === 'strategy' && <StrategyTab strategy={strategy} performance={performance} />}
      {activeTab === 'signals' && <SignalsTab signals={signals} />}
    </div>
  )
}

/* ── Loading Skeleton ── */
function LoadingSkeleton() {
  const shimmer = {
    background: 'linear-gradient(90deg, var(--bg-secondary) 25%, var(--border) 50%, var(--bg-secondary) 75%)',
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.5s infinite',
    borderRadius: '0.5rem',
  }
  return (
    <div>
      <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
      <div style={{ ...shimmer, height: '2rem', width: '200px', marginBottom: '1rem' }} />
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', marginBottom: '1rem' }}>
        {[...Array(8)].map((_, i) => <div key={i} style={{ ...shimmer, height: '4rem' }} />)}
      </div>
      <div style={{ ...shimmer, height: '350px', marginBottom: '1rem' }} />
      <div style={{ ...shimmer, height: '200px' }} />
    </div>
  )
}

/* ── Stance Badge ── */
function StanceBadge({ stance }) {
  const bg = stance.includes('BUY') ? 'rgba(0,230,118,0.15)' :
    stance.includes('SELL') ? 'rgba(255,23,68,0.15)' : 'rgba(255,235,59,0.15)'
  const color = stance.includes('BUY') ? '#00e676' :
    stance.includes('SELL') ? '#ff1744' : '#ffeb3b'
  return (
    <span style={{
      padding: '0.25rem 0.75rem', borderRadius: '2rem', fontWeight: 700,
      fontSize: '0.75rem', background: bg, color,
    }}>
      {STANCE_EMOJI[stance] || '⭐'} {stance}
    </span>
  )
}

/* ── Quick KPI Strip (always visible) ── */
function QuickKpiStrip({ performance, technicals }) {
  const p = performance || {}
  const items = [
    { label: '현재가', value: p.current_price ? `$${p.current_price.toFixed(2)}` : '-', color: 'var(--text-primary)' },
    { label: '1일', value: fmtPct(p.change_1d), color: pctColor(p.change_1d) },
    { label: '5일', value: fmtPct(p.change_5d), color: pctColor(p.change_5d) },
    { label: '20일', value: fmtPct(p.change_20d), color: pctColor(p.change_20d) },
    { label: 'RSI', value: technicals?.rsi_14?.toFixed(1) || '-', color: rsiColor(technicals?.rsi_14) },
    { label: '변동성', value: p.volatility_20d_ann ? `${p.volatility_20d_ann}%` : '-', color: p.volatility_20d_ann > 80 ? 'var(--red)' : 'var(--yellow)' },
    { label: '거래량', value: fmtVolume(p.latest_volume), color: 'var(--text-primary)' },
    { label: '평균거래량', value: fmtVolume(p.avg_volume_20d), color: 'var(--text-muted)' },
  ]
  return (
    <div style={{
      display: 'flex', gap: '0.5rem', overflowX: 'auto', paddingBottom: '0.5rem',
      marginBottom: '0.75rem', scrollbarWidth: 'none',
    }}>
      {items.map((item, i) => (
        <div key={i} style={{
          flex: '0 0 auto', padding: '0.4rem 0.75rem',
          background: 'var(--bg-secondary)', borderRadius: '0.5rem',
          textAlign: 'center', minWidth: '80px',
        }}>
          <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginBottom: '0.15rem' }}>{item.label}</div>
          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: item.color }}>{item.value}</div>
        </div>
      ))}
    </div>
  )
}

/* ── Overview Tab ── */
function OverviewTab({ data, levels, onNavigate, signals }) {
  const { prices, performance, strategy, technicals } = data
  const p = performance || {}

  // Find nearest support/resistance
  const nearestLevels = useMemo(() => {
    if (!levels?.fibonacci || !levels?.pivot_points) return null
    const current = levels.current_price
    const allLevels = [
      ...Object.entries(levels.fibonacci).map(([k, v]) => ({ label: k.replace('_', ' ').replace('fib ', 'Fib '), value: v })),
      ...Object.entries(levels.pivot_points).map(([k, v]) => ({ label: k.toUpperCase(), value: v })),
    ].sort((a, b) => a.value - b.value)

    const support = allLevels.filter(l => l.value < current).pop()
    const resistance = allLevels.filter(l => l.value > current).shift()
    return { support, resistance }
  }, [levels])

  // Latest signal
  const latestSignal = signals?.[0]

  return (
    <>
      {/* Today's Summary Card */}
      <div className="card" style={{
        marginBottom: '1rem', padding: '0.75rem 1rem',
        background: 'linear-gradient(135deg, var(--bg-secondary) 0%, rgba(99,102,241,0.05) 100%)',
        borderLeft: `4px solid ${strategy?.stance?.includes('BUY') ? '#00e676' : strategy?.stance?.includes('SELL') ? '#ff1744' : 'var(--accent)'}`,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '0.3rem' }}>
              오늘의 SOXL 요약
            </div>
            <div style={{ fontSize: '0.85rem', lineHeight: 1.6 }}>
              {strategy && <span>종합 판단: <b style={{ color: strategy.stance.includes('BUY') ? '#00e676' : strategy.stance.includes('SELL') ? '#ff1744' : '#ffeb3b' }}>{strategy.stance}</b></span>}
              {latestSignal && <span style={{ marginLeft: '1rem' }}>시그널 점수: <b>{latestSignal.raw_score?.toFixed(1)}</b>/100</span>}
              {p.volatility_20d_ann && <span style={{ marginLeft: '1rem' }}>변동성: <b style={{ color: p.volatility_20d_ann > 80 ? 'var(--red)' : 'var(--yellow)' }}>{p.volatility_20d_ann}%</b></span>}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '1rem', fontSize: '0.78rem' }}>
            {nearestLevels?.support && (
              <div>
                <span style={{ color: 'var(--text-muted)' }}>지지: </span>
                <b style={{ color: 'var(--green)' }}>${nearestLevels.support.value}</b>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem' }}> ({nearestLevels.support.label})</span>
              </div>
            )}
            {nearestLevels?.resistance && (
              <div>
                <span style={{ color: 'var(--text-muted)' }}>저항: </span>
                <b style={{ color: 'var(--red)' }}>${nearestLevels.resistance.value}</b>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem' }}> ({nearestLevels.resistance.label})</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Price Chart with MA & Levels */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h3 style={{ margin: 0 }}>📈 가격 차트</h3>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            {prices.length}일 데이터 | MA5·MA20·MA60
          </span>
        </div>
        <PriceChart prices={prices} technicals={technicals} levels={levels} />
      </div>

      {/* Two columns: Levels + Strategy */}
      <div className="card-grid" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: '1rem' }}>
        {/* Fibonacci & Pivot */}
        {levels && (
          <div className="card">
            <h4 style={{ marginBottom: '0.5rem' }}>📏 핵심 레벨</h4>
            <LevelTable levels={levels} />
          </div>
        )}

        {/* Strategy Summary */}
        {strategy && (
          <div className="card" style={{
            borderLeft: `4px solid ${strategy.stance.includes('BUY') ? '#00e676' : strategy.stance.includes('SELL') ? '#ff1744' : '#ffeb3b'}`,
          }}>
            <h4 style={{ marginBottom: '0.5rem' }}>
              {STANCE_EMOJI[strategy.stance]} 종합 판단: {strategy.stance}
            </h4>
            <p style={{ color: 'var(--text-secondary)', margin: '0 0 0.5rem', fontSize: '0.8rem' }}>
              {strategy.stance_desc}
            </p>
            <ConditionBars conditions={strategy.conditions} />
            <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', fontSize: '0.75rem' }}>
              <span style={{ color: 'var(--green)' }}>매수 {strategy.buy_signals}개</span>
              <span style={{ color: 'var(--red)' }}>매도 {strategy.sell_signals}개</span>
            </div>
          </div>
        )}
      </div>

      {/* 52-Week Range Bar */}
      {levels?.position && (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h4 style={{ marginBottom: '0.75rem' }}>📍 52주 범위 포지션</h4>
          <RangeBar
            low={levels.fibonacci?.['52w_low']}
            high={levels.fibonacci?.['52w_high']}
            current={levels.current_price}
            levels={levels}
          />
        </div>
      )}

      {/* Risk Warnings */}
      {strategy?.risk_warnings?.length > 0 && (
        <div className="card" style={{ background: 'rgba(255,23,68,0.05)', borderLeft: '4px solid var(--red)' }}>
          <h4>⚠️ 리스크 경고</h4>
          <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.2rem', fontSize: '0.8rem', lineHeight: 1.8 }}>
            {strategy.risk_warnings.map((w, i) => (
              <li key={i} style={{ color: i < 2 ? 'var(--text-secondary)' : 'var(--red)' }}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}

/* ── Charts Tab (NEW - dedicated charting) ── */
function ChartsTab({ technicals, prices, levels, signals }) {
  if (!technicals) return <div className="loading">기술적 지표 데이터 없음</div>

  return (
    <>
      {/* Price + Volume Composed Chart */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginBottom: '0.5rem' }}>📊 가격 + 거래량</h3>
        <PriceVolumeChart prices={prices} levels={levels} signals={signals} />
      </div>

      {/* RSI Chart */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginBottom: '0.5rem' }}>📉 RSI (14)</h3>
        <RsiChart prices={prices} />
      </div>

      {/* MACD Chart */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginBottom: '0.5rem' }}>📈 MACD</h3>
        <MacdChart prices={prices} technicals={technicals} />
      </div>

      {/* Bollinger Bands */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginBottom: '0.5rem' }}>🎯 볼린저 밴드</h3>
        <BollingerChart prices={prices} technicals={technicals} />
      </div>

      {/* Indicator Table */}
      <div className="card">
        <h3 style={{ marginBottom: '0.5rem' }}>🔧 기술적 지표 상세</h3>
        <IndicatorTable technicals={technicals} />
      </div>
    </>
  )
}

/* ── Strategy Tab ── */
function StrategyTab({ strategy, performance }) {
  if (!strategy) return <div className="loading">전략 데이터 없음</div>

  const rules = strategy.trading_rules || {}
  return (
    <>
      {/* Score Gauge */}
      <div className="card" style={{ marginBottom: '1rem', textAlign: 'center' }}>
        <h3 style={{ marginBottom: '0.75rem' }}>🎯 종합 판단</h3>
        <ScoreGauge
          buySignals={strategy.buy_signals}
          sellSignals={strategy.sell_signals}
          stance={strategy.stance}
        />
        <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem', fontSize: '0.85rem' }}>
          {strategy.stance_desc}
        </p>
      </div>

      {/* Conditions */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3>📊 현재 지표 상태</h3>
        <div style={{ display: 'grid', gap: '0.5rem', marginTop: '0.75rem' }}>
          {strategy.conditions?.map((c, i) => (
            <ConditionRow key={i} condition={c} />
          ))}
        </div>
      </div>

      {/* Entry Rules */}
      <RuleCard title="🟢 매수 규칙" rules={rules.entry_rules} color="var(--green)" />
      <RuleCard title="🔴 매도/손절 규칙" rules={rules.exit_rules} color="var(--red)" />
      <RuleCard title="💰 포지션 사이징" rules={rules.position_sizing} color="var(--accent)" />

      {/* Position Size Calculator */}
      <PositionCalculator volatility={performance?.volatility_20d_ann} currentPrice={performance?.current_price} />
    </>
  )
}

/* ── Signals Tab ── */
function SignalsTab({ signals }) {
  const [expandedIdx, setExpandedIdx] = useState(null)

  if (!signals?.length) return (
    <div className="card" style={{ textAlign: 'center', padding: '2rem' }}>
      <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⚡</div>
      <p style={{ color: 'var(--text-muted)' }}>시그널 이력 없음</p>
    </div>
  )

  // Signal score trend chart
  const scoreData = [...signals].reverse().map(s => ({
    date: s.date?.slice(5),
    score: s.raw_score,
    signal: s.final_signal,
  }))

  return (
    <>
      {/* Score Trend Chart */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginBottom: '0.5rem' }}>📈 시그널 점수 추이</h3>
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart data={scoreData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
            <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} domain={[0, 100]} />
            <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8 }} />
            <ReferenceArea y1={70} y2={100} fill="rgba(0,230,118,0.05)" />
            <ReferenceArea y1={0} y2={30} fill="rgba(255,23,68,0.05)" />
            <ReferenceLine y={50} stroke="var(--text-muted)" strokeDasharray="3 3" />
            <ReferenceLine y={70} stroke="var(--green)" strokeDasharray="3 3" strokeOpacity={0.5} />
            <ReferenceLine y={30} stroke="var(--red)" strokeDasharray="3 3" strokeOpacity={0.5} />
            <Bar dataKey="score" radius={[2, 2, 0, 0]}>
              {scoreData.map((entry, i) => (
                <Cell key={i} fill={
                  entry.signal === 'BUY' || entry.signal === 'STRONG_BUY' ? 'rgba(0,230,118,0.6)' :
                  entry.signal === 'SELL' || entry.signal === 'STRONG_SELL' ? 'rgba(255,23,68,0.6)' :
                  'rgba(255,235,59,0.4)'
                } />
              ))}
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Signal History Table */}
      <div className="card">
        <h3 style={{ marginBottom: '0.5rem' }}>⚡ 시그널 이력 (최근 {signals.length}건)</h3>
        <div className="table-container" style={{ marginTop: '0.5rem' }}>
          <table className="table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>날짜</th><th>시그널</th><th>점수</th>
                <th>신뢰도</th><th>HL</th><th>근거</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((s, i) => (
                <tr key={i}
                  style={{ cursor: 'pointer', background: expandedIdx === i ? 'var(--bg-secondary)' : 'transparent' }}
                  onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}>
                  <td style={{ whiteSpace: 'nowrap' }}>{s.date}</td>
                  <td>
                    <span style={{
                      padding: '0.15rem 0.5rem', borderRadius: '0.25rem', fontSize: '0.7rem', fontWeight: 700,
                      background: (s.final_signal || '').includes('BUY') ? 'rgba(0,230,118,0.15)' :
                        (s.final_signal || '').includes('SELL') ? 'rgba(255,23,68,0.15)' : 'rgba(255,235,59,0.15)',
                      color: (s.final_signal || '').includes('BUY') ? '#00e676' :
                        (s.final_signal || '').includes('SELL') ? '#ff1744' : '#ffeb3b',
                    }}>
                      {s.final_signal || s.raw_signal || '-'}
                    </span>
                  </td>
                  <td style={{ fontWeight: 600 }}>{s.raw_score?.toFixed(1) ?? '-'}</td>
                  <td>{s.confidence != null ? `${(s.confidence * 100).toFixed(0)}%` : '-'}</td>
                  <td>{s.hard_limit ? '🛑' : '✓'}</td>
                  <td style={{
                    fontSize: '0.75rem',
                    maxWidth: expandedIdx === i ? 'none' : '300px',
                    whiteSpace: expandedIdx === i ? 'normal' : 'nowrap',
                    overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>
                    {s.rationale || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
          💡 행을 클릭하면 근거를 펼쳐볼 수 있습니다
        </div>
      </div>
    </>
  )
}

/* ── Chart Components ── */

function PriceChart({ prices, technicals, levels }) {
  // Compute MA series from prices
  const chartData = useMemo(() => {
    return prices.map((p, i) => {
      const ma5 = i >= 4 ? avg(prices.slice(i - 4, i + 1).map(x => x.close)) : null
      const ma20 = i >= 19 ? avg(prices.slice(i - 19, i + 1).map(x => x.close)) : null
      const ma60 = i >= 59 ? avg(prices.slice(i - 59, i + 1).map(x => x.close)) : null
      return { ...p, date: p.date?.slice(5), ma5, ma20, ma60 }
    })
  }, [prices])

  return (
    <ResponsiveContainer width="100%" height={350}>
      <ComposedChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
        <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} domain={['auto', 'auto']} />
        <Tooltip
          contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8, fontSize: '0.8rem' }}
          formatter={(v, name) => [name === 'close' ? `$${Number(v).toFixed(2)}` : `$${Number(v).toFixed(2)}`, name === 'close' ? '종가' : name]}
          labelFormatter={l => `${l}`}
        />
        <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
        {/* Support/Resistance levels */}
        {levels?.pivot_points?.s1 && <ReferenceLine y={levels.pivot_points.s1} stroke="var(--green)" strokeDasharray="8 4" strokeOpacity={0.4} />}
        {levels?.pivot_points?.r1 && <ReferenceLine y={levels.pivot_points.r1} stroke="var(--red)" strokeDasharray="8 4" strokeOpacity={0.4} />}
        {/* Price area */}
        <Area type="monotone" dataKey="close" stroke="var(--accent)" fill="rgba(99,102,241,0.1)" strokeWidth={2} dot={false} name="종가" />
        {/* Moving averages */}
        <Line type="monotone" dataKey="ma5" stroke="#e91e63" strokeWidth={1} dot={false} name="MA5" connectNulls />
        <Line type="monotone" dataKey="ma20" stroke="#ff9800" strokeWidth={1.5} dot={false} name="MA20" connectNulls />
        <Line type="monotone" dataKey="ma60" stroke="#2196f3" strokeWidth={1.5} dot={false} name="MA60" connectNulls />
        <Brush dataKey="date" height={20} stroke="var(--border)" fill="var(--bg-secondary)" />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

function PriceVolumeChart({ prices, levels, signals }) {
  const data = useMemo(() => {
    const signalMap = {}
    if (signals) signals.forEach(s => { signalMap[s.date] = s })
    return prices.map(p => ({
      ...p,
      date: p.date?.slice(5),
      fullDate: p.date,
      signal: signalMap[p.date]?.final_signal || null,
    }))
  }, [prices, signals])

  return (
    <ResponsiveContainer width="100%" height={350}>
      <ComposedChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
        <YAxis yAxisId="price" orientation="right" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} domain={['auto', 'auto']} />
        <YAxis yAxisId="vol" orientation="left" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} tickFormatter={v => `${(v / 1e6).toFixed(0)}M`} />
        <Tooltip
          contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8 }}
          formatter={(v, name) => {
            if (name === '거래량') return [`${(Number(v) / 1e6).toFixed(1)}M`, name]
            return [`$${Number(v).toFixed(2)}`, name]
          }}
        />
        <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
        {levels?.pivot_points?.pivot && <ReferenceLine yAxisId="price" y={levels.pivot_points.pivot} stroke="var(--yellow)" strokeDasharray="5 5" strokeOpacity={0.5} />}
        <Bar yAxisId="vol" dataKey="volume" name="거래량" radius={[1, 1, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={
              entry.signal === 'BUY' || entry.signal === 'STRONG_BUY' ? 'rgba(0,230,118,0.3)' :
              entry.signal === 'SELL' || entry.signal === 'STRONG_SELL' ? 'rgba(255,23,68,0.3)' :
              'rgba(99,102,241,0.2)'
            } />
          ))}
        </Bar>
        <Line yAxisId="price" type="monotone" dataKey="close" stroke="var(--accent)" dot={false} strokeWidth={2} name="종가" />
        <Brush dataKey="date" height={20} stroke="var(--border)" fill="var(--bg-secondary)" />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

function RsiChart({ prices }) {
  const data = useMemo(() => {
    return prices.map((p, i) => {
      let rsi = null
      if (i >= 14) {
        const window = prices.slice(i - 13, i + 1)
        let gains = 0, losses = 0
        for (let j = 1; j < window.length; j++) {
          const diff = window[j].close - window[j - 1].close
          if (diff > 0) gains += diff
          else losses += Math.abs(diff)
        }
        const avgGain = gains / 14
        const avgLoss = losses / 14
        rsi = avgLoss === 0 ? 100 : 100 - (100 / (1 + avgGain / avgLoss))
      }
      return { date: p.date?.slice(5), rsi: rsi ? Math.round(rsi * 10) / 10 : null }
    })
  }, [prices])

  return (
    <ResponsiveContainer width="100%" height={200}>
      <ComposedChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
        <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} domain={[0, 100]} ticks={[0, 30, 50, 70, 100]} />
        <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8 }} />
        <ReferenceArea y1={70} y2={100} fill="rgba(255,23,68,0.06)" label={{ value: '과매수', position: 'insideRight', fill: 'var(--red)', fontSize: 10 }} />
        <ReferenceArea y1={0} y2={30} fill="rgba(0,230,118,0.06)" label={{ value: '과매도', position: 'insideRight', fill: 'var(--green)', fontSize: 10 }} />
        <ReferenceLine y={50} stroke="var(--text-muted)" strokeDasharray="3 3" />
        <Line type="monotone" dataKey="rsi" stroke="#e040fb" strokeWidth={2} dot={false} connectNulls name="RSI" />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

function MacdChart({ prices, technicals }) {
  // Simple MACD calculation from prices
  const data = useMemo(() => {
    const closes = prices.map(p => p.close)
    const ema12 = calcEma(closes, 12)
    const ema26 = calcEma(closes, 26)
    const macdLine = ema12.map((v, i) => v != null && ema26[i] != null ? v - ema26[i] : null)
    const macdSignal = calcEma(macdLine.filter(v => v !== null), 9)

    // Align signal with macdLine
    let sigIdx = 0
    const signalAligned = macdLine.map(v => {
      if (v === null) return null
      return sigIdx < macdSignal.length ? macdSignal[sigIdx++] : null
    })

    return prices.map((p, i) => ({
      date: p.date?.slice(5),
      macd: macdLine[i] ? Math.round(macdLine[i] * 1000) / 1000 : null,
      signal: signalAligned[i] ? Math.round(signalAligned[i] * 1000) / 1000 : null,
      histogram: macdLine[i] != null && signalAligned[i] != null ?
        Math.round((macdLine[i] - signalAligned[i]) * 1000) / 1000 : null,
    }))
  }, [prices])

  return (
    <ResponsiveContainer width="100%" height={250}>
      <ComposedChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
        <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
        <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8 }} />
        <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
        <ReferenceLine y={0} stroke="var(--text-muted)" strokeDasharray="3 3" />
        <Bar dataKey="histogram" name="히스토그램" radius={[1, 1, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.histogram >= 0 ? 'rgba(0,230,118,0.4)' : 'rgba(255,23,68,0.4)'} />
          ))}
        </Bar>
        <Line type="monotone" dataKey="macd" stroke="#2196f3" strokeWidth={1.5} dot={false} name="MACD" connectNulls />
        <Line type="monotone" dataKey="signal" stroke="#ff9800" strokeWidth={1.5} dot={false} name="Signal" connectNulls />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

function BollingerChart({ prices, technicals }) {
  const data = useMemo(() => {
    return prices.map((p, i) => {
      let bbUpper = null, bbMiddle = null, bbLower = null
      if (i >= 19) {
        const window = prices.slice(i - 19, i + 1).map(x => x.close)
        const mean = avg(window)
        const std = Math.sqrt(window.reduce((s, v) => s + (v - mean) ** 2, 0) / window.length)
        bbMiddle = mean
        bbUpper = mean + 2 * std
        bbLower = mean - 2 * std
      }
      return {
        date: p.date?.slice(5),
        close: p.close,
        bbUpper: bbUpper ? Math.round(bbUpper * 100) / 100 : null,
        bbMiddle: bbMiddle ? Math.round(bbMiddle * 100) / 100 : null,
        bbLower: bbLower ? Math.round(bbLower * 100) / 100 : null,
      }
    })
  }, [prices])

  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} />
        <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} domain={['auto', 'auto']} />
        <Tooltip
          contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8 }}
          formatter={(v) => [`$${Number(v).toFixed(2)}`, '']}
        />
        <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
        <Area type="monotone" dataKey="bbUpper" stroke="rgba(255,23,68,0.3)" fill="none" strokeDasharray="4 4" name="BB Upper" connectNulls />
        <Area type="monotone" dataKey="bbLower" stroke="rgba(0,230,118,0.3)" fill="rgba(99,102,241,0.04)" strokeDasharray="4 4" name="BB Lower" connectNulls />
        <Line type="monotone" dataKey="bbMiddle" stroke="#ff9800" strokeWidth={1} dot={false} name="BB Middle" connectNulls />
        <Line type="monotone" dataKey="close" stroke="var(--accent)" strokeWidth={2} dot={false} name="종가" />
      </ComposedChart>
    </ResponsiveContainer>
  )
}

/* ── Sub-Components ── */

function LevelTable({ levels }) {
  const currentPrice = levels.current_price
  return (
    <div>
      {/* Fibonacci */}
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '0.3rem' }}>피보나치</div>
      <table style={{ width: '100%', fontSize: '0.78rem', marginBottom: '0.75rem' }}>
        <tbody>
          {levels.fibonacci && Object.entries(levels.fibonacci).map(([k, v]) => {
            const isNear = Math.abs(v - currentPrice) / currentPrice < 0.03
            return (
              <tr key={k} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '0.2rem 0', color: 'var(--text-muted)' }}>
                  {k.replace('_', ' ').replace('fib ', 'Fib ')}
                </td>
                <td style={{
                  textAlign: 'right', fontWeight: isNear ? 800 : 600,
                  color: isNear ? 'var(--accent)' : 'var(--text-primary)',
                }}>
                  ${v} {isNear ? '◄' : ''}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {/* Pivot Points */}
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '0.3rem' }}>피봇 포인트</div>
      <table style={{ width: '100%', fontSize: '0.78rem' }}>
        <tbody>
          {levels.pivot_points && Object.entries(levels.pivot_points).map(([k, v]) => (
            <tr key={k} style={{ borderBottom: '1px solid var(--border)' }}>
              <td style={{ padding: '0.2rem 0', color: 'var(--text-muted)' }}>{k.toUpperCase()}</td>
              <td style={{
                textAlign: 'right', fontWeight: 600,
                color: k.startsWith('r') ? 'var(--red)' : k.startsWith('s') ? 'var(--green)' : 'var(--text-primary)',
              }}>${v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {levels.position && (
        <div style={{ marginTop: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
          고점 대비 <b style={{ color: 'var(--red)' }}>{levels.position.pct_from_52w_high}%</b> |
          저점 대비 <b style={{ color: 'var(--green)' }}>+{levels.position.pct_from_52w_low}%</b>
        </div>
      )}
    </div>
  )
}

function RangeBar({ low, high, current, levels }) {
  if (!low || !high || !current) return null
  const range = high - low
  const pct = range > 0 ? ((current - low) / range) * 100 : 50

  // Key levels to mark
  const marks = []
  if (levels?.fibonacci) {
    Object.entries(levels.fibonacci).forEach(([k, v]) => {
      if (k !== '52w_high' && k !== '52w_low') {
        marks.push({ label: k.replace('fib_', ''), value: v, pct: ((v - low) / range) * 100 })
      }
    })
  }

  return (
    <div style={{ padding: '0 0.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', marginBottom: '0.5rem' }}>
        <span style={{ color: 'var(--green)' }}>52주 저점: ${low}</span>
        <span style={{ fontWeight: 700, color: 'var(--accent)' }}>현재: ${current}</span>
        <span style={{ color: 'var(--red)' }}>52주 고점: ${high}</span>
      </div>
      <div style={{
        position: 'relative', height: '24px', background: 'var(--bg-secondary)',
        borderRadius: '12px', overflow: 'visible',
      }}>
        {/* Gradient fill */}
        <div style={{
          position: 'absolute', left: 0, top: 0, height: '100%',
          width: `${Math.min(pct, 100)}%`,
          background: 'linear-gradient(90deg, var(--green), var(--yellow), var(--red))',
          borderRadius: '12px', opacity: 0.3,
        }} />
        {/* Fib level marks */}
        {marks.map((m, i) => (
          <div key={i} style={{
            position: 'absolute', left: `${m.pct}%`, top: '-4px',
            width: '1px', height: '32px', background: 'var(--border)',
          }}>
            <span style={{
              position: 'absolute', top: '-16px', left: '-10px',
              fontSize: '0.55rem', color: 'var(--text-muted)', whiteSpace: 'nowrap',
            }}>{m.label}</span>
          </div>
        ))}
        {/* Current position marker */}
        <div style={{
          position: 'absolute', left: `${Math.min(pct, 100)}%`, top: '-2px',
          width: '4px', height: '28px', background: 'var(--accent)',
          borderRadius: '2px', transform: 'translateX(-2px)',
          boxShadow: '0 0 8px var(--accent)',
        }} />
      </div>
      <div style={{ textAlign: 'center', marginTop: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
        52주 범위 내 {pct.toFixed(1)}% 위치
      </div>
    </div>
  )
}

function ConditionBars({ conditions }) {
  if (!conditions?.length) return null
  return (
    <div style={{ display: 'grid', gap: '0.3rem' }}>
      {conditions.map((c, i) => {
        const isBullish = c.signal.includes('UNDER') || c.signal === 'BULLISH' || c.signal.includes('OVERSOLD')
        const isBearish = c.signal.includes('OVER') || c.signal === 'BEARISH'
        const color = isBullish ? '#00e676' : isBearish ? '#ff1744' : '#ffeb3b'
        return (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.75rem',
          }}>
            <span style={{
              width: '6px', height: '6px', borderRadius: '50%', background: color, flexShrink: 0,
            }} />
            <span style={{ fontWeight: 600, minWidth: '55px', color }}>{c.indicator}</span>
            <span style={{ color: 'var(--text-muted)' }}>{c.desc}</span>
          </div>
        )
      })}
    </div>
  )
}

function ConditionRow({ condition: c }) {
  const isBullish = c.signal.includes('UNDER') || c.signal === 'BULLISH' || c.signal.includes('OVERSOLD')
  const isBearish = c.signal.includes('OVER') || c.signal === 'BEARISH'
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '0.75rem',
      padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', borderRadius: '0.5rem',
    }}>
      <span style={{
        padding: '0.2rem 0.5rem', borderRadius: '0.25rem', fontSize: '0.7rem', fontWeight: 700,
        minWidth: '80px', textAlign: 'center',
        background: isBearish ? 'rgba(255,23,68,0.15)' : isBullish ? 'rgba(0,230,118,0.15)' : 'rgba(255,235,59,0.15)',
        color: isBearish ? '#ff1744' : isBullish ? '#00e676' : '#ffeb3b',
      }}>
        {c.indicator}
      </span>
      <span style={{ fontWeight: 600, minWidth: '60px' }}>{typeof c.value === 'number' ? c.value : '-'}</span>
      <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', flex: 1 }}>{c.desc}</span>
    </div>
  )
}

function ScoreGauge({ buySignals, sellSignals, stance }) {
  const total = buySignals + sellSignals
  const score = total > 0 ? (buySignals / total) * 100 : 50
  const gaugeColor = stance.includes('BUY') ? '#00e676' : stance.includes('SELL') ? '#ff1744' : '#ffeb3b'

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '2rem' }}>
      {/* Gauge bar */}
      <div style={{ width: '60%', maxWidth: '300px' }}>
        <div style={{
          height: '12px', borderRadius: '6px', background: 'var(--bg-secondary)', position: 'relative', overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', left: 0, top: 0, height: '100%',
            width: `${score}%`, borderRadius: '6px',
            background: `linear-gradient(90deg, #ff1744, #ffeb3b, #00e676)`,
            transition: 'width 0.5s ease',
          }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.25rem', fontSize: '0.65rem', color: 'var(--text-muted)' }}>
          <span>SELL</span>
          <span>HOLD</span>
          <span>BUY</span>
        </div>
      </div>
      {/* Stance label */}
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '1.5rem', fontWeight: 800, color: gaugeColor }}>{stance}</div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
          매수 {buySignals} | 매도 {sellSignals}
        </div>
      </div>
    </div>
  )
}

function RuleCard({ title, rules, color }) {
  if (!rules?.length) return null
  return (
    <div className="card" style={{ marginBottom: '1rem', borderLeft: `4px solid ${color}` }}>
      <h4>{title}</h4>
      <div style={{ display: 'grid', gap: '0.5rem', marginTop: '0.5rem' }}>
        {rules.map((r, i) => (
          <div key={i} style={{ padding: '0.4rem 0', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{r.rule}</div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>{r.desc}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function PositionCalculator({ volatility, currentPrice }) {
  const [portfolioSize, setPortfolioSize] = useState('')
  const size = parseFloat(portfolioSize)
  const price = currentPrice || 56

  const maxPct = volatility && volatility > 80 ? 7.5 : 15
  const maxAmount = size ? (size * maxPct / 100) : null
  const shares = maxAmount ? Math.floor(maxAmount / price) : null

  return (
    <div className="card" style={{ marginBottom: '1rem' }}>
      <h4>🧮 포지션 사이즈 계산기</h4>
      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginTop: '0.75rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>총 포트폴리오:</label>
          <input
            type="number"
            value={portfolioSize}
            onChange={e => setPortfolioSize(e.target.value)}
            placeholder="100000"
            style={{
              padding: '0.4rem 0.75rem', borderRadius: '0.5rem', width: '120px',
              background: 'var(--bg-secondary)', border: '1px solid var(--border)',
              color: 'var(--text-primary)', fontSize: '0.85rem',
            }}
          />
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>USD</span>
        </div>
        {maxAmount && (
          <div style={{ display: 'flex', gap: '1rem', fontSize: '0.85rem' }}>
            <span>
              최대 비중: <b style={{ color: 'var(--accent)' }}>{maxPct}%</b>
              {volatility > 80 && <span style={{ color: 'var(--red)', fontSize: '0.7rem' }}> (고변동성 감소)</span>}
            </span>
            <span>최대 금액: <b style={{ color: 'var(--accent)' }}>${maxAmount.toLocaleString()}</b></span>
            {shares > 0 && <span>약 <b>{shares}</b>주</span>}
          </div>
        )}
      </div>
    </div>
  )
}

function IndicatorTable({ technicals }) {
  const t = technicals
  const indicators = [
    { label: 'RSI (14)', value: t.rsi_14?.toFixed(1), status: rsiStatus(t.rsi_14), color: rsiColor(t.rsi_14) },
    { label: 'MA 5', value: t.ma_5 ? `$${t.ma_5.toFixed(2)}` : '-', status: '-', color: 'var(--text-primary)' },
    { label: 'MA 20', value: t.ma_20 ? `$${t.ma_20.toFixed(2)}` : '-', status: '-', color: '#ff9800' },
    { label: 'MA 60', value: t.ma_60 ? `$${t.ma_60.toFixed(2)}` : '-', status: '-', color: '#2196f3' },
    { label: 'MACD', value: t.macd?.toFixed(3), status: t.macd > (t.macd_signal || 0) ? '골든크로스' : '데드크로스', color: t.macd > (t.macd_signal || 0) ? 'var(--green)' : 'var(--red)' },
    { label: 'MACD Signal', value: t.macd_signal?.toFixed(3), status: '-', color: 'var(--text-muted)' },
    { label: 'BB Upper', value: t.bb_upper ? `$${t.bb_upper.toFixed(2)}` : '-', status: '-', color: 'var(--red)' },
    { label: 'BB Middle', value: t.bb_middle ? `$${t.bb_middle.toFixed(2)}` : '-', status: '-', color: 'var(--text-muted)' },
    { label: 'BB Lower', value: t.bb_lower ? `$${t.bb_lower.toFixed(2)}` : '-', status: '-', color: 'var(--green)' },
    { label: '이격도 (20MA)', value: t.disparity_20 ? `${t.disparity_20.toFixed(1)}%` : '-', status: t.disparity_20 > 105 ? '과열' : t.disparity_20 < 95 ? '이탈' : '정상', color: t.disparity_20 > 105 ? 'var(--red)' : t.disparity_20 < 95 ? 'var(--green)' : 'var(--text-primary)' },
    { label: '거래량 비율', value: t.volume_ratio?.toFixed(2), status: t.volume_ratio > 2 ? '급증' : t.volume_ratio < 0.5 ? '감소' : '보통', color: t.volume_ratio > 2 ? 'var(--yellow)' : 'var(--text-primary)' },
  ]

  return (
    <>
      <table className="table" style={{ width: '100%', marginTop: '0.5rem' }}>
        <thead>
          <tr><th>지표</th><th>값</th><th>상태</th></tr>
        </thead>
        <tbody>
          {indicators.map((ind, i) => (
            <tr key={i}>
              <td style={{ fontWeight: 600 }}>{ind.label}</td>
              <td style={{ color: ind.color, fontWeight: 600 }}>{ind.value ?? '-'}</td>
              <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{ind.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {technicals?.updated_at && (
        <div style={{ marginTop: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
          업데이트: {technicals.updated_at}
        </div>
      )}
    </>
  )
}

/* ── Helpers ── */
function fmtPct(v) { return v != null ? `${v > 0 ? '+' : ''}${v.toFixed(2)}%` : '-' }
function pctColor(v) { return v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'var(--text-primary)' }
function rsiColor(v) { if (v == null) return 'var(--text-muted)'; return v > 70 ? 'var(--red)' : v < 30 ? 'var(--green)' : 'var(--yellow)' }
function rsiStatus(v) { if (v == null) return '-'; return v > 70 ? '과매수' : v > 60 ? '매수우세' : v < 30 ? '과매도' : v < 40 ? '매도우세' : '중립' }
function fmtVolume(v) { if (!v) return '-'; if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`; if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`; if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`; return v.toString() }
function avg(arr) { return arr.length ? arr.reduce((s, v) => s + v, 0) / arr.length : 0 }

function calcEma(data, period) {
  const k = 2 / (period + 1)
  const result = []
  let ema = null
  for (let i = 0; i < data.length; i++) {
    if (data[i] === null || data[i] === undefined) { result.push(null); continue }
    if (ema === null) {
      ema = data[i]
    } else {
      ema = data[i] * k + ema * (1 - k)
    }
    result.push(ema)
  }
  return result
}
