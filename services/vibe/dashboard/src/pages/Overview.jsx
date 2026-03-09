import { useState, useEffect, useCallback } from 'react'
import {
  getSummary, getSignals, getLatestSentiment,
  getPortfolioGroups, getPortfolio, getActionPlan,
  getFearGauge, getUnifiedRiskScore,
} from '../api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie
} from 'recharts'
import SymbolModal from '../components/SymbolModal'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import Tip from '../components/Tip'
import { useToast } from '../components/Toast'

/* ─────── Quick-nav card definitions ─────── */
const QUICK_NAV = [
  {
    id: 'action-plan',
    icon: '\uD83D\uDCCB',
    title: '오늘의 액션 플랜',
    desc: '전략 스탠스, 추천 종목, 포트폴리오 조치',
    gradient: 'linear-gradient(135deg, rgba(59,130,246,0.15), rgba(99,102,241,0.1))',
    border: 'rgba(59,130,246,0.3)',
  },
  {
    id: 'signals',
    icon: '\u26A1',
    title: '시그널 분석',
    desc: '종목별 BUY/SELL/HOLD 상세 분석',
    gradient: 'linear-gradient(135deg, rgba(34,197,94,0.12), rgba(22,163,74,0.08))',
    border: 'rgba(34,197,94,0.3)',
  },
  {
    id: 'macro',
    icon: '\uD83C\uDF10',
    title: '매크로·레짐 분석',
    desc: '시장 국면, 투자 시계, 섹터 영향도',
    gradient: 'linear-gradient(135deg, rgba(234,179,8,0.12), rgba(245,158,11,0.08))',
    border: 'rgba(234,179,8,0.3)',
  },
  {
    id: 'portfolio',
    icon: '\uD83D\uDCBC',
    title: '포트폴리오 현황',
    desc: '보유 종목, 손익, 리밸런싱 필요 여부',
    gradient: 'linear-gradient(135deg, rgba(168,85,247,0.12), rgba(139,92,246,0.08))',
    border: 'rgba(168,85,247,0.3)',
  },
]

