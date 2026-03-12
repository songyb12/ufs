import { useState, useEffect, useCallback } from 'react'
import { getCarryTrade, getGlobalRiskFactors } from '../api'
import { useToast } from '../components/Toast'

const RISK_COLORS = {
  HIGH: '#ef4444',
  ELEVATED: '#f97316',
  WATCH: '#eab308',
  LOW: '#22c55e',
}

const RISK_BG = {
  HIGH: 'rgba(239,68,68,0.12)',
  ELEVATED: 'rgba(249,115,22,0.12)',
  WATCH: 'rgba(234,179,8,0.12)',
  LOW: 'rgba(34,197,94,0.12)',
}

function RiskGauge({ score, level, levelKr, label }) {
  const color = RISK_COLORS[level] || '#6b7280'
  const angle = (score / 100) * 180 - 90
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>{label}</div>
      <svg width="120" height="70" viewBox="0 0 120 70">
        <path d="M10,65 A50,50 0 0,1 110,65" fill="none" stroke="var(--border)" strokeWidth="8" strokeLinecap="round" />
        <path d="M10,65 A50,50 0 0,1 110,65" fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={`${(score / 100) * 157} 157`} />
        <line x1="60" y1="65" x2={60 + 35 * Math.cos((angle * Math.PI) / 180)} y2={65 - 35 * Math.sin((angle * Math.PI) / 180)}
          stroke={color} strokeWidth="2.5" strokeLinecap="round" />
        <circle cx="60" cy="65" r="3" fill={color} />
      </svg>
      <div style={{ fontSize: '1.5rem', fontWeight: 700, color }}>{score}</div>
      <div style={{ fontSize: '0.8rem', color, fontWeight: 600 }}>{levelKr}</div>
    </div>
  )
}

