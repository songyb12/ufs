import { useState, useEffect, useCallback } from 'react'
import { getMacroRegime, getStagflation, getCrossMarket, getMacroTrends,
  getMarketSeason, getInvestmentClock, getYieldPhase, getUnifiedRiskScore,
  getFearGauge, getEntryScenarios, getSectorMacroImpact,
  getCapitulationScan, getCrisisHedge } from '../api'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, BarChart, Bar, Cell
} from 'recharts'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import { useToast } from '../components/Toast'

const REGIME_COLORS = {
  'Risk-On': '#22c55e', 'Risk-Off': '#ef4444', 'Panic': '#dc2626', 'Complacent': '#eab308',
}
const STAG_COLORS = { 'Low': '#22c55e', 'Watch': '#eab308', 'Elevated': '#f97316', 'High': '#ef4444' }
const REC_COLORS = {
  'KR Favorable': '#3b82f6', 'US Favorable': '#a855f7', 'Both OK': '#22c55e', 'Caution': '#ef4444',
}
const RISK_LEVEL_COLORS = {
  'Low': '#22c55e', 'Moderate': '#3b82f6', 'Elevated': '#f97316', 'High': '#ef4444', 'Critical': '#dc2626',
}
const YIELD_PHASE_COLORS = {
  'Normal': '#22c55e', 'Flattening': '#eab308', 'Inverted': '#ef4444',
  'Normalizing': '#dc2626', 'Transitioning': '#3b82f6', 'Unknown': '#64748b',
}
const FEAR_PHASE_COLORS = {
  'Calm': '#22c55e', 'Initial Panic': '#f59e0b', 'Peak Fear': '#ef4444', 'Post-Peak': '#3b82f6',
}
const FEAR_PHASE_ICONS = {
  'Calm': '\u{1F7E2}', 'Initial Panic': '\u{1F7E1}', 'Peak Fear': '\u{1F534}', 'Post-Peak': '\u{1F535}',
}

