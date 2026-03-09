import { useState, useEffect, useCallback } from 'react'
import { getActionPlan } from '../api'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import { useToast } from '../components/Toast'
import Tip from '../components/Tip'

const SEASON_KR = { spring: '금융장세', summer: '실적장세', autumn: '역금융장세', winter: '역실적장세' }
const FEAR_KR = { 'Calm': '평온', 'Initial Panic': '패닉 초기', 'Peak Fear': '공포 극점', 'Post-Peak': '공포 후퇴' }
const FEAR_COLORS = { 'Calm': '#22c55e', 'Initial Panic': '#f59e0b', 'Peak Fear': '#ef4444', 'Post-Peak': '#3b82f6' }

function getStanceRules(strategy) {
  const fp = strategy.fear_phase
  const rs = strategy.risk_score ?? 50
  const sn = (strategy.season || '').toLowerCase()

  // Determine which rule fires (same priority as backend)
  let activeIdx = -1
  if (fp === 'Peak Fear') activeIdx = 0
  else if (fp === 'Initial Panic') activeIdx = 1
  else if (rs >= 75) activeIdx = 2
  else if (rs >= 60) activeIdx = 3
  else if (['autumn', 'winter'].includes(sn)) activeIdx = 4
  else if (rs <= 30 && ['spring', 'summer'].includes(sn)) activeIdx = 5
  else if (rs <= 45) activeIdx = 6
  else activeIdx = 7

  return [
    { label: '\u2460 Peak Fear → 역발상 분할 매수', value: `Fear: ${fp}`, active: activeIdx === 0, skipped: activeIdx < 0 },
    { label: '\u2461 Initial Panic → 방어 태세', value: `Fear: ${fp}`, active: activeIdx === 1, skipped: activeIdx < 1 },
    { label: '\u2462 Risk ≥ 75 → 매우 보수적', value: `Risk: ${rs}`, active: activeIdx === 2, skipped: activeIdx < 2 },
    { label: '\u2463 Risk ≥ 60 → 신중 접근', value: `Risk: ${rs}`, active: activeIdx === 3, skipped: activeIdx < 3 },
    { label: '\u2464 가을/겨울장세 → 신중 접근', value: `Season: ${SEASON_KR[sn] || sn}`, active: activeIdx === 4, skipped: activeIdx < 4 },
    { label: '\u2465 Risk ≤ 30 + 봄/여름 → 적극 매수', value: `Risk: ${rs}, ${SEASON_KR[sn] || sn}`, active: activeIdx === 5, skipped: activeIdx < 5 },
    { label: '\u2466 Risk ≤ 45 → 완만한 매수', value: `Risk: ${rs}`, active: activeIdx === 6, skipped: activeIdx < 6 },
    { label: '\u2467 기본값 → 중립 관망', value: '', active: activeIdx === 7, skipped: activeIdx < 7 },
  ]
}

