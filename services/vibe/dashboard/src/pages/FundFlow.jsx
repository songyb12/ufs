import { useState, useEffect, useCallback } from 'react'
import { getSectorFundFlow, getCrossMarketFlow, getSectorRotation, getThemeRanking, getStrategyMatch } from '../api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend, ComposedChart, Line, Cell, Treemap
} from 'recharts'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import { useToast } from '../components/Toast'

const FLOW_COLORS = ['#3b82f6', '#22c55e', '#eab308', '#a855f7', '#f97316', '#ef4444', '#06b6d4', '#ec4899', '#14b8a6', '#8b5cf6']

function formatKRW(val) {
  if (val == null) return '-'
  const abs = Math.abs(val)
  if (abs >= 1e12) return `${(val / 1e12).toFixed(1)}조`
  if (abs >= 1e8) return `${(val / 1e8).toFixed(0)}억`
  if (abs >= 1e4) return `${(val / 1e4).toFixed(0)}만`
  return val.toLocaleString()
}

// Custom content for Treemap cells
function TreemapContent({ x, y, width, height, name, value, flow_dir }) {
  if (width < 40 || height < 25) return null
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={4}
        fill={flow_dir === 'inflow' ? 'rgba(34,197,94,0.3)' : flow_dir === 'outflow' ? 'rgba(239,68,68,0.3)' : 'rgba(100,116,139,0.3)'}
        stroke={flow_dir === 'inflow' ? '#22c55e' : flow_dir === 'outflow' ? '#ef4444' : '#64748b'}
        strokeWidth={1} />
      <text x={x + width / 2} y={y + height / 2 - 6} textAnchor="middle" fill="#f1f5f9" fontSize={width < 70 ? 9 : 11} fontWeight={600}>
        {name}
      </text>
      <text x={x + width / 2} y={y + height / 2 + 8} textAnchor="middle" fill="#94a3b8" fontSize={width < 70 ? 8 : 10}>
        {formatKRW(value)}
      </text>
    </g>
  )
}

