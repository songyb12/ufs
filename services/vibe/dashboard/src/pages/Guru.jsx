import { useState, useEffect, useCallback, useRef } from 'react'
import { getGuruInsights, getGuruLLMAnalysis } from '../api'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import { useToast } from '../components/Toast'

const STANCE_COLORS = {
  bullish: '#22c55e', buy_innovation: '#22c55e', aggressive_buy: '#22c55e',
  accumulate: '#22c55e', rebalance_buy: '#22c55e', systematic_buy: '#22c55e',
  contrarian_long: '#22c55e', growth_hunting: '#22c55e', accumulate_disruptors: '#22c55e',
  neutral: '#eab308', balanced: '#eab308', selective: '#eab308',
  trend_follow: '#eab308', strategic_hold: '#eab308', index_plus: '#eab308',
  risk_parity: '#3b82f6', hold_conviction: '#3b82f6',
  cautious: '#f97316', short_ready: '#f97316', rebalance_trim: '#f97316',
  defensive: '#ef4444', fx_play: '#a855f7',
}

function convictionColor(c) {
  if (c >= 70) return '#22c55e'
  if (c >= 50) return '#eab308'
  if (c >= 35) return '#f97316'
  return '#ef4444'
}

export default function Guru({ onNavigate, refreshKey }) {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expandedGuru, setExpandedGuru] = useState(null)
  const [llmAnalysis, setLLMAnalysis] = useState({})
  const [llmLoading, setLLMLoading] = useState({})

  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])

  const loadData = useCallback(() => {
    setLoading(true)
    getGuruInsights()
      .then(d => { if (mountedRef.current) setData(d) })
      .catch(err => { if (mountedRef.current) toast.error('Load failed: ' + err.message) })
      .finally(() => { if (mountedRef.current) setLoading(false) })
  }, [])

  useEffect(() => { loadData() }, [loadData, refreshKey])

  const handleLLMAnalysis = async (guruId) => {
    if (llmLoading[guruId]) return
    setLLMLoading(prev => ({ ...prev, [guruId]: true }))
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 60000) // 60s timeout
    try {
      const result = await getGuruLLMAnalysis(guruId, { signal: controller.signal })
      if (!mountedRef.current) return
      if (result.status === 'ok') {
        setLLMAnalysis(prev => ({ ...prev, [guruId]: result.analysis }))
      } else {
        toast.error(result.message || 'LLM 분석 실패')
      }
    } catch (err) {
      if (!mountedRef.current) return
      if (err.name === 'AbortError') {
        toast.error('LLM 분석 시간 초과 (60초). 다시 시도해주세요.')
      } else {
        toast.error('LLM: ' + err.message)
      }
    } finally {
      clearTimeout(timeout)
      if (mountedRef.current) setLLMLoading(prev => ({ ...prev, [guruId]: false }))
    }
  }

  if (loading) return <div className="loading"><span className="spinner" /> 로딩 중...</div>
  if (!data?.gurus) return <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>No data</div>

  const gurus = data.gurus
  const macro = data.macro_snapshot || {}

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'🎯'} 구루 인사이트</h2>
          <p className="subtitle">
            투자 대가들의 현재 시장 분석
            {macro.date && <span style={{ marginLeft: '0.5rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>({macro.date})</span>}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button className="btn btn-outline" onClick={loadData}>{'↻'} Refresh</button>
          <HelpButton section="guru" onNavigate={onNavigate} />
        </div>
      </div>

      <PageGuide
        pageId="guru"
        title="구루 인사이트 활용법"
        steps={[
          '각 구루의 투자 스탠스(매수/중립/매도) 확인',
          '확신도 바 → 높을수록 강한 의견',
          'LLM 심층 분석 → AI가 구루 관점 상세 해석',
          '컨센서스 집계 → 액션 플랜 페이지에서 종합 확인',
        ]}
        color="#f97316"
      />

      {/* Macro Snapshot Bar */}
      <div className="card" style={{ marginBottom: '1rem', display: 'flex', gap: '1.5rem', flexWrap: 'wrap', padding: '0.75rem 1rem' }}>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          VIX: <strong style={{ color: (macro.vix || 0) > 25 ? 'var(--red)' : 'var(--text-primary)' }}>{macro.vix?.toFixed(1) ?? '-'}</strong>
        </span>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          F&G: <strong style={{ color: (macro.fear_greed || 50) < 25 ? 'var(--red)' : (macro.fear_greed || 50) > 75 ? 'var(--green)' : 'var(--text-primary)' }}>
            {macro.fear_greed ?? '-'}
          </strong>
        </span>
        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          USD/KRW: <strong>{macro.usd_krw?.toFixed(0) ?? '-'}</strong>
        </span>
      </div>

      {/* Guru Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
        {gurus.map(guru => {
          const view = guru.market_view || {}
          const stanceColor = STANCE_COLORS[view.stance] || '#64748b'
          const isExpanded = expandedGuru === guru.id

          return (
            <div key={guru.id} className="card" style={{
              borderLeft: `3px solid ${stanceColor}`,
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
              onClick={() => setExpandedGuru(isExpanded ? null : guru.id)}
            >
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <span style={{ fontSize: '1.5rem' }}>{guru.avatar}</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>{guru.name_kr}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{guru.org}</div>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{
                    fontSize: '0.75rem', fontWeight: 700, color: stanceColor,
                    padding: '0.15rem 0.4rem', background: `${stanceColor}15`,
                    borderRadius: '4px',
                  }}>
                    {view.stance_kr || '-'}
                  </div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                    {guru.style_kr}
                  </div>
                </div>
              </div>

              {/* Conviction Bar */}
              <div style={{ marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: '0.15rem' }}>
                  <span>Conviction</span>
                  <span style={{ color: convictionColor(view.conviction || 0) }}>{view.conviction || 0}%</span>
                </div>
                <div style={{ background: '#334155', borderRadius: '3px', height: '4px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${view.conviction || 0}%`,
                    height: '100%',
                    borderRadius: '3px',
                    background: convictionColor(view.conviction || 0),
                    transition: 'width 0.3s',
                  }} />
                </div>
              </div>

              {/* Summary */}
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '0.5rem' }}>
                {view.summary_kr || '-'}
              </div>

              {/* Key Points */}
              {view.key_points_kr && view.key_points_kr.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', marginBottom: '0.5rem' }}>
                  {view.key_points_kr.map((pt, i) => (
                    <div key={i} style={{ fontSize: '0.7rem', color: 'var(--text-muted)', padding: '0.15rem 0.3rem', background: 'rgba(255,255,255,0.03)', borderRadius: '3px' }}>
                      {'•'} {pt}
                    </div>
                  ))}
                </div>
              )}

              {/* Expand indicator */}
              <div style={{ textAlign: 'center', fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                {isExpanded ? '▲ Close' : '▼ Picks & Holdings'}
              </div>

              {/* ── Expanded Section ── */}
              {isExpanded && (
                <div style={{ marginTop: '0.75rem', borderTop: '1px solid #334155', paddingTop: '0.75rem' }}
                  onClick={e => e.stopPropagation()}>

                  {/* Stock Picks */}
                  {guru.picks && guru.picks.length > 0 && (
                    <div style={{ marginBottom: '0.75rem' }}>
                      <h4 style={{ fontSize: '0.8rem', marginBottom: '0.4rem', color: stanceColor }}>
                        {'🎯'} Watchlist Picks
                      </h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                        {guru.picks.map((p, i) => (
                          <div key={i} style={{
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                            padding: '0.3rem 0.5rem', background: '#1e293b', borderRadius: '4px',
                            fontSize: '0.75rem',
                          }}>
                            <div>
                              <strong>{p.name}</strong>
                              <span style={{ marginLeft: '0.3rem', color: 'var(--text-muted)' }}>{p.symbol}</span>
                              <span style={{ marginLeft: '0.3rem', fontSize: '0.65rem', color: p.signal === 'BUY' ? 'var(--green)' : p.signal === 'SELL' ? 'var(--red)' : 'var(--text-muted)' }}>
                                {p.signal}
                              </span>
                            </div>
                            <div style={{
                              minWidth: '32px', textAlign: 'center',
                              fontWeight: 700, fontSize: '0.75rem',
                              color: convictionColor(p.fit_score),
                            }}>
                              {p.fit_score}
                            </div>
                          </div>
                        ))}
                        {guru.picks.length > 0 && (
                          <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textAlign: 'right' }}>
                            {guru.picks[0]?.reason_kr}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Known Holdings */}
                  {guru.portfolio && guru.portfolio.top_holdings && guru.portfolio.top_holdings.length > 0 && (
                    <div style={{ marginBottom: '0.75rem' }}>
                      <h4 style={{ fontSize: '0.8rem', marginBottom: '0.3rem' }}>
                        {'💼'} Known Holdings
                        <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
                          {guru.portfolio.source} ({guru.portfolio.as_of})
                        </span>
                      </h4>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                        {guru.portfolio.top_holdings.map((h, i) => {
                          const isOverlap = guru.portfolio.watchlist_overlaps?.includes(h.symbol)
                          return (
                            <span key={i} style={{
                              fontSize: '0.7rem',
                              padding: '0.15rem 0.4rem',
                              borderRadius: '3px',
                              background: isOverlap ? 'rgba(59,130,246,0.15)' : '#1e293b',
                              border: isOverlap ? '1px solid rgba(59,130,246,0.3)' : '1px solid #334155',
                              color: isOverlap ? '#60a5fa' : 'var(--text-secondary)',
                            }}>
                              {h.symbol} {h.weight}%
                            </span>
                          )
                        })}
                      </div>
                      {guru.portfolio.watchlist_overlaps?.length > 0 && (
                        <div style={{ fontSize: '0.6rem', color: '#60a5fa', marginTop: '0.25rem' }}>
                          {'✨'} Watchlist overlap: {guru.portfolio.watchlist_overlaps.join(', ')}
                        </div>
                      )}
                      {guru.portfolio.total_value && (
                        <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                          Total AUM: {guru.portfolio.total_value}
                        </div>
                      )}
                    </div>
                  )}

                  {/* LLM Deep Analysis Button */}
                  <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <button
                      className="btn btn-sm btn-outline"
                      style={{ fontSize: '0.7rem' }}
                      disabled={llmLoading[guru.id]}
                      onClick={() => handleLLMAnalysis(guru.id)}
                    >
                      {llmLoading[guru.id] ? '⏳ Analyzing...' : `🤖 AI Deep Analysis (${guru.name_kr})`}
                    </button>
                  </div>

                  {/* LLM Analysis Result */}
                  {llmAnalysis[guru.id] && (
                    <div style={{
                      marginTop: '0.5rem', padding: '0.5rem',
                      background: 'rgba(139,92,246,0.06)', borderRadius: '4px',
                      border: '1px solid rgba(139,92,246,0.15)',
                      fontSize: '0.75rem', color: 'var(--text-secondary)',
                      whiteSpace: 'pre-wrap', lineHeight: 1.6,
                    }}>
                      {llmAnalysis[guru.id]}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Philosophy Footer */}
      <div className="card" style={{ borderLeft: '3px solid var(--accent)' }}>
        <h3 style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>{'💡'} Investment Philosophies</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '0.4rem' }}>
          {gurus.map(g => (
            <div key={g.id} style={{
              fontSize: '0.7rem', padding: '0.3rem 0.5rem',
              background: 'rgba(59,130,246,0.04)', borderRadius: '4px',
              color: 'var(--text-secondary)',
            }}>
              <strong>{g.avatar} {g.name_kr}</strong>: &ldquo;{g.philosophy_kr}&rdquo;
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