export default function ActionPlan({ onNavigate, refreshKey }) {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedPick, setExpandedPick] = useState(null)

  const loadData = useCallback(() => {
    setLoading(true)
    getActionPlan()
      .then(d => { setData(d); setError(null) })
      .catch(err => { setError(err.message); toast.error('\uC561\uC158 \uD50C\uB79C \uB85C\uB4DC \uC2E4\uD328') })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData, refreshKey])

  if (loading) return <div className="loading"><span className="spinner" /> 로딩 중...</div>
  if (error) return <div className="error-state">Error: {error}</div>
  if (!data) return <div className="empty-state">No data</div>

  const { strategy = {}, signal_summary = {}, top_picks, portfolio_actions, market_context } = data

  const stanceColors = {
    contrarian_buy: '#22c55e', aggressive: '#22c55e', moderate_buy: '#3b82f6',
    neutral: '#94a3b8', cautious: '#f59e0b', defensive: '#ef4444', very_defensive: '#dc2626',
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'\uD83C\uDFAF'} 액션 플랜</h2>
          <p className="subtitle">{data.date} — {'\uD558\uB77C\uB294\uB300\uB85C\uB9CC \uD574\uB3C4 \uC218\uC775\uC744 \uB0B4\uB294 \uC2DC\uC2A4\uD15C'}</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button className="btn btn-outline" onClick={loadData}>{'\u21BB'} Refresh</button>
          <HelpButton section="action-plan" onNavigate={onNavigate} />
        </div>
      </div>

      <PageGuide
        pageId="action-plan"
        title="오늘의 액션 플랜 읽는 순서"
        steps={[
          '전략 스탠스 확인 → 공격/중립/방어 방향',
          'Top Picks 테이블 → 스코어·R:R 높은 종목 우선',
          '포트폴리오 조치 → CUT_LOSS/TAKE_PROFIT 즉시 대응',
          '구루 컨센서스 → 대가들의 현재 시장 판단',
        ]}
      />

      {/* Strategy Banner */}
      <div style={{
        background: `linear-gradient(135deg, ${stanceColors[strategy.stance] || '#3b82f6'}22, transparent)`,
        border: `2px solid ${stanceColors[strategy.stance] || '#3b82f6'}`,
        borderRadius: '1rem', padding: '1.5rem', marginBottom: '1rem',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <Tip text={TIPS.stance}>
              <div style={{ fontSize: '1.8rem', fontWeight: 700, color: stanceColors[strategy.stance] || '#3b82f6' }}>
                {strategy.stance_kr}
              </div>
            </Tip>
            {strategy.stance_reason && (
              <div style={{ fontSize: '0.8rem', color: stanceColors[strategy.stance] || '#3b82f6', marginTop: '0.2rem', opacity: 0.85 }}>
                {'\u25B8'} {strategy.stance_reason}
              </div>
            )}
            <div style={{ color: 'var(--text-muted)', marginTop: '0.25rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <Tip text={TIPS.risk_score} indicator>
                Risk {strategy.risk_level} ({strategy.risk_score}/100)
              </Tip>
              <span>|</span>
              <Tip text={TIPS.fear_phase} indicator>
                Fear: {strategy.fear_phase}
              </Tip>
              <span>|</span>
              <Tip text={TIPS.season} indicator>
                Season: {SEASON_KR[strategy.season] || strategy.season || '-'}
              </Tip>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <Tip text={TIPS.cash_ratio}>
              <div style={{ fontSize: '1.3rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                {strategy.cash_ratio_kr}
              </div>
            </Tip>
            <Tip text={TIPS.signal_summary}>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                BUY {signal_summary.buy_count} | SELL {signal_summary.sell_count} | HOLD {signal_summary.hold_count}
              </div>
            </Tip>
          </div>
        </div>
      </div>

      {/* Market Context Quick Stats */}
      {market_context && (
        <div className="card-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)', marginBottom: '1rem' }}>
          <div className="card" style={{ textAlign: 'center', padding: '0.6rem' }}>
            <div className="card-label">VIX</div>
            <div className="card-value" style={{ fontSize: '1.1rem', color: (market_context.vix || 0) > 25 ? 'var(--red)' : (market_context.vix || 0) > 20 ? '#f59e0b' : 'var(--green)' }}>
              {market_context.vix?.toFixed(1) ?? '-'}
            </div>
          </div>
          <div className="card" style={{ textAlign: 'center', padding: '0.6rem' }}>
            <div className="card-label">Fear & Greed</div>
            <div className="card-value" style={{ fontSize: '1.1rem', color: (market_context.fear_greed || 50) < 25 ? 'var(--red)' : (market_context.fear_greed || 50) > 75 ? 'var(--green)' : '#f59e0b' }}>
              {market_context.fear_greed ?? '-'}
            </div>
          </div>
          <div className="card" style={{ textAlign: 'center', padding: '0.6rem' }}>
            <div className="card-label">USD/KRW</div>
            <div className="card-value" style={{ fontSize: '1.1rem' }}>
              {market_context.usd_krw?.toFixed(0) ?? '-'}
            </div>
          </div>
          <div className="card" style={{ textAlign: 'center', padding: '0.6rem' }}>
            <div className="card-label">Risk Score</div>
            <div className="card-value" style={{ fontSize: '1.1rem', color: (market_context.risk_score || 0) >= 60 ? 'var(--red)' : (market_context.risk_score || 0) >= 40 ? '#f59e0b' : 'var(--green)' }}>
              {market_context.risk_score ?? '-'}
            </div>
          </div>
          <div className="card" style={{ textAlign: 'center', padding: '0.6rem' }}>
            <div className="card-label">Fear Phase</div>
            <div className="card-value" style={{ fontSize: '0.85rem', color: FEAR_COLORS[market_context.fear_phase] || 'var(--text-primary)' }}>
              {FEAR_KR[market_context.fear_phase] || market_context.fear_phase || '-'}
            </div>
          </div>
        </div>
      )}

      {/* Stance Decision Logic */}
      <div className="card" style={{ marginBottom: '1.5rem', borderLeft: `3px solid ${stanceColors[strategy.stance] || '#3b82f6'}` }}>
        <h3 style={{ marginBottom: '0.5rem', fontSize: '0.9rem' }}>
          {'\uD83E\uDDE0'}{' '}
          <Tip text={TIPS.stance_logic} indicator>스탠스 결정 로직</Tip>
        </h3>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          위에서 아래 순서로 검사, 먼저 해당되면 아래 규칙은 무시됨
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
          {getStanceRules(strategy).map((rule, i) => (
            <div key={i} style={{
              padding: '0.25rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem',
              display: 'flex', alignItems: 'center', gap: '0.4rem',
              background: rule.active ? `${stanceColors[strategy.stance] || '#3b82f6'}12` : 'transparent',
              borderLeft: rule.active ? `2px solid ${stanceColors[strategy.stance] || '#3b82f6'}` : '2px solid transparent',
              opacity: rule.skipped ? 0.35 : 1,
            }}>
              <span style={{ width: '16px', textAlign: 'center', fontSize: '0.7rem', flexShrink: 0 }}>
                {rule.active ? '\u25B6' : rule.skipped ? '\u2500' : '\u2502'}
              </span>
              <span style={{ color: rule.active ? stanceColors[strategy.stance] || '#3b82f6' : 'var(--text-muted)', fontWeight: rule.active ? 600 : 400 }}>
                {rule.label}
              </span>
              <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: 'var(--text-muted)', flexShrink: 0 }}>
                {rule.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Strategic Actions */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ marginBottom: '1rem' }}>
          {'\u26A1'}{' '}
          <Tip text={TIPS.action_items} indicator>{'\uC624\uB298\uC758 \uC804\uB7B5 \uC561\uC158'}</Tip>
        </h3>
        {strategy.action_items?.map((item, i) => (
          <div key={i} style={{
            padding: '0.75rem 1rem', marginBottom: '0.5rem',
            background: item.priority === 1 ? 'rgba(59,130,246,0.08)' : 'var(--bg-primary)',
            borderRadius: '0.5rem',
            borderLeft: `3px solid ${item.priority === 1 ? '#3b82f6' : item.priority === 2 ? '#f59e0b' : '#64748b'}`,
          }}>
            <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
              <Tip text={TIPS.priority[item.priority] || TIPS.priority[3]}>
                <span>{item.priority === 1 ? '\uD83D\uDD34' : item.priority === 2 ? '\uD83D\uDFE1' : '\u26AA'}</span>
              </Tip>
              {' '}{item.title}
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '0.25rem' }}>
              {item.detail_kr}
            </div>
          </div>
        ))}
      </div>

      {/* Sector Bias */}
      {strategy.sector_bias?.length > 0 && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>
            {'\uD83D\uDD04'}{' '}
            <Tip text={TIPS.sector_bias} indicator>{'\uC139\uD130 \uBC30\uBD84 \uC804\uB7B5'}</Tip>
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.5rem' }}>
            {strategy.sector_bias.map((s, i) => (
              <div key={i} style={{
                padding: '0.75rem', borderRadius: '0.5rem',
                background: s.bias === 'overweight' ? 'rgba(34,197,94,0.06)' : s.bias === 'underweight' ? 'rgba(239,68,68,0.06)' : 'var(--bg-primary)',
                border: `1px solid ${s.bias === 'overweight' ? 'var(--green)' : s.bias === 'underweight' ? 'var(--red)' : 'var(--border)'}`,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{s.sector}</span>
                  <Tip text={TIPS.bias_label[s.bias] || ''}>
                    <span className={`badge ${s.bias === 'overweight' ? 'badge-buy' : s.bias === 'underweight' ? 'badge-sell' : 'badge-hold'}`}>
                      {s.bias === 'overweight' ? 'Overweight' : s.bias === 'underweight' ? 'Underweight' : 'Neutral'}
                    </span>
                  </Tip>
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.25rem' }}>{s.reason}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top Picks */}
      {top_picks?.length > 0 && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>
            {'\uD83C\uDFC6'}{' '}
            <Tip text={TIPS.top_picks} indicator>{'\uCD94\uCC9C \uB9E4\uC218 TOP'} {top_picks.length}</Tip>
          </h3>
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>SYMBOL</th>
                  <th><Tip text={TIPS.col_score} indicator>SCORE</Tip></th>
                  <th><Tip text={TIPS.col_rsi} indicator>RSI</Tip></th>
                  <th><Tip text={TIPS.col_current} indicator>{'\uD604\uC7AC\uAC00'}</Tip></th>
                  <th><Tip text={TIPS.col_target} indicator>{'\uBAA9\uD45C\uAC00'}</Tip></th>
                  <th><Tip text={TIPS.col_stoploss} indicator>{'\uC190\uC808\uAC00'}</Tip></th>
                  <th><Tip text={TIPS.col_rr} indicator>R:R</Tip></th>
                  <th><Tip text={TIPS.col_amount} indicator>{'\uCD94\uCC9C \uAE08\uC561'}</Tip></th>
                </tr>
              </thead>
              <tbody>
                {top_picks.map((p, i) => (
                  <tr key={p.symbol} onClick={() => setExpandedPick(expandedPick === i ? null : i)} style={{ cursor: 'pointer' }}>
                    <td style={{ fontWeight: 700, color: 'var(--blue)' }}>{p.rank}</td>
                    <td>
                      <strong>{p.name || p.symbol}</strong>
                      <br /><span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{p.symbol} · {p.market}</span>
                    </td>
                    <td style={{ color: 'var(--green)', fontWeight: 600 }}>+{p.signal_score}</td>
                    <td style={{ color: (p.rsi ?? 50) < 30 ? 'var(--green)' : (p.rsi ?? 50) > 70 ? 'var(--red)' : 'var(--text-secondary)' }}>
                      {p.rsi ?? '-'}
                    </td>
                    <td>{p.current_price != null ? p.current_price.toLocaleString() : '-'}</td>
                    <td style={{ color: 'var(--green)' }}>{p.target_price != null ? p.target_price.toLocaleString() : '-'}</td>
                    <td style={{ color: 'var(--red)' }}>{p.stop_loss != null ? p.stop_loss.toLocaleString() : '-'}</td>
                    <td style={{ fontWeight: 600, color: (p.rr_ratio ?? 0) >= 2 ? 'var(--green)' : 'var(--text-secondary)' }}>
                      {p.rr_ratio ?? '-'}:1
                    </td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{p.recommended_size?.toLocaleString() ?? '-'}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{p.recommended_pct}%</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {expandedPick != null && top_picks[expandedPick] && (
            <div style={{ padding: '1rem', background: 'var(--bg-primary)', borderRadius: '0.5rem', marginTop: '0.5rem', fontSize: '0.85rem' }}>
              <strong>{top_picks[expandedPick].name}</strong>
              <div style={{ marginTop: '0.5rem', color: 'var(--text-secondary)' }}>
                {top_picks[expandedPick].rationale || top_picks[expandedPick].size_rationale_kr}
              </div>
              <div style={{ marginTop: '0.5rem', color: 'var(--text-muted)' }}>
                <Tip text={TIPS.target_return} indicator>{'\uBAA9\uD45C \uC218\uC775\uB960'}</Tip>: +{top_picks[expandedPick].target_return_pct}% |{' '}
                <Tip text={TIPS.confidence} indicator>{'\uD655\uC2E0\uB3C4'}</Tip>: {top_picks[expandedPick].confidence}%
              </div>
            </div>
          )}
        </div>
      )}

      {/* Portfolio Actions */}
      {portfolio_actions?.length > 0 && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>
            {'\uD83D\uDCBC'}{' '}
            <Tip text={TIPS.portfolio_actions} indicator>{'\uBCF4\uC720 \uC885\uBAA9 \uC561\uC158'}</Tip>
            {' '}({portfolio_actions.length})
          </h3>
          {portfolio_actions.map((a, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '0.75rem 1rem', marginBottom: '0.4rem', borderRadius: '0.5rem',
              background: a.urgency === 'high' ? 'rgba(239,68,68,0.06)' : a.urgency === 'medium' ? 'rgba(245,158,11,0.06)' : 'var(--bg-primary)',
              border: `1px solid ${a.urgency === 'high' ? 'rgba(239,68,68,0.2)' : a.urgency === 'medium' ? 'rgba(245,158,11,0.2)' : 'var(--border)'}`,
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{a.name}</span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{a.symbol}</span>
                  <Tip text={TIPS.signal_badge[a.signal] || ''}>
                    <span className={`badge badge-${a.signal === 'BUY' ? 'buy' : a.signal === 'SELL' ? 'sell' : 'hold'}`} style={{ fontSize: '0.65rem' }}>
                      {a.signal}
                    </span>
                  </Tip>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                  {a.reason_kr}
                </div>
              </div>
              <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: '1rem' }}>
                <Tip text={TIPS.action_type[a.action] || a.action_kr}>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>{a.action_kr}</div>
                </Tip>
                <div style={{ color: a.pnl_pct >= 0 ? 'var(--green)' : 'var(--red)', fontSize: '0.85rem' }}>
                  {a.pnl_pct >= 0 ? '+' : ''}{a.pnl_pct}%
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Weekly Outlook */}
      {strategy.weekly_outlook && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>
            {'\uD83D\uDCC5'}{' '}
            <Tip text={TIPS.weekly_outlook} indicator>{'\uC8FC\uAC04 \uC804\uB9DD'}</Tip>
          </h3>
          <p style={{ color: 'var(--text-secondary)', lineHeight: 1.7, fontSize: '0.9rem' }}>
            {strategy.weekly_outlook.summary_kr}
          </p>
          {strategy.weekly_outlook.watch_items?.length > 0 && (
            <div style={{ marginTop: '0.75rem' }}>
              <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                <Tip text={TIPS.watch_list} indicator>
                  {'\uD83D\uDC41\uFE0F'} Watch List
                </Tip>
              </div>
              {strategy.weekly_outlook.watch_items.map((w, i) => (
                <div key={i} style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', padding: '0.2rem 0' }}>
                  {'\u2022'} {w}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Guru Consensus */}
      {strategy.guru_summary && (
        <div className="card">
          <h3 style={{ marginBottom: '0.75rem' }}>
            {'\uD83C\uDFAF'}{' '}
            <Tip text={TIPS.guru_consensus} indicator>{'\uAD6C\uB8E8 \uCEE8\uC13C\uC11C\uC2A4'}</Tip>
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              {strategy.guru_summary.consensus_kr}
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              ({strategy.guru_summary.guru_count}{'\uBA85'}{' '}
              <Tip text={TIPS.guru_conviction} indicator>{'\uD3C9\uADE0 \uD655\uC2E0\uB3C4'}</Tip> {strategy.guru_summary.avg_conviction}%)
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Tooltip text definitions ──────────────────────────────────────────────
const TIPS = {
  stance: '\uD604\uC7AC \uC2DC\uC7A5 \uC0C1\uD669\uC744 \uC885\uD569 \uBD84\uC11D\uD558\uC5EC \uACB0\uC815\uB41C \uD22C\uC790 \uC804\uB7B5 \uBC29\uD5A5.\n\u2022 \uC5ED\uBC1C\uC0C1 \uB9E4\uC218: \uC2DC\uC7A5 \uACF5\uD3EC \uAD6C\uAC04\uC5D0\uC11C \uBD84\uD560 \uB9E4\uC218 \uAE30\uD68C\n\u2022 \uACF5\uACA9\uC801: \uC0C1\uC2B9 \uCD94\uC138 \uAC15\uD654, \uC801\uADF9 \uB9E4\uC218\n\u2022 \uC911\uB9BD: \uBC29\uD5A5\uC131 \uD0D0\uC0C9 \uC911, \uAD00\uB9DD\n\u2022 \uBC29\uC5B4\uC801: \uD558\uB77D \uC704\uD5D8 \uB192\uC74C, \uD604\uAE08 \uBE44\uC911 \uD655\uB300',
  stance_logic: '\uC2A4\uD0E0\uC2A4 \uACB0\uC815 \uC6B0\uC120\uC21C\uC704.\n\u2460 \uACF5\uD3EC \uAD6D\uBA74 → \u2461 \uD328\uB2C9 \uCD08\uAE30 → \u2462~\u2463 \uB9AC\uC2A4\uD06C \uC810\uC218 → \u2464 \uC2DC\uC7A5 \uACC4\uC808 → \u2465~\u2467 \uAE30\uBCF8\uAC12.\n\uC704\uCABD \uADDC\uCE59\uC774 \uD2B8\uB9AC\uAC70\uB418\uBA74 \uC544\uB798 \uADDC\uCE59\uC740 \uBB34\uC2DC\uB429\uB2C8\uB2E4.\n\uC608: \uACF5\uD3EC \uCD08\uAE30\uBA74 \uB9AC\uC2A4\uD06C \uC810\uC218\uAC00 \uB0AE\uC544\uB3C4 \uBC29\uC5B4 \uD0DC\uC138.',
  risk_score: '\uB9E4\uD06C\uB85C \uC704\uD5D8 \uC810\uC218 (0~100).\n\uC2A4\uD0DC\uADF8\uD50C\uB808\uC774\uC158 \uC9C0\uC218(40%) + \uC704\uD5D8 \uB808\uC9D0(30%) + \uD22C\uC790\uC2DC\uACC4(30%)\uB97C \uC885\uD569\uD55C \uAC12.\n\uB0AE\uC744\uC218\uB85D \uC548\uC804, \uB192\uC744\uC218\uB85D \uC704\uD5D8.',
  fear_phase: '\uACF5\uD3EC \uAD6D\uBA74 \uBD84\uC11D (Fear Gauge).\nVIX \uBCC0\uD654\uC728, F&G \uBAA8\uBA58\uD140, Put/Call \uBE44\uC728\uC744 \uC885\uD569.\n\u2022 Calm: \uD3C9\uC628\uD55C \uC2DC\uC7A5\n\u2022 Initial Panic: \uACF5\uD3EC \uC2DC\uC791\n\u2022 Peak Fear: \uACF5\uD3EC \uADF9\uC810 (\uC5ED\uBC1C\uC0C1 \uB9E4\uC218 \uAE30\uD68C)\n\u2022 Post-Peak: \uACF5\uD3EC \uD6C4\uD1F4 (\uD68C\uBCF5 \uC2DC\uC791)',
  season: '\uC2DC\uC7A5 \uACC4\uC808 \uBD84\uC11D.\n\uACBD\uAE30 \uC21C\uD658\uACFC \uD1B5\uD654 \uC815\uCC45\uC5D0 \uB530\uB77C \uD22C\uC790 \uC2DC\uACC4\uC758 4\uC0AC\uBD84\uBA74\uC744 \uBD84\uC11D.\nRecovery / Reflation / Overheat / Stagflation',
  cash_ratio: '\uD604\uC7AC \uC2DC\uC7A5 \uC704\uD5D8\uB3C4\uC5D0 \uB530\uB978 \uAD8C\uC7A5 \uD604\uAE08 \uBE44\uC911.\n\uC704\uD5D8\uC774 \uB192\uC744\uC218\uB85D \uD604\uAE08 \uBE44\uC911\uC744 \uB192\uC5EC \uBC29\uC5B4,\n\uB0AE\uC744\uC218\uB85D \uD22C\uC790 \uBE44\uC911 \uD655\uB300 \uAD8C\uC7A5.',
  signal_summary: 'VIBE \uD30C\uC774\uD504\uB77C\uC778\uC774 \uBD84\uC11D\uD55C \uC804\uCCB4 \uC885\uBAA9 \uC2DC\uADF8\uB110 \uC694\uC57D.\nBUY: \uB9E4\uC218 \uC2DC\uADF8\uB110 \uC885\uBAA9 \uC218\nSELL: \uB9E4\uB3C4 \uC2DC\uADF8\uB110 \uC885\uBAA9 \uC218\nHOLD: \uAD00\uB9DD/\uC720\uC9C0 \uC885\uBAA9 \uC218',
  action_items: '\uC624\uB298 \uC218\uD589\uD574\uC57C \uD560 \uD22C\uC790 \uC561\uC158 \uBAA9\uB85D.\n\uC6B0\uC120\uC21C\uC704 \uC21C\uC73C\uB85C \uC815\uB82C\uB418\uC5B4 \uC788\uC73C\uBA70,\n\uAC01 \uD56D\uBAA9\uC5D0\uB294 \uAD6C\uCCB4\uC801\uC778 \uC2E4\uD589 \uBC29\uBC95\uC774 \uD3EC\uD568.',
  priority: {
    1: '\uD83D\uDD34 \uCD5C\uC6B0\uC120 (Priority 1)\n\uAC00\uC7A5 \uBA3C\uC800 \uC2E4\uD589\uD574\uC57C \uD560 \uD575\uC2EC \uC804\uB7B5.',
    2: '\uD83D\uDFE1 \uC911\uC694 (Priority 2)\n\uD575\uC2EC \uC804\uB7B5 \uB2E4\uC74C\uC73C\uB85C \uC2E4\uD589\uD560 \uBCF4\uC870 \uC804\uB7B5.',
    3: '\u26AA \uCC38\uACE0 (Priority 3)\n\uC5EC\uC720\uAC00 \uB420 \uB54C \uCC38\uACE0\uD560 \uBD80\uAC00 \uC815\uBCF4.',
  },
  sector_bias: '\uD604\uC7AC \uC2DC\uC7A5 \uD658\uACBD\uC5D0 \uB530\uB77C \uC139\uD130\uBCC4 \uBE44\uC911 \uC870\uC808 \uAD8C\uC7A5.\nVIX, \uAE08\uB9AC, \uC720\uAC00, \uD658\uC728 \uB4F1 \uB9E4\uD06C\uB85C \uC9C0\uD45C\uB97C \uBD84\uC11D\uD558\uC5EC\n\uAC01 \uC139\uD130\uC758 \uD22C\uC790 \uBE44\uC911\uC744 \uC81C\uC548\uD569\uB2C8\uB2E4.',
  bias_label: {
    overweight: 'Overweight (\uBE44\uC911 \uD655\uB300)\n\uD604\uC7AC \uC2DC\uC7A5 \uD658\uACBD\uC5D0\uC11C \uC774 \uC139\uD130\uAC00 \uC720\uB9AC\uD569\uB2C8\uB2E4.\n\uD3EC\uD2B8\uD3F4\uB9AC\uC624\uC5D0\uC11C \uBE44\uC911\uC744 \uB2E4\uC18C \uB192\uC774\uB294 \uAC83\uC774 \uC88B\uC2B5\uB2C8\uB2E4.',
    neutral: 'Neutral (\uC911\uB9BD)\n\uD2B9\uBCC4\uD55C \uBE44\uC911 \uC870\uC808 \uD544\uC694 \uC5C6\uC74C.\n\uAE30\uC874 \uBE44\uC911\uC744 \uADE0\uD615\uC801\uC73C\uB85C \uC720\uC9C0\uD558\uC138\uC694.',
    underweight: 'Underweight (\uBE44\uC911 \uCD95\uC18C)\n\uD604\uC7AC \uD658\uACBD\uC5D0\uC11C \uC774 \uC139\uD130\uAC00 \uBD88\uB9AC\uD569\uB2C8\uB2E4.\n\uD3EC\uD2B8\uD3F4\uB9AC\uC624\uC5D0\uC11C \uBE44\uC911\uC744 \uC904\uC774\uB294 \uAC83\uC774 \uC88B\uC2B5\uB2C8\uB2E4.',
  },
  top_picks: 'BUY \uC2DC\uADF8\uB110 \uC885\uBAA9 \uC911 \uC810\uC218\uAC00 \uAC00\uC7A5 \uB192\uC740 \uC0C1\uC704 \uC885\uBAA9.\n\uAE30\uC220\uC801 \uBD84\uC11D + \uB9E4\uD06C\uB85C + \uC218\uAE09 + \uB274\uC2A4 \uC810\uC218\uB97C \uC885\uD569\uD558\uC5EC\n\uC21C\uC704\uB97C \uC0B0\uCD9C\uD558\uACE0, \uD074\uB9AD\uD558\uBA74 \uC0C1\uC138\uD55C \uADFC\uAC70\uB97C \uD655\uC778\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.',
  col_score: '\uC885\uD569 \uD22C\uC790 \uC810\uC218.\n\uAE30\uC220\uC801 \uBD84\uC11D(RSI/MACD/\uC774\uACA9\uB3C4 \uB4F1), \uB9E4\uD06C\uB85C \uC870\uAC74,\n\uC218\uAE09 \uB3D9\uD5A5, \uB274\uC2A4 \uBD84\uC11D\uC744 \uAC00\uC911 \uD569\uC0B0\uD55C \uAC12.\n\uB192\uC744\uC218\uB85D \uB9E4\uC218 \uADFC\uAC70\uAC00 \uAC15\uD568.',
  col_rsi: 'RSI (\uC0C1\uB300\uAC15\uB3C4\uC9C0\uC218, 0~100).\n30 \uC774\uD558: \uACFC\uB9E4\uB3C4 (\uBC18\uB4F1 \uAC00\uB2A5\uC131 \uB192\uC74C)\n30~50: \uC57D\uC138\n50~70: \uC815\uC0C1~\uAC15\uC138\n70 \uC774\uC0C1: \uACFC\uB9E4\uC218 (\uC870\uC815 \uC8FC\uC758)',
  col_current: '\uD574\uB2F9 \uC885\uBAA9\uC758 \uD604\uC7AC \uC2DC\uC7A5\uAC00 (\uCD5C\uC2E0 \uC885\uAC00 \uAE30\uC900).',
  col_target: '\uBAA9\uD45C \uB9E4\uB3C4\uAC00.\nRSI\uC640 \uC2DC\uADF8\uB110 \uAC15\uB3C4\uC5D0 \uB530\uB77C \uC0B0\uCD9C.\nRSI \uB0AE\uC744\uC218\uB85D \uD0C0\uAC9F \uB192\uC74C (+8~15%).',
  col_stoploss: '\uC190\uC808 \uAE30\uC900\uAC00.\n\uC774 \uAC00\uACA9 \uC774\uD558\uB85C \uD558\uB77D \uC2DC \uC190\uC808 \uB9E4\uB3C4 \uAD8C\uC7A5.\n\uAE30\uBCF8\uAC12: \uD604\uC7AC\uAC00 \uB300\uBE44 -7%.',
  col_rr: 'R:R (\uBCF4\uC0C1/\uC704\uD5D8 \uBE44\uC728).\n(\uBAA9\uD45C\uAC00 - \uD604\uC7AC\uAC00) / (\uD604\uC7AC\uAC00 - \uC190\uC808\uAC00).\n1.5 \uC774\uC0C1\uC774\uBA74 \uB9E4\uB825\uC801, 2 \uC774\uC0C1 \uC6B0\uC218.\n\uAC12\uC774 \uB192\uC744\uC218\uB85D \uAE30\uB300 \uC218\uC775 \uB300\uBE44 \uC704\uD5D8\uC774 \uC791\uC74C.',
  col_amount: '\uCF08\uB9AC \uACF5\uC2DD \uAE30\uBC18 \uAD8C\uC7A5 \uD22C\uC790 \uAE08\uC561.\n\uC2DC\uADF8\uB110 \uC810\uC218\uC640 \uD655\uC2E0\uB3C4\uC5D0 \uB530\uB77C \uD55C \uBC88\uC5D0 \uD22C\uC790\uD560\n\uCD5C\uC801 \uAE08\uC561\uACFC \uBE44\uC911(%).\n\uC804\uCCB4 \uC790\uBCF8 \uB300\uBE44 \uBE44\uC728\uC744 \uD568\uAED8 \uD45C\uC2DC.',
  target_return: '\uBAA9\uD45C \uC218\uC775\uB960.\n\uD604\uC7AC\uAC00 \uB300\uBE44 \uBAA9\uD45C\uAC00\uAE4C\uC9C0\uC758 \uAE30\uB300 \uC218\uC775\uB960(%).\nRSI\uAC00 \uB0AE\uC744\uC218\uB85D(30 \uBBF8\uB9CC) \uB354 \uB192\uC740 \uBAA9\uD45C \uC124\uC815.',
  confidence: '\uD22C\uC790 \uD655\uC2E0\uB3C4.\n\uC2DC\uADF8\uB110\uC758 \uB2E4\uC591\uD55C \uC9C0\uD45C\uAC00 \uC5BC\uB9C8\uB098 \uC77C\uCE58\uD558\uB294\uC9C0 \uBCF4\uC5EC\uC8FC\uB294 \uAC12.\n\uB192\uC744\uC218\uB85D \uC5EC\uB7EC \uC9C0\uD45C\uAC00 \uAC19\uC740 \uBC29\uD5A5\uC744 \uAC00\uB9AC\uD0B4.',
  portfolio_actions: '\uD604\uC7AC \uBCF4\uC720 \uC911\uC778 \uC885\uBAA9\uB4E4\uC758 \uC218\uC775\uB960, \uC2DC\uADF8\uB110\uC744 \uBD84\uC11D\uD558\uC5EC\n\uC790\uB3D9 \uC0DD\uC131\uB41C \uC561\uC158 \uC81C\uC548.\n\uC190\uC808(-7%), \uC775\uC808(+15%), \uBD80\uBD84\uC775\uC808(+10%) \uB4F1\n\uADDC\uCE59 \uAE30\uBC18\uC73C\uB85C \uD310\uB2E8\uD569\uB2C8\uB2E4.',
  action_type: {
    CUT_LOSS: '\uC190\uC808 \uB9E4\uB3C4\n\uC190\uC2E4\uC774 -7% \uC774\uC0C1. \uC989\uC2DC \uC815\uB9AC \uAD8C\uC7A5.\n\uCD94\uAC00 \uD558\uB77D \uBCF4\uB2E4 \uC190\uC2E4 \uD655\uC815\uC744 \uD1B5\uD574 \uC790\uBCF8 \uBCF4\uC804.',
    TAKE_PROFIT: '\uC775\uC808 \uB9E4\uB3C4\n\uC218\uC775\uC774 +15% \uC774\uC0C1. \uCC28\uC775 \uC2E4\uD604 \uAD8C\uC7A5.\n\uBAA9\uD45C \uC218\uC775 \uB2EC\uC131, \uCD5C\uC18C 50% \uC774\uC0C1 \uCC28\uC775 \uC2E4\uD604.',
    PARTIAL_PROFIT: '\uBD80\uBD84 \uC775\uC808\n\uC218\uC775 +10~15% \uAD6C\uAC04. \uC804\uCCB4\uAC00 \uC544\uB2CC \uC77C\uBD80 \uB9E4\uB3C4\uB85C\n\uC218\uC775\uC744 \uD655\uBCF4\uD558\uBA74\uC11C \uC0C1\uC2B9 \uC5EC\uB825\uB3C4 \uB0A8\uAE40.',
    ADD_MORE: '\uCD94\uAC00 \uB9E4\uC218\n\uD604\uC7AC BUY \uC2DC\uADF8\uB110 \uC9C0\uC18D. \uAE30\uC874 \uD3EC\uC9C0\uC158\uC5D0\n\uCD94\uAC00 \uB9E4\uC218\uB85C \uD3C9\uADE0 \uB2E8\uAC00\uB97C \uC870\uC815\uD558\uAC70\uB098 \uBE44\uC911 \uD655\uB300.',
    REDUCE: '\uBE44\uC911 \uCD95\uC18C\nSELL \uC2DC\uADF8\uB110 \uBC1C\uC0DD. \uC804\uCCB4 \uB9E4\uB3C4\uBCF4\uB2E4\uB294\n\uC77C\uBD80 \uBE44\uC911\uC744 \uC904\uC5EC \uC704\uD5D8 \uAD00\uB9AC.',
    WATCH_CLOSELY: '\uC8FC\uC758 \uAD00\uCC30\n\uC190\uC808\uC120(-7%) \uC811\uADFC \uC911. \uCD94\uAC00 \uD558\uB77D \uC2DC\n\uC989\uC2DC \uB300\uC751\uD560 \uC900\uBE44 \uD544\uC694.',
    HOLD: '\uBCF4\uC720 \uC720\uC9C0\n\uD2B9\uBCC4\uD55C \uC561\uC158 \uD544\uC694 \uC5C6\uC74C.\n\uD604\uC7AC \uC2DC\uADF8\uB110 HOLD, \uAE30\uC874 \uD3EC\uC9C0\uC158 \uC720\uC9C0.',
  },
  signal_badge: {
    BUY: 'BUY \uC2DC\uADF8\uB110: VIBE \uD30C\uC774\uD504\uB77C\uC778\uC774 \uB9E4\uC218 \uAD8C\uC7A5\uC73C\uB85C \uD310\uB2E8\uD55C \uC885\uBAA9.',
    SELL: 'SELL \uC2DC\uADF8\uB110: VIBE \uD30C\uC774\uD504\uB77C\uC778\uC774 \uB9E4\uB3C4/\uC815\uB9AC \uAD8C\uC7A5\uC73C\uB85C \uD310\uB2E8\uD55C \uC885\uBAA9.',
    HOLD: 'HOLD \uC2DC\uADF8\uB110: \uD604\uC7AC \uAD00\uB9DD, \uB9E4\uC218/\uB9E4\uB3C4 \uADFC\uAC70 \uBD80\uC871.',
  },
  weekly_outlook: '\uC774\uBC88 \uC8FC \uC2DC\uC7A5 \uC804\uB9DD \uC694\uC57D.\n\uB9E4\uD06C\uB85C \uD658\uACBD, \uACF5\uD3EC/\uD0D0\uC695 \uC9C0\uC218, \uD22C\uC790 \uC2DC\uACC4\uB97C \uC885\uD569\uD558\uC5EC\n\uD5A5\uD6C4 1\uC8FC\uAC04 \uC804\uB9DD\uACFC \uC8FC\uC758\uC0AC\uD56D\uC744 \uC815\uB9AC\uD569\uB2C8\uB2E4.',
  watch_list: '\uC774\uBC88 \uC8FC \uD2B9\uBCC4\uD788 \uBAA8\uB2C8\uD130\uB9C1\uD574\uC57C \uD560 \uC9C0\uD45C\uC640 \uC774\uBCA4\uD2B8.\n\uD574\uB2F9 \uD56D\uBAA9\uC758 \uBCC0\uD654\uC5D0 \uB530\uB77C \uC804\uB7B5 \uC870\uC815\uC774 \uD544\uC694\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.',
  guru_consensus: '8\uBA85\uC758 \uD22C\uC790 \uB300\uAC00(Buffett, Soros, Dalio \uB4F1)\uC758\n\uD22C\uC790 \uD504\uB808\uC784\uC6CC\uD06C\uB85C \uD604\uC7AC \uC2DC\uC7A5\uC744 \uBD84\uC11D\uD55C \uACB0\uACFC.\n\uAC01 \uAD6C\uB8E8\uC758 \uC804\uB7B5\uC774 \uAC15\uC138/\uC57C\uC138/\uAD00\uB9DD \uC911\n\uC5B4\uB290 \uCABD\uC5D0 \uD3B8\uD5A5\uB418\uC5B4 \uC788\uB294\uC9C0 \uBCF4\uC5EC\uC90D\uB2C8\uB2E4.',
  guru_conviction: '\uAD6C\uB8E8\uB4E4\uC758 \uD3C9\uADE0 \uD655\uC2E0\uB3C4.\n0%: \uD310\uB2E8 \uBD88\uD655\uC2E4, 100%: \uB9E4\uC6B0 \uAC15\uD55C \uD655\uC2E0.\n50% \uBBF8\uB9CC\uC774\uBA74 \uC758\uACAC\uC774 \uBD84\uC0B0, 70% \uC774\uC0C1\uC774\uBA74 \uAC15\uD55C \uD569\uC758.',
}