function PairCard({ pair }) {
  const ur = pair.unwind_risk || {}
  const riskColor = RISK_COLORS[ur.risk_level] || '#6b7280'
  const riskBg = RISK_BG[ur.risk_level] || 'transparent'

  return (
    <div className="card" style={{ padding: '1rem', borderLeft: `3px solid ${riskColor}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>{pair.label}</div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{pair.description_kr}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ padding: '0.15rem 0.5rem', borderRadius: '0.25rem', background: riskBg, color: riskColor, fontSize: '0.75rem', fontWeight: 600 }}>
            {ur.risk_level_kr || '?'}
          </div>
          {ur.trend_kr && (
            <div style={{ fontSize: '0.65rem', color: ur.trend === 'WORSENING' ? '#ef4444' : ur.trend === 'IMPROVING' ? '#22c55e' : 'var(--text-muted)', marginTop: '0.15rem' }}>
              {ur.trend === 'WORSENING' ? '▲' : ur.trend === 'IMPROVING' ? '▼' : '●'} {ur.trend_kr}
            </div>
          )}
        </div>
      </div>

      {/* Rate comparison */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', fontSize: '0.75rem' }}>
        <span style={{ color: 'var(--text-muted)' }}>{pair.funding}</span>
        <span style={{ fontWeight: 700, color: '#3b82f6' }}>{pair.funding_rate != null ? `${pair.funding_rate}%` : '?'}</span>
        <span style={{ color: 'var(--text-muted)' }}>{'→'}</span>
        <span style={{ color: 'var(--text-muted)' }}>{pair.investing}</span>
        <span style={{ fontWeight: 700, color: '#a855f7' }}>{pair.investing_rate != null ? `${pair.investing_rate}%` : '?'}</span>
        <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: '0.7rem' }}>
          {pair.rate_differential != null ? `차이 ${pair.rate_differential}%p` : ''}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', marginBottom: '0.75rem' }}>
        <Metric label="금리차" value={pair.rate_differential != null ? `${pair.rate_differential}%p` : 'N/A'} />
        <Metric label="캐리 매력" value={pair.carry_score} suffix="/100" color={pair.carry_score > 60 ? '#22c55e' : pair.carry_score < 40 ? '#ef4444' : '#eab308'} />
        <Metric label="청산위험" value={ur.risk_score} suffix="/100" color={riskColor} />
        <Metric label="환율" value={pair.fx_current ? pair.fx_current.toLocaleString() : 'N/A'} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '0.75rem' }}>
        <FxChange label="1일" value={pair.fx_change_1d_pct} />
        <FxChange label="1주" value={pair.fx_change_1w_pct} />
        <FxChange label="1개월" value={pair.fx_change_1m_pct} />
      </div>

      {ur.signals && ur.signals.length > 0 && (
        <div style={{ background: riskBg, borderRadius: '0.375rem', padding: '0.5rem 0.75rem' }}>
          {ur.signals.map((s, i) => (
            <div key={i} style={{ fontSize: '0.75rem', color: riskColor, marginBottom: i < ur.signals.length - 1 ? '0.25rem' : 0 }}>
              {s}
            </div>
          ))}
        </div>
      )}

      {/* Carry score bar */}
      <div style={{ marginTop: '0.5rem', marginBottom: '0.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '0.15rem' }}>
          <span>캐리 매력도</span>
          <span>{pair.carry_score}/100</span>
        </div>
        <div style={{ height: '5px', background: 'var(--border)', borderRadius: '3px' }}>
          <div style={{
            width: `${pair.carry_score}%`,
            height: '100%',
            borderRadius: '3px',
            background: pair.carry_score > 60 ? '#22c55e' : pair.carry_score < 40 ? '#ef4444' : '#eab308',
            transition: 'width 0.3s',
          }} />
        </div>
      </div>

      {pair.market_impact?.impacts?.length > 0 && (
        <div style={{ marginTop: '0.5rem' }}>
          <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.25rem' }}>시장 영향</div>
          {pair.market_impact.impacts.map((imp, i) => (
            <div key={i} style={{ fontSize: '0.72rem', color: imp.direction === 'negative' ? '#ef4444' : '#22c55e', marginBottom: '0.15rem' }}>
              [{imp.market}] {imp.reason_kr}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Metric({ label, value, suffix = '', color }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>{label}</div>
      <div style={{ fontSize: '1rem', fontWeight: 700, color: color || 'var(--text-primary)' }}>
        {value}{suffix && <span style={{ fontSize: '0.65rem', fontWeight: 400 }}>{suffix}</span>}
      </div>
    </div>
  )
}

function FxChange({ label, value }) {
  const v = value || 0
  const color = v > 0 ? '#ef4444' : v < 0 ? '#22c55e' : 'var(--text-muted)'
  return (
    <div style={{ textAlign: 'center', padding: '0.25rem', background: 'var(--bg-secondary)', borderRadius: '0.25rem' }}>
      <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>{label}</div>
      <div style={{ fontSize: '0.85rem', fontWeight: 600, color }}>{v > 0 ? '+' : ''}{v.toFixed(2)}%</div>
    </div>
  )
}

function RiskFactorCard({ factor }) {
  const color = RISK_COLORS[factor.severity] || '#6b7280'
  const bg = RISK_BG[factor.severity] || 'transparent'

  return (
    <div className="card" style={{ padding: '0.75rem 1rem', borderLeft: `3px solid ${color}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>{factor.name_kr}</span>
        <span style={{ padding: '0.1rem 0.5rem', borderRadius: '0.25rem', background: bg, color, fontSize: '0.72rem', fontWeight: 600 }}>
          {factor.severity_kr} ({factor.score})
        </span>
      </div>
      <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '0.35rem' }}>{factor.description_kr}</div>
      <div style={{ fontSize: '0.72rem', color, marginBottom: '0.2rem' }}>{factor.market_impact_kr}</div>
      <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>트리거: {factor.trigger_kr}</div>
    </div>
  )
}

