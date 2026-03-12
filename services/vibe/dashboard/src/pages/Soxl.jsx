import { useState, useEffect } from 'react'
import { useToast } from '../components/Toast'
import { getSoxlDashboard, getSoxlLevels } from '../api'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  ReferenceLine, Legend,
} from 'recharts'

const SIGNAL_COLORS = {
  BUY: 'var(--green)', SELL: 'var(--red)', HOLD: 'var(--yellow)',
  STRONG_BUY: '#00e676', STRONG_SELL: '#ff1744',
}

const STANCE_EMOJI = {
  STRONG_BUY: '🟢', BUY: '🟢', SELL: '🔴',
  STRONG_SELL: '🔴', HOLD: '🟡',
}

export default function Soxl({ onNavigate, refreshKey }) {
  const [data, setData] = useState(null)
  const [levels, setLevels] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  const toast = useToast()

  useEffect(() => {
    setLoading(true)
    Promise.all([getSoxlDashboard(90), getSoxlLevels()])
      .then(([d, l]) => { setData(d); setLevels(l) })
      .catch(err => toast.error('SOXL 데이터 로드 실패: ' + err.message))
      .finally(() => setLoading(false))
  }, [refreshKey])

  if (loading) return <div className="loading">⏳ SOXL 데이터 로딩...</div>
  if (!data) return <div className="loading">⚠ SOXL 데이터가 없습니다. Watchlist에 SOXL을 추가하고 파이프라인을 실행해주세요.</div>

  const { prices, technicals, signals, performance, strategy } = data
  const tabs = [
    { id: 'overview', label: '오버뷰' },
    { id: 'strategy', label: '매매 전략' },
    { id: 'technicals', label: '기술적 분석' },
    { id: 'signals', label: '시그널 이력' },
  ]

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div>
          <h2>SOXL 전용 대시보드</h2>
          <p style={{ color: 'var(--text-muted)', margin: '0.25rem 0 0' }}>
            Direxion Daily Semiconductor Bull 3X Shares &mdash; {data.asset_type}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {strategy && (
            <span style={{
              padding: '0.4rem 1rem', borderRadius: '2rem', fontWeight: 700, fontSize: '0.85rem',
              background: strategy.stance.includes('BUY') ? 'rgba(0,230,118,0.15)' :
                strategy.stance.includes('SELL') ? 'rgba(255,23,68,0.15)' : 'rgba(255,235,59,0.15)',
              color: strategy.stance.includes('BUY') ? '#00e676' :
                strategy.stance.includes('SELL') ? '#ff1744' : '#ffeb3b',
            }}>
              {STANCE_EMOJI[strategy.stance] || '⭐'} {strategy.stance}
            </span>
          )}
          <button className="btn btn-primary" onClick={() => onNavigate('geopolitical')}>
            🌍 이란 이슈 →
          </button>
        </div>
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

      {activeTab === 'overview' && <OverviewTab data={data} levels={levels} />}
      {activeTab === 'strategy' && <StrategyTab strategy={strategy} />}
      {activeTab === 'technicals' && <TechnicalsTab technicals={technicals} prices={prices} levels={levels} />}
      {activeTab === 'signals' && <SignalsTab signals={signals} />}
    </div>
  )
}