export default function Macro({ onNavigate, refreshKey }) {
  const toast = useToast()
  const [regime, setRegime] = useState(null)
  const [stagflation, setStagflation] = useState(null)
  const [crossMarket, setCrossMarket] = useState(null)
  const [trends, setTrends] = useState([])
  const [season, setSeason] = useState(null)
  const [clock, setClock] = useState(null)
  const [yieldPhase, setYieldPhase] = useState(null)
  const [riskScore, setRiskScore] = useState(null)
  const [fearGauge, setFearGauge] = useState(null)
  const [entryScenarios, setEntryScenarios] = useState(null)
  const [sectorImpact, setSectorImpact] = useState(null)
  const [capitulation, setCapitulation] = useState(null)
  const [crisisHedge, setCrisisHedge] = useState(null)
  const [loading, setLoading] = useState(true)
  const [trendDays, setTrendDays] = useState(30)

  const loadData = useCallback(() => {
    setLoading(true)
    return Promise.all([
      getMacroRegime().catch(() => null),
      getStagflation().catch(() => null),
      getCrossMarket().catch(() => null),
      getMarketSeason().catch(() => null),
      getInvestmentClock().catch(() => null),
      getYieldPhase().catch(() => null),
      getUnifiedRiskScore().catch(() => null),
      getFearGauge().catch(() => null),
      getEntryScenarios().catch(() => null),
      getSectorMacroImpact().catch(() => null),
      getCapitulationScan('KR').catch(() => null),
      getCrisisHedge(20).catch(() => null),
    ])
      .then(([r, s, cm, sea, clk, yp, rs, fg, es, si, cap, hedge]) => {
        setRegime(r); setStagflation(s); setCrossMarket(cm)
        setSeason(sea); setClock(clk); setYieldPhase(yp); setRiskScore(rs)
        setFearGauge(fg); setEntryScenarios(es); setSectorImpact(si)
        setCapitulation(cap); setCrisisHedge(hedge)
      })
      .catch(err => toast.error('Load failed: ' + err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData, refreshKey])

  // Fetch trends separately so changing trendDays doesn't reload all 12 other APIs
  useEffect(() => {
    getMacroTrends(trendDays).catch(() => ({ trends: [] }))
      .then(t => setTrends(t?.trends || []))
  }, [trendDays, refreshKey])

  if (loading) return <div className="loading"><span className="spinner" /> 로딩 중...</div>

  const risk = regime?.risk_regime || {}
  const driver = regime?.driver_regime || {}
  const stag = stagflation || {}
  const cm = crossMarket || {}

  // Radar chart data for cross-market comparison
  const radarData = cm.factors ? Object.entries(cm.factors).map(([key, f]) => ({
    factor: key === 'fx_trend' ? 'FX' : key === 'volatility' ? 'VIX' : key === 'yield_env' ? 'Yield' : key === 'fund_flow' ? 'Flow' : 'Signal',
    KR: Math.round(((f.kr_impact || 0) + 1) * 50),
    US: Math.round(((f.us_impact || 0) + 1) * 50),
  })) : []

  // Stagflation component bar data
  const stagBars = stag.components ? Object.entries(stag.components).map(([key, c]) => ({
    name: key === 'gold_copper_ratio' ? 'Gold/Copper' : key === 'yield_curve' ? 'Yield Curve' : key === 'oil_pressure' ? 'Oil' : key === 'dxy_tightening' ? 'DXY' : 'Copper',
    score: c.score || 0,
    weight: (c.weight || 0) * 100,
  })) : []

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'\uD83C\uDF10'} 매크로 인텔리전스</h2>
          <p className="subtitle">시장 레짐, 스태그플레이션 모니터링, 교차시장 분석</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button className="btn btn-outline" onClick={loadData}>{'\u21BB'} Refresh</button>
          <HelpButton section="macro" onNavigate={onNavigate} />
        </div>
      </div>

      <PageGuide
        pageId="macro"
        title="이 페이지에서 확인할 것"
        steps={[
          'Market Season → 지금 봄/여름/가을/겨울 중 어디?',
          '리스크 점수 → 60 이상이면 방어 모드 전환 고려',
          'Fear Gauge → Peak Fear 시 역발상 매수 기회',
          'Entry Scenarios → KOSPI/SPY 지지·저항 참조선',
        ]}
        color="#f59e0b"
      />

      {/* Quick navigation to related pages */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button
          className="btn btn-outline"
          onClick={() => onNavigate('carry-trade')}
          style={{ fontSize: '0.75rem', padding: '0.3rem 0.75rem' }}
        >
          {'\uD83D\uDCB1'} 캐리트레이드 분석
        </button>
        <button
          className="btn btn-outline"
          onClick={() => onNavigate('forex-map')}
          style={{ fontSize: '0.75rem', padding: '0.3rem 0.75rem' }}
        >
          {'\uD83D\uDDFA'} 환율 세계지도
        </button>
      </div>

      {/* ── Phase J: Market Season + Investment Clock + Yield Phase + Risk Score ── */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: '1rem' }}>
        {/* Market Season */}
        <div className="card" style={{ borderLeft: '3px solid #f59e0b', textAlign: 'center' }}>
          <div className="card-label">Market Season</div>
          <div style={{ fontSize: '2rem', lineHeight: 1.2 }}>{season?.icon || '\u2753'}</div>
          <div className="card-value" style={{ fontSize: '1.1rem', color: '#f59e0b' }}>
            {season?.season_kr || '-'}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            {season?.season || '-'} / Conf: {season?.confidence ?? '-'}
          </div>
          {season?.strategy_kr && (
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.3rem',
              padding: '0.2rem 0.4rem', background: 'rgba(245,158,11,0.08)', borderRadius: '4px' }}>
              {season.strategy_kr}
            </div>
          )}
          {season?.season_hint && (
            <div style={{ fontSize: '0.65rem', color: '#f59e0b', marginTop: '0.25rem' }}>
              {'\u2139\uFE0F'} 추정: {season.season_hint_kr || season.season_hint}
            </div>
          )}
          {season?.data_days != null && season.data_days < 20 && (
            <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
              데이터 {season.data_days}일 (20일 미만 — 신뢰도 제한)
            </div>
          )}
        </div>

        {/* Investment Clock */}
        <div className="card" style={{ borderLeft: `3px solid ${clock?.color || '#64748b'}`, textAlign: 'center' }}>
          <div className="card-label">Investment Clock</div>
          <div className="card-value" style={{ fontSize: '1.1rem', color: clock?.color || 'var(--text-primary)' }}>
            {clock?.quadrant_kr || '-'}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            성장: {clock?.growth_score ?? '-'} / 인플레: {clock?.inflation_score ?? '-'}
          </div>
          {clock?.asset_kr && (
            <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.3rem',
              padding: '0.2rem 0.4rem', background: `${clock?.color || '#3b82f6'}12`, borderRadius: '4px' }}>
              {clock.asset_kr}
            </div>
          )}
        </div>

        {/* Yield Phase */}
        <div className="card" style={{ borderLeft: `3px solid ${YIELD_PHASE_COLORS[yieldPhase?.phase] || '#64748b'}`, textAlign: 'center' }}>
          <div className="card-label">Yield Curve Phase</div>
          <div className="card-value" style={{
            fontSize: '1.1rem',
            color: YIELD_PHASE_COLORS[yieldPhase?.phase] || 'var(--text-primary)',
          }}>
            {yieldPhase?.phase_kr || '-'}
            {yieldPhase?.risk_flag && <span style={{ marginLeft: '0.3rem' }}>{'\u26A0\uFE0F'}</span>}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Spread: {yieldPhase?.current_spread ?? '-'}% / {yieldPhase?.trend || '-'}
          </div>
        </div>

        {/* Unified Risk Score */}
        <div className="card" style={{
          borderLeft: `3px solid ${RISK_LEVEL_COLORS[riskScore?.level] || '#64748b'}`,
          textAlign: 'center',
        }}>
          <div className="card-label">Macro Risk Score</div>
          <div className="card-value" style={{
            fontSize: '1.8rem',
            color: RISK_LEVEL_COLORS[riskScore?.level] || 'var(--text-primary)',
          }}>
            {riskScore?.score ?? '-'}
          </div>
          <div className="card-sub">{riskScore?.level_kr || '-'}</div>
          <div style={{ marginTop: '0.4rem', background: '#334155', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
            <div style={{
              width: `${Math.min(100, riskScore?.score || 0)}%`,
              height: '100%',
              borderRadius: '4px',
              background: RISK_LEVEL_COLORS[riskScore?.level] || '#64748b',
              transition: 'width 0.5s',
            }} />
          </div>
        </div>
      </div>

      {/* ── Phase K: Fear Gauge + Entry Scenarios ── */}
      {(fearGauge || entryScenarios) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem', marginBottom: '1rem' }}>
          {/* Fear Gauge Card */}
          {fearGauge && (
            <div className="card" style={{ borderLeft: `3px solid ${FEAR_PHASE_COLORS[fearGauge.phase] || '#64748b'}`, textAlign: 'center' }}>
              <div className="card-label">Fear Gauge</div>
              <div style={{ fontSize: '2rem', lineHeight: 1.2 }}>
                {FEAR_PHASE_ICONS[fearGauge.phase] || '\u2753'}
              </div>
              <div className="card-value" style={{
                fontSize: '1.1rem',
                color: FEAR_PHASE_COLORS[fearGauge.phase] || 'var(--text-primary)',
              }}>
                {fearGauge.phase_kr || fearGauge.phase || '-'}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                Conf: {((fearGauge.confidence ?? 0) * 100).toFixed(0)}%
              </div>
              {fearGauge.metrics && (
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.5rem',
                  display: 'flex', flexDirection: 'column', gap: '0.15rem', textAlign: 'left' }}>
                  <span>VIX: {fearGauge.metrics.vix_current?.toFixed(1) ?? '-'} (vel: {fearGauge.metrics.vix_velocity_5d?.toFixed(1) ?? '-'}%)</span>
                  <span>F&G: {fearGauge.metrics.fg_current ?? '-'} (mom: {fearGauge.metrics.fg_momentum_5d?.toFixed(1) ?? '-'})</span>
                  <span>P/C Spike: {fearGauge.metrics.put_call_spike ? 'Yes' : 'No'} / Backwd: {fearGauge.metrics.backwardation_streak ?? 0}d</span>
                </div>
              )}
              {fearGauge.action_kr && (
                <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.5rem',
                  padding: '0.3rem 0.4rem', background: `${FEAR_PHASE_COLORS[fearGauge.phase] || '#64748b'}12`,
                  borderRadius: '4px', textAlign: 'left' }}>
                  {fearGauge.action_kr}
                </div>
              )}
            </div>
          )}

          {/* Entry Scenarios Table */}
          {entryScenarios && (
            <div className="card">
              <h3 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>Entry Scenarios (MA Reference)</h3>
              {entryScenarios.probability_bias && (
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                  Probability Bias: <strong style={{
                    color: entryScenarios.probability_bias === 'worst' ? '#ef4444'
                      : entryScenarios.probability_bias === 'best' ? '#22c55e' : '#eab308'
                  }}>{entryScenarios.probability_bias.toUpperCase()}</strong>
                </div>
              )}
              <table style={{ fontSize: '0.8rem' }}>
                <thead>
                  <tr>
                    <th>Scenario</th>
                    <th>KOSPI</th>
                    <th>SPY</th>
                    <th>USD/KRW</th>
                  </tr>
                </thead>
                <tbody>
                  {['best', 'base', 'worst'].map(s => {
                    const sc = entryScenarios.scenarios?.[s]
                    const scColor = s === 'best' ? '#22c55e' : s === 'worst' ? '#ef4444' : '#eab308'
                    return (
                      <tr key={s}>
                        <td style={{ fontWeight: 600, color: scColor }}>
                          {s === 'best' ? 'Best (MA20)' : s === 'base' ? 'Base (MA60)' : 'Worst (MA120)'}
                        </td>
                        <td>{sc?.kospi ? `${sc.kospi.toFixed(0)}` : '-'}</td>
                        <td>{sc?.spy ? `$${sc.spy.toFixed(1)}` : '-'}</td>
                        <td>{sc?.usd_krw ? `${sc.usd_krw.toFixed(0)}` : '-'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              {/* Benchmark MA details */}
              {entryScenarios.benchmarks && (
                <div style={{ marginTop: '0.5rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                  {Object.entries(entryScenarios.benchmarks).map(([name, b]) => (
                    <div key={name} style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                      <strong>{name}</strong>: MA20={b.ma20?.toFixed(1) ?? '-'} / MA60={b.ma60?.toFixed(1) ?? '-'} / MA120={b.ma120?.toFixed(1) ?? '-'}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Sector-Macro Impact */}
      {sectorImpact?.sectors?.length > 0 && (
        <div className="table-container" style={{ marginBottom: '1rem' }}>
          <div className="table-header">
            <h3>Sector-Macro Cross Impact</h3>
          </div>
          <table style={{ fontSize: '0.8rem' }}>
            <thead>
              <tr>
                <th>Sector</th>
                <th>Adjustment</th>
                <th>Oil</th>
                <th>Rate</th>
                <th>FX</th>
                <th>DXY</th>
                <th>Warnings</th>
              </tr>
            </thead>
            <tbody>
              {sectorImpact.sectors.filter(s => s.adjustment_score !== 0).slice(0, 12).map((s, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600 }}>{s.sector}</td>
                  <td style={{
                    fontWeight: 700,
                    color: s.adjustment_score > 0 ? 'var(--green)' : s.adjustment_score < 0 ? 'var(--red)' : 'var(--text-muted)',
                  }}>
                    {s.adjustment_score > 0 ? '+' : ''}{s.adjustment_score.toFixed(1)}
                  </td>
                  <td style={{ color: (s.factors?.oil?.contribution || 0) > 0 ? 'var(--green)' : (s.factors?.oil?.contribution || 0) < 0 ? 'var(--red)' : 'var(--text-muted)' }}>
                    {(s.factors?.oil?.contribution || 0).toFixed(1)}
                  </td>
                  <td style={{ color: (s.factors?.rate?.contribution || 0) > 0 ? 'var(--green)' : (s.factors?.rate?.contribution || 0) < 0 ? 'var(--red)' : 'var(--text-muted)' }}>
                    {(s.factors?.rate?.contribution || 0).toFixed(1)}
                  </td>
                  <td style={{ color: (s.factors?.fx?.contribution || 0) > 0 ? 'var(--green)' : (s.factors?.fx?.contribution || 0) < 0 ? 'var(--red)' : 'var(--text-muted)' }}>
                    {(s.factors?.fx?.contribution || 0).toFixed(1)}
                  </td>
                  <td style={{ color: (s.factors?.dxy?.contribution || 0) > 0 ? 'var(--green)' : (s.factors?.dxy?.contribution || 0) < 0 ? 'var(--red)' : 'var(--text-muted)' }}>
                    {(s.factors?.dxy?.contribution || 0).toFixed(1)}
                  </td>
                  <td style={{ fontSize: '0.7rem', color: 'var(--text-muted)', maxWidth: '200px' }}>
                    {(s.warnings || []).join('; ') || '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Phase K: Capitulation Scan + Crisis Hedge ── */}
      {(capitulation?.candidates?.length > 0 || crisisHedge?.hedge_candidates?.length > 0) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
          {/* Capitulation Scan */}
          {capitulation?.candidates?.length > 0 && (
            <div className="card" style={{ borderLeft: '3px solid #ef4444' }}>
              <h3 style={{ fontSize: '0.85rem', marginBottom: '0.5rem', color: '#ef4444' }}>
                {'\uD83D\uDCA5'} Capitulation Detected ({capitulation.count})
              </h3>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                Volume spike + price drop = panic selling candidates
              </div>
              <table style={{ fontSize: '0.8rem' }}>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Volume Ratio</th>
                    <th>Price Chg</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {capitulation.candidates.slice(0, 8).map((c, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600 }}>{c.symbol}</td>
                      <td>{c.trigger_value ? `${Number(c.trigger_value).toFixed(1)}x` : '-'}</td>
                      <td style={{ color: 'var(--red)' }}>
                        {c.trigger_description?.match(/-[\d.]+%/)?.[0] || '-'}
                      </td>
                      <td style={{ fontSize: '0.7rem' }}>{c.detected_date?.slice(5) || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Crisis Hedge Candidates */}
          {crisisHedge?.hedge_candidates?.length > 0 && (
            <div className="card" style={{ borderLeft: '3px solid #3b82f6' }}>
              <h3 style={{ fontSize: '0.85rem', marginBottom: '0.5rem', color: '#3b82f6' }}>
                {'\uD83D\uDEE1\uFE0F'} Crisis Hedge Candidates
              </h3>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                Defense sectors with RS {'>'} 1.0 during {crisisHedge.risk_regime || 'risk-off'}
              </div>
              <table style={{ fontSize: '0.8rem' }}>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Sector</th>
                    <th>RS</th>
                    <th>Return</th>
                  </tr>
                </thead>
                <tbody>
                  {crisisHedge.hedge_candidates.slice(0, 8).map((h, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600 }}>{h.symbol}</td>
                      <td style={{ fontSize: '0.7rem' }}>{h.sector}</td>
                      <td style={{ color: h.rs > 1 ? 'var(--green)' : 'var(--text-muted)', fontWeight: 600 }}>
                        {h.rs?.toFixed(3) || '-'}
                      </td>
                      <td style={{ color: (h.return_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                        {h.return_pct != null ? `${h.return_pct >= 0 ? '+' : ''}${h.return_pct.toFixed(1)}%` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Investment Clock Detail + Season Axes */}
      {(clock || season) && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
          {/* Investment Clock Quadrant Visualization */}
          {clock && (
            <div className="card">
              <h3 style={{ fontSize: '0.85rem', marginBottom: '0.75rem' }}>Investment Clock</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px', maxWidth: '280px', margin: '0 auto' }}>
                {[
                  { key: 'recovery', label: 'Recovery', kr: '\uD68C\uBCF5', pos: 'growth\u2191 inflation\u2193', color: '#22c55e' },
                  { key: 'overheat', label: 'Overheat', kr: '\uACFC\uC5F4', pos: 'growth\u2191 inflation\u2191', color: '#f59e0b' },
                  { key: 'reflation', label: 'Reflation', kr: '\uD658\uAE30', pos: 'growth\u2193 inflation\u2193', color: '#3b82f6' },
                  { key: 'stagflation', label: 'Stagflation', kr: '\uCE68\uCCB4', pos: 'growth\u2193 inflation\u2191', color: '#ef4444' },
                ].map(q => {
                  const isActive = clock.quadrant?.toLowerCase() === q.key
                  return (
                    <div key={q.key} style={{
                      padding: '0.75rem 0.5rem',
                      background: isActive ? `${q.color}20` : '#1e293b',
                      border: isActive ? `2px solid ${q.color}` : '1px solid #334155',
                      borderRadius: '6px',
                      textAlign: 'center',
                    }}>
                      <div style={{ fontWeight: 700, fontSize: '0.85rem', color: isActive ? q.color : 'var(--text-muted)' }}>
                        {q.kr}
                      </div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>{q.pos}</div>
                    </div>
                  )
                })}
              </div>
              {clock.description_kr && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.75rem', textAlign: 'center' }}>
                  {clock.description_kr}
                </div>
              )}
            </div>
          )}

          {/* Season Axes Breakdown */}
          {season && season.axes && (
            <div className="card">
              <h3 style={{ fontSize: '0.85rem', marginBottom: '0.75rem' }}>Season Axes</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {/* Rate Axis */}
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                    Rate Direction: <strong style={{ color: season.axes?.rate_direction === 'falling' ? '#22c55e' : season.axes?.rate_direction === 'rising' ? '#ef4444' : '#eab308' }}>
                      {season.axes?.rate_direction || '-'}
                    </strong>
                    <span style={{ marginLeft: '0.5rem' }}>({((season.axes?.rate_momentum ?? 0) * 100).toFixed(1)}%)</span>
                  </div>
                  <div style={{ background: '#334155', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
                    <div style={{
                      width: `${Math.min(100, Math.abs(season.axes?.rate_momentum ?? 0) * 500)}%`,
                      height: '100%',
                      borderRadius: '4px',
                      background: season.axes?.rate_direction === 'falling' ? '#22c55e' : season.axes?.rate_direction === 'rising' ? '#ef4444' : '#eab308',
                    }} />
                  </div>
                </div>
                {/* Growth Proxy */}
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                    Growth Proxy: <strong style={{ color: season.axes?.growth_direction === 'improving' ? '#22c55e' : season.axes?.growth_direction === 'deteriorating' ? '#ef4444' : '#eab308' }}>
                      {season.axes?.growth_direction || '-'}
                    </strong>
                    <span style={{ marginLeft: '0.5rem' }}>({((season.axes?.growth_proxy ?? 0) * 100).toFixed(1)}%)</span>
                  </div>
                  <div style={{ background: '#334155', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
                    <div style={{
                      width: `${Math.min(100, Math.abs(season.axes?.growth_proxy ?? 0) * 500)}%`,
                      height: '100%',
                      borderRadius: '4px',
                      background: season.axes?.growth_direction === 'improving' ? '#22c55e' : season.axes?.growth_direction === 'deteriorating' ? '#ef4444' : '#eab308',
                    }} />
                  </div>
                </div>
                {/* Component breakdown */}
                {season.axes?.components && (
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <span>Copper: {((season.axes.components?.copper_momentum ?? 0) * 100).toFixed(1)}%</span>
                    <span>ETF: {((season.axes.components?.etf_momentum ?? 0) * 100).toFixed(1)}%</span>
                    <span>KR Flow: {((season.axes.components?.kr_flow_momentum ?? 0) * 100).toFixed(1)}%</span>
                  </div>
                )}
              </div>
              {season.description_kr && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.75rem',
                  padding: '0.4rem', background: 'rgba(245,158,11,0.06)', borderRadius: '4px' }}>
                  {season.description_kr}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Market Season Cycle Guide */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h3 style={{ fontSize: '0.85rem', marginBottom: '0.75rem' }}>{'\uD83D\uDD04'} 시장 사이클 가이드 (우라가미 쿠니오)</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem' }}>
          {[
            { key: 'spring', icon: '\uD83C\uDF31', kr: '금융장세', en: 'Spring', desc: '금리 하락 + 경기 회복 초기\n유동성 확대로 주식 강세 시작', strategy: '주식 비중 확대, 성장주 중심', color: '#22c55e', axes: '금리\u2193 성장\u2191' },
            { key: 'summer', icon: '\u2600\uFE0F', kr: '실적장세', en: 'Summer', desc: '금리 상승 시작이나 실적 개선이 더 강함\n실적 우량주 강세', strategy: '실적 우량주 선별, 섹터 로테이션', color: '#f59e0b', axes: '금리\u2191 성장\u2191' },
            { key: 'autumn', icon: '\uD83C\uDF42', kr: '역금융장세', en: 'Autumn', desc: '금리 고점/상승 지속 + 성장 둔화\n밸류에이션 부담 증가', strategy: '비중 축소, 방어주 전환, 현금 확대', color: '#ef4444', axes: '금리\u2191 성장\u2193' },
            { key: 'winter', icon: '\u2744\uFE0F', kr: '역실적장세', en: 'Winter', desc: '금리 하락 시작이나 실적 악화 지속\n본격적 하락장', strategy: '현금/채권 극대화, 역발상 매수 준비', color: '#3b82f6', axes: '금리\u2193 성장\u2193' },
          ].map(s => {
            const isCurrent = season?.season?.toLowerCase() === s.key
            return (
              <div key={s.key} style={{
                padding: '0.75rem', borderRadius: '8px', position: 'relative',
                background: isCurrent ? `${s.color}15` : '#1e293b',
                border: isCurrent ? `2px solid ${s.color}` : '1px solid #334155',
              }}>
                {isCurrent && (
                  <div style={{ position: 'absolute', top: '-8px', right: '8px', fontSize: '0.6rem', fontWeight: 700,
                    color: s.color, background: 'var(--bg-secondary)', padding: '0 4px', borderRadius: '4px' }}>
                    현재
                  </div>
                )}
                <div style={{ textAlign: 'center', marginBottom: '0.3rem' }}>
                  <span style={{ fontSize: '1.5rem' }}>{s.icon}</span>
                </div>
                <div style={{ textAlign: 'center', fontWeight: 700, fontSize: '0.9rem', color: isCurrent ? s.color : 'var(--text-primary)' }}>
                  {s.kr}
                </div>
                <div style={{ textAlign: 'center', fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                  {s.en} · {s.axes}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', lineHeight: 1.5, whiteSpace: 'pre-line', marginBottom: '0.4rem' }}>
                  {s.desc}
                </div>
                <div style={{ fontSize: '0.65rem', color: s.color, padding: '0.2rem 0.3rem', background: `${s.color}08`, borderRadius: '4px' }}>
                  전략: {s.strategy}
                </div>
              </div>
            )
          })}
        </div>
        <div style={{ textAlign: 'center', marginTop: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
          봄 → 여름 → 가을 → 겨울 → 봄 (순환) · 우라가미 쿠니오(浦上邦雄) 모델 기반
        </div>
      </div>

      {/* Summary Cards */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        {/* Regime Card */}
        <div className="card" style={{ borderLeft: `3px solid ${REGIME_COLORS[risk.regime] || '#64748b'}` }}>
          <div className="card-label">Market Regime</div>
          <div className="card-value" style={{ color: REGIME_COLORS[risk.regime] || 'var(--text-primary)', fontSize: '1.3rem' }}>
            {risk.regime_kr || '-'}
          </div>
          <div className="card-sub">{driver.driver_kr || '-'}</div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Risk Score: {risk.score ?? '-'} / Confidence: {driver.confidence ?? '-'}
          </div>
        </div>

        {/* Stagflation Gauge */}
        <div className="card" style={{ borderLeft: `3px solid ${STAG_COLORS[stag.level] || '#64748b'}` }}>
          <div className="card-label">Stagflation Risk</div>
          <div className="card-value" style={{ color: STAG_COLORS[stag.level] || 'var(--text-primary)', fontSize: '1.3rem' }}>
            {stag.index ?? '-'}
          </div>
          <div className="card-sub">{stag.level_kr || '-'}</div>
          {/* Progress bar */}
          <div style={{ marginTop: '0.5rem', background: '#334155', borderRadius: '4px', height: '8px', overflow: 'hidden' }}>
            <div style={{
              width: `${Math.min(100, stag.index || 0)}%`,
              height: '100%',
              borderRadius: '4px',
              background: stag.index > 70 ? '#ef4444' : stag.index > 50 ? '#f97316' : stag.index > 30 ? '#eab308' : '#22c55e',
              transition: 'width 0.5s',
            }} />
          </div>
        </div>

        {/* Cross-Market Recommendation */}
        <div className="card" style={{ borderLeft: `3px solid ${REC_COLORS[cm.recommendation] || '#64748b'}` }}>
          <div className="card-label">Cross-Market</div>
          <div className="card-value" style={{ color: REC_COLORS[cm.recommendation] || 'var(--text-primary)', fontSize: '1.3rem' }}>
            {cm.recommendation_kr || '-'}
          </div>
          <div className="card-sub">KR {cm.kr_score ?? '-'} / US {cm.us_score ?? '-'}</div>
        </div>
      </div>

      {/* Cross-Market Radar + Stagflation Breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
        {/* Radar Chart */}
        <div className="card">
          <h3 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>KR vs US Factor Comparison</h3>
          {radarData.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#334155" />
                <PolarAngleAxis dataKey="factor" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 9 }} />
                <Radar name="KR" dataKey="KR" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} />
                <Radar name="US" dataKey="US" stroke="#a855f7" fill="#a855f7" fillOpacity={0.2} />
                <Legend wrapperStyle={{ fontSize: '0.75rem' }} />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.8rem' }} />
              </RadarChart>
            </ResponsiveContainer>
          ) : <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No data</div>}
        </div>

        {/* Stagflation Breakdown */}
        <div className="card">
          <h3 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>Stagflation Components</h3>
          {stagBars.length > 0 ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={stagBars} layout="vertical" margin={{ left: 10, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} width={80} />
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.8rem' }}
                  formatter={(v) => [`${v.toFixed(1)}`, 'Score']} />
                <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={16}>
                  {stagBars.map((d, i) => (
                    <Cell key={i} fill={d.score > 60 ? '#ef4444' : d.score > 35 ? '#eab308' : '#22c55e'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No data</div>}
        </div>
      </div>

      {/* Cross-Market Factor Detail */}
      {cm.factors && (
        <div className="table-container" style={{ marginBottom: '1rem' }}>
          <div className="table-header">
            <h3>Factor Breakdown</h3>
          </div>
          <table>
            <thead>
              <tr>
                <th>Factor</th>
                <th>Analysis</th>
                <th>KR Impact</th>
                <th>US Impact</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(cm.factors).map(([key, f]) => (
                <tr key={key}>
                  <td style={{ fontWeight: 600 }}>
                    {key === 'fx_trend' ? 'FX (USD/KRW)' : key === 'volatility' ? 'Volatility (VIX)' : key === 'yield_env' ? 'Yield Env' : key === 'fund_flow' ? 'Fund Flow' : 'Signal Momentum'}
                  </td>
                  <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{f.label}</td>
                  <td style={{ color: f.kr_impact >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                    {f.kr_impact >= 0 ? '+' : ''}{f.kr_impact?.toFixed(2)}
                  </td>
                  <td style={{ color: f.us_impact >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                    {f.us_impact >= 0 ? '+' : ''}{f.us_impact?.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Macro Trends Chart */}
      <div className="card" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h3 style={{ fontSize: '0.85rem' }}>Macro Trends</h3>
          <div style={{ display: 'flex', gap: '0.3rem' }}>
            {[7, 30, 90].map(d => (
              <button key={d} className={`btn btn-sm ${trendDays === d ? 'btn-primary' : 'btn-outline'}`}
                onClick={() => setTrendDays(d)} style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}>
                {d}d
              </button>
            ))}
          </div>
        </div>
        {trends.length > 0 ? (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trends} margin={{ left: 5, right: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 9 }}
                tickFormatter={v => v?.slice(5)} />
              <YAxis yAxisId="left" tick={{ fill: '#94a3b8', fontSize: 9 }}
                domain={['auto', 'auto']} />
              <YAxis yAxisId="right" orientation="right" tick={{ fill: '#94a3b8', fontSize: 9 }}
                domain={['auto', 'auto']} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.75rem' }} />
              <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
              <Line yAxisId="left" type="monotone" dataKey="vix" stroke="#ef4444" name="VIX" dot={false} strokeWidth={2} />
              <Line yAxisId="left" type="monotone" dataKey="fear_greed" stroke="#eab308" name="F&G" dot={false} strokeWidth={1.5} />
              <Line yAxisId="left" type="monotone" dataKey="yield_spread" stroke="#22c55e" name="Yield Spread" dot={false} strokeWidth={1.5} />
              <Line yAxisId="right" type="monotone" dataKey="usd_krw" stroke="#3b82f6" name="USD/KRW" dot={false} strokeWidth={1.5} />
              <Line yAxisId="right" type="monotone" dataKey="dxy" stroke="#a855f7" name="DXY" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        ) : <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No trend data</div>}
      </div>

      {/* Action Items */}
      {cm.action_items && cm.action_items.length > 0 && (
        <div className="card" style={{ borderLeft: '3px solid var(--accent)' }}>
          <h3 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>{'\uD83D\uDCA1'} Action Items</h3>
          <ul style={{ listStyle: 'none', padding: 0, display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            {cm.action_items.map((item, i) => (
              <li key={i} style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', padding: '0.4rem 0.6rem', background: 'rgba(59,130,246,0.06)', borderRadius: '0.25rem' }}>
                {'\u2022'} {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