export default function CarryTrade({ refreshKey, onNavigate }) {
  const toast = useToast()
  const [carry, setCarry] = useState(null)
  const [riskFactors, setRiskFactors] = useState([])
  const [loading, setLoading] = useState(true)

  const loadData = useCallback(() => {
    setLoading(true)
    Promise.all([
      getCarryTrade().catch(() => null),
      getGlobalRiskFactors().catch(() => []),
    ])
      .then(([c, rf]) => {
        setCarry(c)
        setRiskFactors(rf?.factors || (Array.isArray(rf) ? rf : []))
      })
      .catch(err => toast.error('Load failed: ' + err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData, refreshKey])

  if (loading) {
    return <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading carry trade data...</div>
  }

  const overall = carry?.overall_risk || {}
  const pairs = carry?.pairs || []

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h2>Carry Trade & Global Risk</h2>
        {carry?.date && <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Data: {carry.date}</span>}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', margin: 0 }}>
          캐리 트레이드 위험 분석 및 글로벌 금융시장 리스크 요인
        </p>
        {onNavigate && (
          <button
            className="btn btn-outline"
            onClick={() => onNavigate('forex-map')}
            style={{ fontSize: '0.72rem', padding: '0.25rem 0.6rem' }}
          >
            {'🗺'} 환율 세계지도
          </button>
        )}
      </div>

      {/* Overall Risk Summary */}
      <div className="card" style={{ padding: '1.25rem', marginBottom: '1.25rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '1.5rem', alignItems: 'center' }}>
          <RiskGauge
            score={overall.score || 0}
            level={overall.level || 'LOW'}
            levelKr={overall.level_kr || '양호'}
            label="캐리 트레이드 종합 위험도"
          />
          <div>
            <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '0.75rem' }}>
              <Metric label="VIX" value={carry?.vix?.toFixed(1) || 'N/A'} color={carry?.vix > 25 ? '#ef4444' : carry?.vix > 20 ? '#eab308' : '#22c55e'} />
              <Metric label="DXY" value={carry?.dxy?.toFixed(1) || 'N/A'} color={carry?.dxy > 105 ? '#ef4444' : '#6b7280'} />
            </div>
            {overall.scenario_kr && (
              <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '0.5rem', fontStyle: 'italic' }}>
                {overall.scenario_kr}
              </div>
            )}
            {overall.advice && overall.advice.length > 0 && (
              <div style={{ background: RISK_BG[overall.level] || 'var(--bg-secondary)', borderRadius: '0.375rem', padding: '0.5rem 0.75rem' }}>
                {overall.advice.map((a, i) => (
                  <div key={i} style={{ fontSize: '0.78rem', color: RISK_COLORS[overall.level] || 'var(--text-secondary)', marginBottom: i < overall.advice.length - 1 ? '0.3rem' : 0 }}>
                    {a}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Risk Comparison */}
      {pairs.length > 0 && (
        <div className="card" style={{ padding: '1rem', marginBottom: '1.25rem' }}>
          <h3 style={{ fontSize: '0.95rem', marginBottom: '0.75rem' }}>페어별 위험도 비교</h3>
          {pairs.map(p => {
            const ur = p.unwind_risk || {}
            const color = RISK_COLORS[ur.risk_level] || '#6b7280'
            return (
              <div key={p.pair_id} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                <span style={{ width: '140px', fontSize: '0.78rem', flexShrink: 0 }}>{p.label}</span>
                <div style={{ flex: 1, height: '18px', background: 'var(--bg-secondary)', borderRadius: '9px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${Math.max(ur.risk_score || 0, 3)}%`,
                    height: '100%',
                    background: color,
                    borderRadius: '9px',
                    transition: 'width 0.4s ease',
                  }} />
                </div>
                <span style={{ width: '30px', fontSize: '0.75rem', fontWeight: 700, color, textAlign: 'right' }}>{ur.risk_score || 0}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* Carry Pairs */}
      <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>캐리 트레이드 페어 분석</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '0.75rem', marginBottom: '1.5rem' }}>
        {pairs.map(p => <PairCard key={p.pair_id} pair={p} />)}
      </div>

      {/* Global Risk Factors */}
      {riskFactors.length > 0 && (
        <>
          <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem' }}>글로벌 리스크 요인</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '0.75rem' }}>
            {riskFactors.map((f, i) => <RiskFactorCard key={f.factor || i} factor={f} />)}
          </div>
        </>
      )}

      {riskFactors.length === 0 && (
        <div className="card" style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
          현재 감지된 글로벌 리스크 요인 없음 (시장 안정)
        </div>
      )}

      {/* Interest Rates */}
      {carry?.interest_rates && Object.keys(carry.interest_rates).length > 0 && (
        <div className="card" style={{ padding: '1rem', marginTop: '1.25rem' }}>
          <h3 style={{ fontSize: '0.95rem', marginBottom: '0.75rem' }}>주요국 기준금리</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {Object.entries(carry.interest_rates)
              .filter(([, v]) => v != null && typeof v === 'number')
              .sort(([,a], [,b]) => b - a)
              .slice(0, 15)
              .map(([cur, rate]) => (
                <div key={cur} style={{
                  padding: '0.35rem 0.6rem', borderRadius: '0.25rem',
                  background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                  fontSize: '0.75rem',
                }}>
                  <span style={{ fontWeight: 700 }}>{cur}</span>{' '}
                  <span style={{ color: rate > 4 ? '#ef4444' : rate < 1 ? '#22c55e' : '#3b82f6' }}>
                    {rate.toFixed(2)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