export default function FundFlow({ onNavigate, refreshKey }) {
  const toast = useToast()
  const [sectorFlow, setSectorFlow] = useState([])
  const [crossFlow, setCrossFlow] = useState([])
  const [rotation, setRotation] = useState([])
  const [themes, setThemes] = useState([])
  const [strategyMatch, setStrategyMatch] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [days, setDays] = useState(5)

  const loadData = useCallback(() => {
    setLoading(true)
    return Promise.all([
      getSectorFundFlow(days).catch(() => ({ sectors: [] })),
      getCrossMarketFlow(30).catch(() => ({ series: [] })),
      getSectorRotation().catch(() => ({ rotation: [] })),
      getThemeRanking().catch(() => ({ themes: [] })),
      getStrategyMatch().catch(() => null),
    ])
      .then(([sf, cf, rot, th, sm]) => {
        setSectorFlow(sf?.sectors || [])
        setCrossFlow(cf?.series || [])
        setRotation(rot?.rotation || [])
        setThemes(th?.themes || [])
        setStrategyMatch(sm)
      })
      .catch(err => { setError(err.message); toast.error('자금 흐름 로드 실패: ' + err.message) })
      .finally(() => setLoading(false))
  }, [days])

  useEffect(() => { loadData() }, [loadData, refreshKey])

  if (loading) return <div className="loading"><span className="spinner" /> 로딩 중...</div>
  if (error) return <div className="error-state">오류: {error}</div>

  // Summary stats
  const totalForeign = sectorFlow.reduce((s, x) => s + (x.foreign_net || 0), 0)
  const totalInst = sectorFlow.reduce((s, x) => s + (x.institution_net || 0), 0)

  // Cross-market flow chart data
  const flowChartData = crossFlow.map(d => ({
    date: d.date?.slice(5),
    kr_foreign: d.kr_foreign_net ? d.kr_foreign_net / 1e8 : null, // to 억
    us_risk: d.us_risk_appetite,
    spy: d.spy_change,
    qqq: d.qqq_change,
  }))

  // Sector bar chart — adapts to fund_flow or signal-based data
  const hasFundFlow = sectorFlow.some(s => (s.foreign_net || 0) !== 0 || (s.institution_net || 0) !== 0)
  const sectorBars = sectorFlow.slice(0, 10).map(s => ({
    sector: s.sector,
    foreign: hasFundFlow ? (s.foreign_net || 0) / 1e8 : 0, // 억
    institution: hasFundFlow ? (s.institution_net || 0) / 1e8 : 0,
    avg_score: s.avg_score || 0,
  }))

  // Treemap data — use theme_score when flow_net is 0
  const treemapData = themes.filter(t => t.theme_score !== 0 || t.flow_net !== 0).map(t => ({
    name: t.sector,
    size: Math.max(t.flow_net !== 0 ? Math.abs(t.flow_net) : Math.abs(t.theme_score) * 1e9, 1e6),
    value: t.flow_net || t.theme_score,
    flow_dir: t.theme_score > 0.1 ? 'inflow' : t.theme_score < -0.1 ? 'outflow' : 'neutral',
  }))

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'💰'} 자금 흐름</h2>
          <p className="subtitle">자금 흐름 추적, 섹터 순환, 투자 테마 분석</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {[5, 10, 30].map(d => (
            <button key={d} className={`btn btn-sm ${days === d ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setDays(d)} style={{ fontSize: '0.75rem' }}>
              {d}d
            </button>
          ))}
          <button className="btn btn-outline" onClick={loadData}>{'↻'}</button>
          <HelpButton section="fund-flow" onNavigate={onNavigate} />
        </div>
      </div>

      <PageGuide
        pageId="fund-flow"
        title="자금흐름 읽는 법"
        steps={[
          'KR/US 교차흐름 → 외국인·기관 자금 방향 확인',
          '섹터 순환 → 자금 유입 섹터 = 다음 주도주 후보',
          '테마 히트맵 → 크기 = 관심도, 색상 = 긍정/부정',
          '전략 정합성 경고 → 시그널과 수급 방향 불일치 주의',
        ]}
        color="#f59e0b"
      />

      {/* Strategy Match Warnings */}
      {strategyMatch?.warnings?.length > 0 && (
        <div style={{ marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
          {strategyMatch.warnings.map((w, i) => (
            <div key={i} style={{
              padding: '0.5rem 0.75rem',
              borderRadius: '0.375rem',
              fontSize: '0.8rem',
              background: w.level === 'warning' ? 'rgba(239,68,68,0.08)' : w.level === 'opportunity' ? 'rgba(34,197,94,0.08)' : 'rgba(59,130,246,0.08)',
              borderLeft: `3px solid ${w.level === 'warning' ? '#ef4444' : w.level === 'opportunity' ? '#22c55e' : '#3b82f6'}`,
              color: 'var(--text-secondary)',
            }}>
              {w.level === 'warning' ? '⚠️' : w.level === 'opportunity' ? '💡' : 'ℹ️'} {w.message}
              {i === 0 && strategyMatch.season && (
                <span style={{ marginLeft: '0.5rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                  ({strategyMatch.season} / {strategyMatch.clock_quadrant ?? '-'})
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Summary Cards */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <div className="card">
          <div className="card-label">KR 외국인 순매수</div>
          <div className={`card-value ${totalForeign >= 0 ? 'green' : 'red'}`} style={{ fontSize: '1.2rem' }}>
            {totalForeign >= 0 ? '+' : ''}{formatKRW(totalForeign)}
          </div>
          <div className="card-sub">{days}일 누적</div>
        </div>
        <div className="card">
          <div className="card-label">KR 기관 순매수</div>
          <div className={`card-value ${totalInst >= 0 ? 'green' : 'red'}`} style={{ fontSize: '1.2rem' }}>
            {totalInst >= 0 ? '+' : ''}{formatKRW(totalInst)}
          </div>
          <div className="card-sub">{days}일 누적</div>
        </div>
        <div className="card">
          <div className="card-label">추적 섹터</div>
          <div className="card-value blue">{sectorFlow.length}</div>
          <div className="card-sub">유입 {sectorFlow.filter(s => s.total_net > 0).length} / 유출 {sectorFlow.filter(s => s.total_net < 0).length}</div>
        </div>
        <div className="card">
          <div className="card-label">핫 테마</div>
          <div className="card-value green">{themes.filter(t => t.signal === 'Hot').length}</div>
          <div className="card-sub">{themes.length}개 섹터 중</div>
        </div>
      </div>

      {/* Cross-Market Flow Chart */}
      {flowChartData.length > 0 && (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>Cross-Market Fund Flow</h3>
          <ResponsiveContainer width="100%" height={250}>
            <ComposedChart data={flowChartData} margin={{ left: 5, right: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 9 }} />
              <YAxis yAxisId="left" tick={{ fill: '#94a3b8', fontSize: 9 }} label={{ value: 'KR (억)', fill: '#94a3b8', fontSize: 9, angle: -90, position: 'insideLeft' }} />
              <YAxis yAxisId="right" orientation="right" tick={{ fill: '#94a3b8', fontSize: 9 }} label={{ value: 'US ETF', fill: '#94a3b8', fontSize: 9, angle: 90, position: 'insideRight' }} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.8rem' }}
                formatter={(v, name) => {
                  if (v == null) return ['-', name]
                  if (name === 'kr_foreign') return [`${v.toFixed(0)}억`, 'KR 외국인']
                  if (name === 'us_risk') return [v.toFixed(2), 'US Risk Appetite']
                  if (name === 'spy') return [`${v.toFixed(2)}%`, 'SPY']
                  return [v.toFixed(2), name]
                }} />
              <Legend wrapperStyle={{ fontSize: '0.7rem' }} formatter={v => v === 'kr_foreign' ? 'KR 외국인(억)' : v === 'us_risk' ? 'US Risk Appetite' : v.toUpperCase()} />
              <Bar yAxisId="left" dataKey="kr_foreign" name="kr_foreign" barSize={12} radius={[3, 3, 0, 0]}>
                {flowChartData.map((d, i) => (
                  <Cell key={i} fill={(d.kr_foreign || 0) >= 0 ? 'rgba(34,197,94,0.6)' : 'rgba(239,68,68,0.6)'} />
                ))}
              </Bar>
              <Line yAxisId="right" type="monotone" dataKey="us_risk" name="us_risk" stroke="#a855f7" strokeWidth={2} dot={false} />
              <Line yAxisId="right" type="monotone" dataKey="spy" name="spy" stroke="#3b82f6" strokeWidth={1} dot={false} strokeDasharray="3 3" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Sector Fund Flow / Signal Chart */}
      {sectorBars.length > 0 && (
        <div className="card" style={{ marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>
            {hasFundFlow ? `Sector Fund Flow (${days}d)` : 'Sector Signal Strength'}
          </h3>
          <ResponsiveContainer width="100%" height={Math.max(200, sectorBars.length * 35)}>
            <BarChart data={sectorBars} layout="vertical" margin={{ left: 10, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 9 }} />
              <YAxis type="category" dataKey="sector" tick={{ fill: '#94a3b8', fontSize: 10 }} width={90} />
              <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.8rem' }}
                formatter={(v, name) => [hasFundFlow ? `${v.toFixed(0)}억` : v.toFixed(1), name]} />
              <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
              {hasFundFlow ? (
                <>
                  <Bar dataKey="foreign" name="Foreign" fill="#3b82f6" barSize={10} radius={[0, 3, 3, 0]} />
                  <Bar dataKey="institution" name="Institution" fill="#22c55e" barSize={10} radius={[0, 3, 3, 0]} />
                </>
              ) : (
                <Bar dataKey="avg_score" name="Avg Score" barSize={14} radius={[0, 3, 3, 0]}>
                  {sectorBars.map((s, i) => (
                    <Cell key={i} fill={s.avg_score >= 0 ? 'rgba(34,197,94,0.6)' : 'rgba(239,68,68,0.6)'} />
                  ))}
                </Bar>
              )}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Sector Rotation Table + Theme Treemap side by side */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
        {/* Rotation Table */}
        <div className="table-container">
          <div className="table-header">
            <h3>Sector Rotation</h3>
            <span className="card-sub">5d vs prev 5d</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>Sector</th>
                <th>Rank</th>
                <th>Change</th>
                <th>Net Flow</th>
                <th>Signal</th>
              </tr>
            </thead>
            <tbody>
              {rotation.length === 0 ? (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '1.5rem' }}>No data</td></tr>
              ) : rotation.map((r, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600 }}>{r.sector}</td>
                  <td>{r.current_rank}</td>
                  <td style={{ color: r.rank_change > 0 ? 'var(--green)' : r.rank_change < 0 ? 'var(--red)' : 'var(--text-muted)', fontWeight: 600 }}>
                    {r.rank_change > 0 ? `↑+${r.rank_change}` : r.rank_change < 0 ? `↓${r.rank_change}` : '-'}
                  </td>
                  <td style={{ fontSize: '0.8rem' }}>
                    {r.current_net ? formatKRW(r.current_net) : r.avg_score != null ? r.avg_score.toFixed(1) : '-'}
                  </td>
                  <td>
                    <span className={`badge ${
                      r.signal === 'Inflow' || r.signal === 'Buy-Dominant' ? 'badge-buy' :
                      r.signal === 'Outflow' || r.signal === 'Sell-Dominant' ? 'badge-sell' : 'badge-hold'
                    }`}>
                      {r.signal}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Theme Treemap */}
        <div className="card">
          <h3 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>Theme Heat Map</h3>
          {treemapData.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <Treemap data={treemapData} dataKey="size" nameKey="name" aspectRatio={4 / 3}
                content={<TreemapContent />} />
            </ResponsiveContainer>
          ) : <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No theme data</div>}
        </div>
      </div>

      {/* Theme Ranking Table */}
      {themes.length > 0 && (
        <div className="table-container">
          <div className="table-header">
            <h3>Theme Ranking</h3>
            <span className="card-sub">{themes.length} sectors</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Sector</th>
                <th>Score</th>
                <th>Foreign Net</th>
                <th>Inst Net</th>
                <th className="hide-on-tablet">Avg Signal</th>
                <th className="hide-on-tablet">BUY/SELL</th>
                <th>Signal</th>
              </tr>
            </thead>
            <tbody>
              {themes.map((t, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td style={{ fontWeight: 600 }}>{t.sector}</td>
                  <td style={{ color: (t.theme_score ?? 0) > 0.1 ? 'var(--green)' : (t.theme_score ?? 0) < -0.1 ? 'var(--red)' : 'var(--text-muted)', fontWeight: 600 }}>
                    {(t.theme_score ?? 0) >= 0 ? '+' : ''}{t.theme_score?.toFixed(2) ?? '-'}
                  </td>
                  <td style={{ color: t.foreign_net >= 0 ? 'var(--green)' : 'var(--red)', fontSize: '0.8rem' }}>
                    {formatKRW(t.foreign_net)}
                  </td>
                  <td style={{ color: t.institution_net >= 0 ? 'var(--green)' : 'var(--red)', fontSize: '0.8rem' }}>
                    {formatKRW(t.institution_net)}
                  </td>
                  <td className="hide-on-tablet" style={{ color: (t.avg_signal_score ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {t.avg_signal_score?.toFixed(1) ?? '-'}
                  </td>
                  <td className="hide-on-tablet">
                    <span style={{ color: 'var(--green)' }}>{t.buy_signals}</span>
                    {' / '}
                    <span style={{ color: 'var(--red)' }}>{t.sell_signals}</span>
                  </td>
                  <td>
                    <span className={`badge ${t.signal === 'Hot' ? 'badge-buy' : t.signal === 'Cold' ? 'badge-sell' : 'badge-hold'}`}>
                      {t.signal}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