export default function Overview({ onNavigate, refreshKey }) {
  const toast = useToast()
  const [summary, setSummary] = useState(null)
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [sentimentData, setSentimentData] = useState(null)
  const [portfolioAgg, setPortfolioAgg] = useState({ holdings: 0, pnl: 0 })
  const [actionBrief, setActionBrief] = useState(null)
  const [riskScore, setRiskScore] = useState(null)
  const [fearGauge, setFearGauge] = useState(null)

  const loadData = useCallback(() => {
    return Promise.all([
      getSummary(0),
      getSignals(),
      getLatestSentiment().catch(() => null),
      getPortfolioGroups().catch(() => ({ groups: [] })),
      getActionPlan().catch(() => null),
      getUnifiedRiskScore().catch(() => null),
      getFearGauge().catch(() => null),
    ])
      .then(async ([s, sig, sent, groupsRes, plan, risk, fear]) => {
        setSummary(s); setSignals(sig); setError(null)
        setSentimentData(sent)
        setActionBrief(plan)
        setRiskScore(risk)
        setFearGauge(fear)

        const groups = groupsRes?.groups || []
        if (groups.length > 0) {
          const portfolios = await Promise.all(
            groups.map(g => getPortfolio(null, g.id).catch(() => ({ positions: [] })))
          )
          let totalValue = 0, totalInvested = 0, totalHoldings = 0
          portfolios.forEach(p => {
            const positions = p?.positions || []
            positions.forEach(pos => {
              totalHoldings++
              const size = pos.position_size || 0
              const entry = pos.entry_price || 0
              if (pos.current_price != null && entry > 0) {
                totalInvested += size
                totalValue += size * pos.current_price / entry
              }
            })
          })
          const aggPnl = totalInvested > 0 ? ((totalValue - totalInvested) / totalInvested * 100) : 0
          setPortfolioAgg({ holdings: totalHoldings, pnl: +aggPnl.toFixed(2) })
        }
      })
      .catch(err => { console.error(err); setError(err.message); toast.error('데이터 로드 실패: ' + err.message) })
  }, [])

  useEffect(() => {
    loadData().finally(() => setLoading(false))
  }, [loadData, refreshKey])

  useEffect(() => {
    const interval = setInterval(() => {
      loadData().catch(err => { console.error('Auto-refresh error:', err); toast.warn('자동 갱신 실패') })
    }, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [loadData])

  if (loading) return <div className="loading"><span className="spinner" /> 로딩 중...</div>
  if (error) return <div className="loading" style={{ color: 'var(--red)' }}>오류: {error}</div>
  if (!summary) return <div className="loading">데이터 없음</div>

  const {
    signals: sigCounts = {},
    portfolio = {},
    pipelines = {},
    data = {},
    hard_limit_count = 0,
  } = summary || {}
  const pKR = pipelines.KR || {}
  const pUS = pipelines.US || {}
  const totalSignals = (sigCounts.BUY || 0) + (sigCounts.SELL || 0) + (sigCounts.HOLD || 0)

  // Strategy brief from action plan
  const strategy = actionBrief?.strategy
  const rawStance = strategy?.stance || ''
  const STANCE_MAP = {
    'aggressive_buy': '적극 매수',
    'contrarian_buy': '역발상 매수',
    'selective_buy': '선별 매수',
    'neutral': '중립',
    'cautious': '신중',
    'defensive': '방어',
    'strong_sell': '강력 매도',
  }
  const stanceName = STANCE_MAP[rawStance] || rawStance
  const stanceColor = (rawStance.includes('buy') || rawStance.includes('aggressive')) ? 'var(--green)'
    : (rawStance.includes('defensive') || rawStance.includes('sell') || rawStance.includes('cautious')) ? 'var(--red)'
    : rawStance.includes('neutral') ? 'var(--yellow)'
    : 'var(--accent)'
  const riskVal = riskScore?.score
  const fearPhase = fearGauge?.phase
  const fgIndex = sentimentData?.fear_greed_index

  const pieData = [
    { name: 'BUY', value: sigCounts.BUY || 0, color: '#22c55e' },
    { name: 'SELL', value: sigCounts.SELL || 0, color: '#ef4444' },
    { name: 'HOLD', value: sigCounts.HOLD || 0, color: '#eab308' },
  ].filter(d => d.value > 0)

  const seenSymbols = new Set()
  const topSignals = [...signals]
    .sort((a, b) => Math.abs(b.raw_score) - Math.abs(a.raw_score))
    .filter(s => {
      const key = `${s.symbol}-${s.market}`
      if (seenSymbols.has(key)) return false
      seenSymbols.add(key)
      return true
    })
    .slice(0, 8)

  const barData = topSignals.map(s => ({
    name: s.name || s.symbol,
    score: s.raw_score,
    signal: s.final_signal,
  }))

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'\u2302'} 오버뷰</h2>
          <p className="subtitle">
            최근 분석: {summary.latest_signal_date || 'N/A'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button className="btn btn-outline" onClick={() => { setLoading(true); loadData().finally(() => setLoading(false)) }}>
            {'\u21BB'} 새로고침
          </button>
          <HelpButton section="overview" onNavigate={onNavigate} />
        </div>
      </div>

      <PageGuide
        pageId="overview"
        title="VIBE 대시보드 시작하기"
        steps={[
          '오늘의 시장 상태 → 전략 스탠스 + 리스크 점수 확인',
          '액션 플랜 보기 → 오늘 해야 할 매매 액션',
          'KPI 카드 → BUY/SELL 종목 수, 포트폴리오 손익',
          '빠른 이동 카드 → 필요한 분석 페이지로 직행',
        ]}
      />

      {/* ── Today's Situation Banner ── */}
      <div style={{
        background: 'linear-gradient(135deg, var(--bg-secondary), rgba(30,41,59,0.8))',
        border: '1px solid var(--border)',
        borderRadius: '0.75rem',
        padding: '1.25rem 1.5rem',
        marginBottom: '1.5rem',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        gap: '1.5rem', flexWrap: 'wrap',
      }}>
        <div style={{ flex: 1, minWidth: '200px' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            오늘의 시장 상태
          </div>
          {strategy ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                <Tip text="전략 스탠스: 현재 시장 상황에 따른 투자 방향. 공격/중립/방어로 구분됩니다.">
                  <span style={{ fontSize: '1.15rem', fontWeight: 700, color: stanceColor }}>
                    {stanceName}
                  </span>
                </Tip>
                {riskVal != null && (
                  <Tip text="통합 리스크 점수 (0~100). 높을수록 위험. 60 이상이면 방어적 포지션 권장.">
                    <span style={{
                      fontSize: '0.75rem', padding: '0.15rem 0.5rem', borderRadius: '0.25rem',
                      background: riskVal > 60 ? 'rgba(239,68,68,0.15)' : riskVal > 35 ? 'rgba(234,179,8,0.15)' : 'rgba(34,197,94,0.15)',
                      color: riskVal > 60 ? '#ef4444' : riskVal > 35 ? '#eab308' : '#22c55e',
                    }}>
                      리스크 {riskVal}
                    </span>
                  </Tip>
                )}
                {fearPhase && (
                  <Tip text="공포 게이지: VIX 속도 + F&G 모멘텀 기반 시장 공포 위상. Calm/Initial Panic/Peak Fear/Post-Peak.">
                    <span style={{
                      fontSize: '0.75rem', padding: '0.15rem 0.5rem', borderRadius: '0.25rem',
                      background: fearPhase === 'Calm' ? 'rgba(34,197,94,0.15)'
                        : fearPhase === 'Post-Peak' ? 'rgba(59,130,246,0.15)'
                        : 'rgba(239,68,68,0.15)',
                      color: fearPhase === 'Calm' ? '#22c55e'
                        : fearPhase === 'Post-Peak' ? '#3b82f6'
                        : '#ef4444',
                    }}>
                      {fearPhase}
                    </span>
                  </Tip>
                )}
              </div>
              <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                {strategy.headline || strategy.rationale || (() => {
                  const cash = strategy.cash_ratio
                  const sigSum = actionBrief?.signal_summary
                  const parts = []
                  if (cash != null) parts.push(`현금 비중 ${cash}% 권장`)
                  if (sigSum) parts.push(`BUY ${sigSum.buy_count || 0} / SELL ${sigSum.sell_count || 0} / HOLD ${sigSum.hold_count || 0}`)
                  return parts.length > 0 ? parts.join(' · ') : '액션 플랜에서 상세 전략을 확인하세요'
                })()}
              </p>
            </>
          ) : (
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>
              파이프라인 실행 후 오늘의 전략이 표시됩니다
            </p>
          )}
        </div>
        <button
          className="btn btn-primary"
          onClick={() => onNavigate('action-plan')}
          style={{ whiteSpace: 'nowrap', padding: '0.6rem 1.25rem' }}
        >
          {'\uD83D\uDCCB'} 액션 플랜 보기 {'\u2192'}
        </button>
      </div>

      {/* ── Quick Navigation Cards ── */}
      {(() => {
        const quickCards = [
          {
            ...QUICK_NAV[0],
            badge: stanceName || null,
            badgeColor: stanceColor,
          },
          {
            ...QUICK_NAV[1],
            badge: totalSignals > 0 ? `BUY ${sigCounts.BUY || 0}` : null,
            badgeColor: 'var(--green)',
          },
          {
            ...QUICK_NAV[2],
            badge: riskVal != null ? `리스크 ${riskVal}` : null,
            badgeColor: riskVal > 60 ? 'var(--red)' : riskVal > 35 ? 'var(--yellow)' : 'var(--green)',
          },
          {
            ...QUICK_NAV[3],
            badge: portfolioAgg.holdings > 0 ? `${portfolioAgg.pnl >= 0 ? '+' : ''}${portfolioAgg.pnl}%` : null,
            badgeColor: portfolioAgg.pnl >= 0 ? 'var(--green)' : 'var(--red)',
          },
        ]
        return (
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '0.75rem', marginBottom: '1.5rem',
          }}>
            {quickCards.map(nav => (
              <div
                key={nav.id}
                onClick={() => onNavigate(nav.id)}
                style={{
                  background: nav.gradient,
                  border: `1px solid ${nav.border}`,
                  borderRadius: '0.75rem',
                  padding: '1rem',
                  cursor: 'pointer',
                  transition: 'transform 0.15s, box-shadow 0.15s',
                  position: 'relative',
                }}
                onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.2)' }}
                onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <span style={{ fontSize: '1.5rem' }}>{nav.icon}</span>
                  {nav.badge && (
                    <span style={{
                      fontSize: '0.65rem', fontWeight: 700,
                      padding: '0.1rem 0.4rem', borderRadius: '0.25rem',
                      background: `${nav.badgeColor}20`,
                      color: nav.badgeColor,
                      whiteSpace: 'nowrap',
                    }}>
                      {nav.badge}
                    </span>
                  )}
                </div>
                <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.25rem', marginTop: '0.3rem' }}>{nav.title}</div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>{nav.desc}</div>
              </div>
            ))}
          </div>
        )
      })()}

      {/* ── KPI Cards ── */}
      <div className="card-grid">
        <div className="card">
          <div className="card-label">
            <Tip text="매수 추천 종목 수. 기술적/매크로/수급 분석을 종합한 결과.">BUY 시그널</Tip>
          </div>
          <div className="card-value green">{sigCounts.BUY || 0}</div>
          <div className="card-sub">전체 {totalSignals}개 중</div>
        </div>
        <div className="card">
          <div className="card-label">
            <Tip text="매도 권고 종목 수. 하락 추세 진입 또는 과열 이탈 신호.">SELL 시그널</Tip>
          </div>
          <div className="card-value red">{sigCounts.SELL || 0}</div>
          <div className="card-sub">전체 {totalSignals}개 중</div>
        </div>
        <div className="card">
          <div className="card-label">
            <Tip text="안전장치 발동 횟수. RSI 과열/이격도 초과 시 매수를 강제 차단합니다.">Hard Limit</Tip>
          </div>
          <div className="card-value yellow">{hard_limit_count}</div>
          <div className="card-sub">안전장치 발동</div>
        </div>
        <div className="card">
          <div className="card-label">
            <Tip text="전체 포트폴리오 그룹 합산 손익률.">포트폴리오 P&L</Tip>
          </div>
          <div className={`card-value ${(portfolioAgg.pnl || 0) >= 0 ? 'green' : 'red'}`}>
            {(portfolioAgg.pnl || 0) >= 0 ? '+' : ''}{portfolioAgg.pnl || 0}%
          </div>
          <div className="card-sub">{portfolioAgg.holdings || 0}개 종목 보유</div>
        </div>
        <div className="card">
          <div className="card-label">KR 파이프라인</div>
          <div className="card-value blue" style={{ fontSize: '1rem' }}>
            <span className={`status-dot ${pKR.status === 'completed' ? 'green' : 'red'}`} />
            {pKR.status || 'unknown'}
          </div>
          <div className="card-sub">{pKR.last_run ? new Date(pKR.last_run).toLocaleString('ko-KR') : 'never'}</div>
        </div>
        <div className="card">
          <div className="card-label">US 파이프라인</div>
          <div className="card-value blue" style={{ fontSize: '1rem' }}>
            <span className={`status-dot ${pUS.status === 'completed' ? 'green' : 'red'}`} />
            {pUS.status || 'unknown'}
          </div>
          <div className="card-sub">{pUS.last_run ? new Date(pUS.last_run).toLocaleString('ko-KR') : 'never'}</div>
        </div>
      </div>

      {/* ── Sentiment + Market Context ── */}
      {sentimentData && (
        <div className="grid-2" style={{ marginBottom: '1.5rem' }}>
          <div className="card">
            <div className="card-label">
              <Tip text="CNN Fear & Greed Index. 0(극단적 공포)~100(극단적 탐욕). 시장 심리 수온계.">Fear & Greed Index</Tip>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.75rem', marginBottom: '0.25rem' }}>
              <span className="card-value" style={{
                fontSize: '2rem',
                color: (fgIndex ?? 50) <= 25 ? 'var(--red)'
                  : (fgIndex ?? 50) <= 45 ? 'var(--orange)'
                  : (fgIndex ?? 50) <= 55 ? 'var(--yellow)'
                  : 'var(--green)',
              }}>
                {fgIndex ?? '-'}
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                {(fgIndex ?? 50) <= 25 ? 'Extreme Fear'
                  : (fgIndex ?? 50) <= 45 ? 'Fear'
                  : (fgIndex ?? 50) <= 55 ? 'Neutral'
                  : (fgIndex ?? 50) <= 75 ? 'Greed'
                  : 'Extreme Greed'}
              </span>
            </div>
            <div className="gauge-bar">
              <div className="gauge-fill" style={{
                width: `${Math.min(100, Math.max(0, fgIndex ?? 0))}%`,
                background: `linear-gradient(90deg, var(--red), var(--orange), var(--yellow), var(--green))`,
              }} />
            </div>
            <div className="card-sub" style={{ marginTop: '0.5rem' }}>{sentimentData.indicator_date}</div>
          </div>
          <div className="card">
            <div className="card-label">시장 지표</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Tip text="풋/콜 비율. 1.0 이상이면 풋 옵션 비중 과다 → 시장 공포 감지." indicator>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Put/Call Ratio</span>
                </Tip>
                <span style={{ fontWeight: 600, color: (sentimentData.put_call_ratio ?? 1) > 1.0 ? 'var(--red)' : 'var(--green)' }}>
                  {sentimentData.put_call_ratio?.toFixed(3) ?? '-'}
                </span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Tip text="VIX 기간구조. contango(정상)=안정, backwardation(역전)=단기 공포 급등." indicator>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>VIX Term Structure</span>
                </Tip>
                <span style={{ fontWeight: 600, color: sentimentData.vix_term_structure === 'contango' ? 'var(--green)' : 'var(--red)' }}>
                  {sentimentData.vix_term_structure ?? '-'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Charts Row ── */}
      <div className="grid-2">
        <div className="chart-container">
          <h3>{'\uD83D\uDCC8'} 시그널 분포</h3>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.8rem' }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              파이프라인 실행 후 시그널 분포가 표시됩니다
            </div>
          )}
        </div>

        <div className="chart-container">
          <h3>{'\u26A1'} 스코어 상위 종목</h3>
          {barData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={barData} layout="vertical">
                <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis
                  dataKey="name"
                  type="category"
                  width={100}
                  tick={{ fill: '#94a3b8', fontSize: 10 }}
                  tickFormatter={v => v?.length > 14 ? v.slice(0, 12) + '..' : v}
                />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.8rem' }}
                  formatter={(v) => [v != null ? `${v > 0 ? '+' : ''}${v.toFixed(1)}` : '-', '스코어']}
                />
                <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                  {barData.map((entry) => (
                    <Cell
                      key={entry.name}
                      fill={entry.signal === 'BUY' ? '#22c55e' : entry.signal === 'SELL' ? '#ef4444' : '#eab308'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              최근 시그널이 없습니다
            </div>
          )}
        </div>
      </div>

      {/* ── Latest Signals Table ── */}
      <div className="table-container">
        <div className="table-header">
          <h3>{'\u26A1'} 최근 시그널</h3>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <span className="card-sub">{new Set(signals.map(s => `${s.symbol}-${s.market}`)).size}개 종목</span>
            <button
              className="btn btn-outline btn-sm"
              onClick={() => onNavigate('signals')}
            >
              전체 보기 {'\u2192'}
            </button>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>종목</th>
              <th className="hide-on-mobile">마켓</th>
              <th>시그널</th>
              <th>스코어</th>
              <th className="hide-on-tablet">RSI</th>
              <th className="hide-on-tablet">Hard Limit</th>
              <th className="hide-on-mobile">확신도</th>
            </tr>
          </thead>
          <tbody>
            {(() => {
              const seen = new Set()
              return signals.filter(s => {
                const k = `${s.symbol}-${s.market}`
                if (seen.has(k)) return false
                seen.add(k)
                return true
              }).slice(0, 12)
            })().map((s, idx) => (
              <tr key={`${s.symbol}-${s.market}-${s.signal_date}-${idx}`}>
                <td
                  className="symbol-link"
                  onClick={() => setSelectedSymbol({ symbol: s.symbol, market: s.market })}
                >
                  <strong>{s.name || s.symbol}</strong>
                  <br />
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{s.symbol}</span>
                </td>
                <td className="hide-on-mobile">{s.market}</td>
                <td>
                  <span className={`badge badge-${s.final_signal?.toLowerCase()}`}>
                    {s.final_signal}
                  </span>
                </td>
                <td style={{ color: s.raw_score > 0 ? 'var(--green)' : s.raw_score < 0 ? 'var(--red)' : 'var(--text-secondary)' }}>
                  {s.raw_score?.toFixed(1)}
                </td>
                <td className="hide-on-tablet">{s.rsi_value?.toFixed(1)}</td>
                <td className="hide-on-tablet">
                  {s.hard_limit_triggered
                    ? <span className="badge badge-sell">YES</span>
                    : <span style={{ color: 'var(--text-muted)' }}>-</span>
                  }
                </td>
                <td className="hide-on-mobile">{s.confidence != null ? `${(s.confidence <= 1 ? s.confidence * 100 : s.confidence).toFixed(0)}%` : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Data Stats ── */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <div className="card">
          <div className="card-label">가격 데이터</div>
          <div className="card-value blue">{(data.prices || 0).toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="card-label">누적 시그널</div>
          <div className="card-value blue">{(data.signals_total || 0).toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="card-label">Watchlist</div>
          <div className="card-value blue">{data.watchlist ?? 0}</div>
          <div className="card-sub">활성 종목</div>
        </div>
      </div>

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