/* ── Overview Tab ── */
function OverviewTab({ data, levels }) {
  const { prices, performance, strategy, technicals } = data
  const p = performance || {}

  return (
    <>
      {/* KPI Cards */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', marginBottom: '1rem' }}>
        <KpiCard label="현재가" value={p.current_price ? `$${p.current_price.toFixed(2)}` : '-'} />
        <KpiCard label="1일" value={fmtPct(p.change_1d)} color={pctColor(p.change_1d)} />
        <KpiCard label="5일" value={fmtPct(p.change_5d)} color={pctColor(p.change_5d)} />
        <KpiCard label="20일" value={fmtPct(p.change_20d)} color={pctColor(p.change_20d)} />
        <KpiCard label="60일" value={fmtPct(p.change_60d)} color={pctColor(p.change_60d)} />
        <KpiCard label="변동성(20d)" value={p.volatility_20d_ann ? `${p.volatility_20d_ann}%` : '-'} color={p.volatility_20d_ann > 80 ? 'var(--red)' : 'var(--yellow)'} />
        <KpiCard label="RSI" value={technicals?.rsi_14?.toFixed(1) || '-'} color={rsiColor(technicals?.rsi_14)} />
        <KpiCard label="거래량비" value={technicals?.volume_ratio?.toFixed(2) || '-'} />
      </div>

      {/* Price Chart */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ marginBottom: '0.75rem' }}>📈 SOXL 가격 차트 (90일)</h3>
        <ResponsiveContainer width="100%" height={350}>
          <AreaChart data={prices}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} tickFormatter={d => d?.slice(5)} />
            <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 11 }} domain={['auto', 'auto']} />
            <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8 }}
              formatter={(v) => [`$${Number(v).toFixed(2)}`, '']}
              labelFormatter={l => `날짜: ${l}`} />
            {technicals?.ma_20 && <ReferenceLine y={technicals.ma_20} stroke="#ff9800" strokeDasharray="5 5" label={{ value: 'MA20', fill: '#ff9800', fontSize: 10 }} />}
            {technicals?.ma_60 && <ReferenceLine y={technicals.ma_60} stroke="#2196f3" strokeDasharray="5 5" label={{ value: 'MA60', fill: '#2196f3', fontSize: 10 }} />}
            <Area type="monotone" dataKey="close" stroke="var(--accent)" fill="rgba(99,102,241,0.15)" strokeWidth={2} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Levels */}
      {levels && (
        <div className="card-grid" style={{ gridTemplateColumns: '1fr 1fr', marginBottom: '1rem' }}>
          <div className="card">
            <h4>📏 피보나치 레벨</h4>
            <table style={{ width: '100%', fontSize: '0.8rem', marginTop: '0.5rem' }}>
              <tbody>
                {levels.fibonacci && Object.entries(levels.fibonacci).map(([k, v]) => (
                  <tr key={k} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '0.3rem 0', color: 'var(--text-muted)' }}>{k.replace('_', ' ').replace('fib ', 'Fib ')}</td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>${v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="card">
            <h4>📍 피봇 포인트</h4>
            <table style={{ width: '100%', fontSize: '0.8rem', marginTop: '0.5rem' }}>
              <tbody>
                {levels.pivot_points && Object.entries(levels.pivot_points).map(([k, v]) => (
                  <tr key={k} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '0.3rem 0', color: 'var(--text-muted)' }}>{k.toUpperCase()}</td>
                    <td style={{ textAlign: 'right', fontWeight: 600, color: k.startsWith('r') ? 'var(--red)' : k.startsWith('s') ? 'var(--green)' : 'var(--text-primary)' }}>${v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {levels.position && (
              <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                52주 고점 대비: <b style={{ color: 'var(--red)' }}>{levels.position.pct_from_52w_high}%</b> |
                52주 저점 대비: <b style={{ color: 'var(--green)' }}>+{levels.position.pct_from_52w_low}%</b>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Stance summary */}
      {strategy && (
        <div className="card" style={{
          borderLeft: `4px solid ${strategy.stance.includes('BUY') ? '#00e676' : strategy.stance.includes('SELL') ? '#ff1744' : '#ffeb3b'}`,
          marginBottom: '1rem',
        }}>
          <h3>{STANCE_EMOJI[strategy.stance]} 종합 판단: {strategy.stance}</h3>
          <p style={{ color: 'var(--text-secondary)', margin: '0.5rem 0 0' }}>{strategy.stance_desc}</p>
          <div style={{ display: 'flex', gap: '1rem', marginTop: '0.75rem', fontSize: '0.8rem' }}>
            <span style={{ color: 'var(--green)' }}>매수 신호: {strategy.buy_signals}개</span>
            <span style={{ color: 'var(--red)' }}>매도 신호: {strategy.sell_signals}개</span>
          </div>
        </div>
      )}

      {/* Risk Warnings */}
      {strategy?.risk_warnings?.length > 0 && (
        <div className="card" style={{ background: 'rgba(255,23,68,0.05)', borderLeft: '4px solid var(--red)' }}>
          <h4>⚠️ 리스크 경고</h4>
          <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.2rem', fontSize: '0.8rem', lineHeight: 1.8 }}>
            {strategy.risk_warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}
    </>
  )
}

/* ── Strategy Tab ── */
function StrategyTab({ strategy }) {
  if (!strategy) return <div className="loading">전략 데이터 없음</div>

  const rules = strategy.trading_rules || {}
  return (
    <>
      {/* Conditions */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3>📊 현재 지표 상태</h3>
        <div style={{ display: 'grid', gap: '0.5rem', marginTop: '0.75rem' }}>
          {strategy.conditions?.map((c, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: '0.75rem',
              padding: '0.5rem 0.75rem', background: 'var(--bg-secondary)', borderRadius: '0.5rem',
            }}>
              <span style={{
                padding: '0.2rem 0.5rem', borderRadius: '0.25rem', fontSize: '0.7rem', fontWeight: 700, minWidth: '80px', textAlign: 'center',
                background: c.signal.includes('OVER') || c.signal === 'BEARISH' ? 'rgba(255,23,68,0.15)' :
                  c.signal.includes('UNDER') || c.signal === 'BULLISH' ? 'rgba(0,230,118,0.15)' : 'rgba(255,235,59,0.15)',
                color: c.signal.includes('OVER') || c.signal === 'BEARISH' ? '#ff1744' :
                  c.signal.includes('UNDER') || c.signal === 'BULLISH' ? '#00e676' : '#ffeb3b',
              }}>
                {c.indicator}
              </span>
              <span style={{ fontWeight: 600, minWidth: '60px' }}>{typeof c.value === 'number' ? c.value : '-'}</span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{c.desc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Entry Rules */}
      <RuleCard title="🟢 매수 규칙" rules={rules.entry_rules} color="var(--green)" />

      {/* Exit Rules */}
      <RuleCard title="🔴 매도/손절 규칙" rules={rules.exit_rules} color="var(--red)" />

      {/* Position Sizing */}
      <RuleCard title="💰 포지션 사이징" rules={rules.position_sizing} color="var(--accent)" />
    </>
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

/* ── Technicals Tab ── */
function TechnicalsTab({ technicals, prices, levels }) {
  if (!technicals) return <div className="loading">기술적 지표 데이터 없음</div>

  // Build RSI time-series from recent signals if not available in prices
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
      {/* Volume Chart */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3>📊 가격 + 거래량</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={prices.slice(-60)}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} tickFormatter={d => d?.slice(5)} />
            <YAxis yAxisId="price" orientation="right" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} domain={['auto', 'auto']} />
            <YAxis yAxisId="vol" orientation="left" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} tickFormatter={v => `${(v / 1e6).toFixed(0)}M`} />
            <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 8 }} />
            <Bar yAxisId="vol" dataKey="volume" fill="rgba(99,102,241,0.2)" />
            <Line yAxisId="price" type="monotone" dataKey="close" stroke="var(--accent)" dot={false} strokeWidth={2} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Indicator Table */}
      <div className="card">
        <h3>🔧 기술적 지표 상세</h3>
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
      </div>
    </>
  )
}

/* ── Signals Tab ── */
function SignalsTab({ signals }) {
  if (!signals?.length) return <div className="loading">시그널 이력 없음</div>

  return (
    <div className="card">
      <h3>⚡ SOXL 시그널 이력 (최근 30건)</h3>
      <div className="table-container" style={{ marginTop: '0.5rem' }}>
        <table className="table" style={{ width: '100%' }}>
          <thead>
            <tr>
              <th>날짜</th><th>시그널</th><th>점수</th>
              <th>신뢰도</th><th>Hard Limit</th><th>근거</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((s, i) => (
              <tr key={i}>
                <td>{s.date}</td>
                <td>
                  <span className={`badge badge-${(s.final_signal || '').toLowerCase()}`}>
                    {s.final_signal || s.raw_signal || '-'}
                  </span>
                </td>
                <td style={{ fontWeight: 600 }}>{s.raw_score?.toFixed(1) ?? '-'}</td>
                <td>{s.confidence != null ? `${(s.confidence * 100).toFixed(0)}%` : '-'}</td>
                <td>{s.hard_limit ? '🛑' : '-'}</td>
                <td style={{ fontSize: '0.75rem', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {s.rationale || '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ── Helpers ── */
function KpiCard({ label, value, color }) {
  return (
    <div className="card" style={{ textAlign: 'center', padding: '0.75rem 0.5rem' }}>
      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>{label}</div>
      <div style={{ fontSize: '1.1rem', fontWeight: 700, color: color || 'var(--text-primary)' }}>{value ?? '-'}</div>
    </div>
  )
}

function fmtPct(v) { return v != null ? `${v > 0 ? '+' : ''}${v.toFixed(2)}%` : '-' }
function pctColor(v) { return v > 0 ? 'var(--green)' : v < 0 ? 'var(--red)' : 'var(--text-primary)' }
function rsiColor(v) { if (v == null) return 'var(--text-muted)'; return v > 70 ? 'var(--red)' : v < 30 ? 'var(--green)' : 'var(--yellow)' }
function rsiStatus(v) { if (v == null) return '-'; return v > 70 ? '과매수' : v > 60 ? '매수우세' : v < 30 ? '과매도' : v < 40 ? '매도우세' : '중립' }
