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
    { label: '① Peak Fear → 역발상 분할 매수', value: `Fear: ${fp}`, active: activeIdx === 0, skipped: activeIdx < 0 },
    { label: '② Initial Panic → 방어 태세', value: `Fear: ${fp}`, active: activeIdx === 1, skipped: activeIdx < 1 },
    { label: '③ Risk ≥ 75 → 매우 보수적', value: `Risk: ${rs}`, active: activeIdx === 2, skipped: activeIdx < 2 },
    { label: '④ Risk ≥ 60 → 신중 접근', value: `Risk: ${rs}`, active: activeIdx === 3, skipped: activeIdx < 3 },
    { label: '⑤ 가을/겨울장세 → 신중 접근', value: `Season: ${SEASON_KR[sn] || sn}`, active: activeIdx === 4, skipped: activeIdx < 4 },
    { label: '⑥ Risk ≤ 30 + 봄/여름 → 적극 매수', value: `Risk: ${rs}, ${SEASON_KR[sn] || sn}`, active: activeIdx === 5, skipped: activeIdx < 5 },
    { label: '⑦ Risk ≤ 45 → 완만한 매수', value: `Risk: ${rs}`, active: activeIdx === 6, skipped: activeIdx < 6 },
    { label: '⑧ 기본값 → 중립 관망', value: '', active: activeIdx === 7, skipped: activeIdx < 7 },
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
      .catch(err => { setError(err.message); toast.error('액션 플랜 로드 실패') })
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
          <h2>{'🎯'} 액션 플랜</h2>
          <p className="subtitle">{data.date} — {'하라는대로만 해도 수익을 내는 시스템'}</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button className="btn btn-outline" onClick={loadData}>{'↻'} Refresh</button>
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
                {'▸'} {strategy.stance_reason}
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
          {'🧠'}{' '}
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
                {rule.active ? '▶' : rule.skipped ? '─' : '│'}
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
          {'⚡'}{' '}
          <Tip text={TIPS.action_items} indicator>{'오늘의 전략 액션'}</Tip>
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
                <span>{item.priority === 1 ? '🔴' : item.priority === 2 ? '🟡' : '⚪'}</span>
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
            {'🔄'}{' '}
            <Tip text={TIPS.sector_bias} indicator>{'섹터 배분 전략'}</Tip>
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
            {'🏆'}{' '}
            <Tip text={TIPS.top_picks} indicator>{'추천 매수 TOP'} {top_picks.length}</Tip>
          </h3>
          <div className="table-responsive">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>SYMBOL</th>
                  <th><Tip text={TIPS.col_score} indicator>SCORE</Tip></th>
                  <th><Tip text={TIPS.col_rsi} indicator>RSI</Tip></th>
                  <th><Tip text={TIPS.col_current} indicator>{'현재가'}</Tip></th>
                  <th><Tip text={TIPS.col_target} indicator>{'목표가'}</Tip></th>
                  <th><Tip text={TIPS.col_stoploss} indicator>{'손절가'}</Tip></th>
                  <th><Tip text={TIPS.col_rr} indicator>R:R</Tip></th>
                  <th><Tip text={TIPS.col_amount} indicator>{'추천 금액'}</Tip></th>
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
                <Tip text={TIPS.target_return} indicator>{'목표 수익률'}</Tip>: +{top_picks[expandedPick].target_return_pct}% |{' '}
                <Tip text={TIPS.confidence} indicator>{'확신도'}</Tip>: {top_picks[expandedPick].confidence}%
              </div>
            </div>
          )}
        </div>
      )}

      {/* Portfolio Actions */}
      {portfolio_actions?.length > 0 && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>
            {'💼'}{' '}
            <Tip text={TIPS.portfolio_actions} indicator>{'보유 종목 액션'}</Tip>
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
            {'📅'}{' '}
            <Tip text={TIPS.weekly_outlook} indicator>{'주간 전망'}</Tip>
          </h3>
          <p style={{ color: 'var(--text-secondary)', lineHeight: 1.7, fontSize: '0.9rem' }}>
            {strategy.weekly_outlook.summary_kr}
          </p>
          {strategy.weekly_outlook.watch_items?.length > 0 && (
            <div style={{ marginTop: '0.75rem' }}>
              <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                <Tip text={TIPS.watch_list} indicator>
                  {'👁️'} Watch List
                </Tip>
              </div>
              {strategy.weekly_outlook.watch_items.map((w, i) => (
                <div key={i} style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', padding: '0.2rem 0' }}>
                  {'•'} {w}
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
            {'🎯'}{' '}
            <Tip text={TIPS.guru_consensus} indicator>{'구루 컨센서스'}</Tip>
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              {strategy.guru_summary.consensus_kr}
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              ({strategy.guru_summary.guru_count}{'명'}{' '}
              <Tip text={TIPS.guru_conviction} indicator>{'평균 확신도'}</Tip> {strategy.guru_summary.avg_conviction}%)
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Tooltip text definitions ──────────────────────────────────────────────
const TIPS = {
  stance: '현재 시장 상황을 종합 분석하여 결정된 투자 전략 방향.\n• 역발상 매수: 시장 공포 구간에서 분할 매수 기회\n• 공격적: 상승 추세 강화, 적극 매수\n• 중립: 방향성 탐색 중, 관망\n• 방어적: 하락 위험 높음, 현금 비중 확대',
  stance_logic: '스탠스 결정 우선순위.\n① 공포 국면 → ② 패닉 초기 → ③~④ 리스크 점수 → ⑤ 시장 계절 → ⑥~⑧ 기본값.\n위쪽 규칙이 트리거되면 아래 규칙은 무시됩니다.\n예: 공포 초기면 리스크 점수가 낮아도 방어 태세.',
  risk_score: '매크로 위험 점수 (0~100).\n스태그플레이션 지수(40%) + 위험 레짐(30%) + 투자시계(30%)를 종합한 값.\n낮을수록 안전, 높을수록 위험.',
  fear_phase: '공포 국면 분석 (Fear Gauge).\nVIX 변화율, F&G 모멘텀, Put/Call 비율을 종합.\n• Calm: 평온한 시장\n• Initial Panic: 공포 시작\n• Peak Fear: 공포 극점 (역발상 매수 기회)\n• Post-Peak: 공포 후퇴 (회복 시작)',
  season: '시장 계절 분석.\n경기 순환과 통화 정책에 따라 투자 시계의 4사분면을 분석.\nRecovery / Reflation / Overheat / Stagflation',
  cash_ratio: '현재 시장 위험도에 따른 권장 현금 비중.\n위험이 높을수록 현금 비중을 높여 방어,\n낮을수록 투자 비중 확대 권장.',
  signal_summary: 'VIBE 파이프라인이 분석한 전체 종목 시그널 요약.\nBUY: 매수 시그널 종목 수\nSELL: 매도 시그널 종목 수\nHOLD: 관망/유지 종목 수',
  action_items: '오늘 수행해야 할 투자 액션 목록.\n우선순위 순으로 정렬되어 있으며,\n각 항목에는 구체적인 실행 방법이 포함.',
  priority: {
    1: '🔴 최우선 (Priority 1)\n가장 먼저 실행해야 할 핵심 전략.',
    2: '🟡 중요 (Priority 2)\n핵심 전략 다음으로 실행할 보조 전략.',
    3: '⚪ 참고 (Priority 3)\n여유가 될 때 참고할 부가 정보.',
  },
  sector_bias: '현재 시장 환경에 따라 섹터별 비중 조절 권장.\nVIX, 금리, 유가, 환율 등 매크로 지표를 분석하여\n각 섹터의 투자 비중을 제안합니다.',
  bias_label: {
    overweight: 'Overweight (비중 확대)\n현재 시장 환경에서 이 섹터가 유리합니다.\n포트폴리오에서 비중을 다소 높이는 것이 좋습니다.',
    neutral: 'Neutral (중립)\n특별한 비중 조절 필요 없음.\n기존 비중을 균형적으로 유지하세요.',
    underweight: 'Underweight (비중 축소)\n현재 환경에서 이 섹터가 불리합니다.\n포트폴리오에서 비중을 줄이는 것이 좋습니다.',
  },
  top_picks: 'BUY 시그널 종목 중 점수가 가장 높은 상위 종목.\n기술적 분석 + 매크로 + 수급 + 뉴스 점수를 종합하여\n순위를 산출하고, 클릭하면 상세한 근거를 확인할 수 있습니다.',
  col_score: '종합 투자 점수.\n기술적 분석(RSI/MACD/이격도 등), 매크로 조건,\n수급 동향, 뉴스 분석을 가중 합산한 값.\n높을수록 매수 근거가 강함.',
  col_rsi: 'RSI (상대강도지수, 0~100).\n30 이하: 과매도 (반등 가능성 높음)\n30~50: 약세\n50~70: 정상~강세\n70 이상: 과매수 (조정 주의)',
  col_current: '해당 종목의 현재 시장가 (최신 종가 기준).',
  col_target: '목표 매도가.\nRSI와 시그널 강도에 따라 산출.\nRSI 낮을수록 타겟 높음 (+8~15%).',
  col_stoploss: '손절 기준가.\n이 가격 이하로 하락 시 손절 매도 권장.\n기본값: 현재가 대비 -7%.',
  col_rr: 'R:R (보상/위험 비율).\n(목표가 - 현재가) / (현재가 - 손절가).\n1.5 이상이면 매력적, 2 이상 우수.\n값이 높을수록 기대 수익 대비 위험이 작음.',
  col_amount: '켈리 공식 기반 권장 투자 금액.\n시그널 점수와 확신도에 따라 한 번에 투자할\n최적 금액과 비중(%).\n전체 자본 대비 비율을 함께 표시.',
  target_return: '목표 수익률.\n현재가 대비 목표가까지의 기대 수익률(%).\nRSI가 낮을수록(30 미만) 더 높은 목표 설정.',
  confidence: '투자 확신도.\n시그널의 다양한 지표가 얼마나 일치하는지 보여주는 값.\n높을수록 여러 지표가 같은 방향을 가리킴.',
  portfolio_actions: '현재 보유 중인 종목들의 수익률, 시그널을 분석하여\n자동 생성된 액션 제안.\n손절(-7%), 익절(+15%), 부분익절(+10%) 등\n규칙 기반으로 판단합니다.',
  action_type: {
    CUT_LOSS: '손절 매도\n손실이 -7% 이상. 즉시 정리 권장.\n추가 하락 보다 손실 확정을 통해 자본 보전.',
    TAKE_PROFIT: '익절 매도\n수익이 +15% 이상. 차익 실현 권장.\n목표 수익 달성, 최소 50% 이상 차익 실현.',
    PARTIAL_PROFIT: '부분 익절\n수익 +10~15% 구간. 전체가 아닌 일부 매도로\n수익을 확보하면서 상승 여력도 남김.',
    ADD_MORE: '추가 매수\n현재 BUY 시그널 지속. 기존 포지션에\n추가 매수로 평균 단가를 조정하거나 비중 확대.',
    REDUCE: '비중 축소\nSELL 시그널 발생. 전체 매도보다는\n일부 비중을 줄여 위험 관리.',
    WATCH_CLOSELY: '주의 관찰\n손절선(-7%) 접근 중. 추가 하락 시\n즉시 대응할 준비 필요.',
    HOLD: '보유 유지\n특별한 액션 필요 없음.\n현재 시그널 HOLD, 기존 포지션 유지.',
  },
  signal_badge: {
    BUY: 'BUY 시그널: VIBE 파이프라인이 매수 권장으로 판단한 종목.',
    SELL: 'SELL 시그널: VIBE 파이프라인이 매도/정리 권장으로 판단한 종목.',
    HOLD: 'HOLD 시그널: 현재 관망, 매수/매도 근거 부족.',
  },
  weekly_outlook: '이번 주 시장 전망 요약.\n매크로 환경, 공포/탐욕 지수, 투자 시계를 종합하여\n향후 1주간 전망과 주의사항을 정리합니다.',
  watch_list: '이번 주 특별히 모니터링해야 할 지표와 이벤트.\n해당 항목의 변화에 따라 전략 조정이 필요할 수 있습니다.',
  guru_consensus: '8명의 투자 대가(Buffett, Soros, Dalio 등)의\n투자 프레임워크로 현재 시장을 분석한 결과.\n각 구루의 전략이 강세/야세/관망 중\n어느 쪽에 편향되어 있는지 보여줍니다.',
  guru_conviction: '구루들의 평균 확신도.\n0%: 판단 불확실, 100%: 매우 강한 확신.\n50% 미만이면 의견이 분산, 70% 이상이면 강한 합의.',
}
