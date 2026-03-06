import { useState, useEffect, useCallback } from 'react'
import { getMarketBriefings, getLatestBriefing, generateBriefing, analyzeWithAI } from '../api'
import HelpButton from '../components/HelpButton'

export default function MarketBrief({ onNavigate }) {
  const [briefing, setBriefing] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState(null)
  const [selectedDate, setSelectedDate] = useState(null)

  // AI Analysis state
  const [showAIPanel, setShowAIPanel] = useState(false)
  const [aiQuestion, setAIQuestion] = useState('')
  const [aiResult, setAIResult] = useState(null)
  const [aiLoading, setAILoading] = useState(false)

  const loadData = useCallback(() => {
    setLoading(true)
    Promise.all([getLatestBriefing(), getMarketBriefings(10)])
      .then(([latest, hist]) => {
        if (latest && !latest.status) {
          setBriefing(latest)
        } else {
          setBriefing(null)
        }
        setHistory(hist?.briefings || [])
        setError(null)
      })
      .catch(err => { setError(err.message) })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleGenerate = async () => {
    setGenerating(true)
    try {
      const res = await generateBriefing()
      if (res?.briefing) {
        setBriefing(res.briefing)
      }
      loadData()
    } catch (err) {
      setError(`생성 실패: ${err.message}`)
    } finally {
      setGenerating(false)
    }
  }

  const handleAIAnalyze = async (question = null) => {
    setAILoading(true)
    setAIResult(null)
    try {
      const q = question || aiQuestion || undefined
      const result = await analyzeWithAI(q)
      setAIResult(result)
    } catch (err) {
      setAIResult({ status: 'error', message: err.message })
    } finally {
      setAILoading(false)
    }
  }

  const aiPresetQuestions = [
    '오늘의 시장 상황을 종합 분석해주세요.',
    '현재 포트폴리오 리스크를 분석해주세요.',
    '이번 주 주목할 매수/매도 기회를 알려주세요.',
    '매크로 환경 변화가 국내 시장에 미치는 영향은?',
  ]

  const selectHistoryItem = (item) => {
    setSelectedDate(item.briefing_date)
    setBriefing(item.content ? { ...item.content, llm_summary: item.llm_summary } : item)
  }

  if (loading) return <div className="loading"><span className="spinner" /> Loading...</div>

  const macro = briefing?.macro || {}
  const sentiment = briefing?.sentiment || {}
  const signals = briefing?.signals || {}
  const movers = briefing?.market_movers || []
  const news = briefing?.news || []
  const llmSummary = briefing?.llm_summary

  const signalKR = signals?.summary?.KR || {}
  const signalUS = signals?.summary?.US || {}

  const fgColor = (fg) => {
    if (fg == null) return 'var(--text-muted)'
    if (fg <= 25) return 'var(--red)'
    if (fg <= 45) return '#f97316'
    if (fg <= 55) return 'var(--text-secondary)'
    if (fg <= 75) return '#22c55e'
    return 'var(--green)'
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'\uD83D\uDCCA'} 시황 브리핑</h2>
          <p className="subtitle">
            {briefing?.briefing_date || '데이터 없음'} 기준 시장 현황
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button
            className="btn btn-outline"
            onClick={() => setShowAIPanel(!showAIPanel)}
            style={{ borderColor: 'var(--accent)', color: 'var(--accent)' }}
          >
            {showAIPanel ? '\u2716 \uB2EB\uAE30' : '\uD83E\uDD16 AI \uBD84\uC11D'}
          </button>
          <button
            className="btn btn-primary"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? '생성 중...' : '\uD83D\uDD04 브리핑 생성'}
          </button>
          <HelpButton section="quickstart" onNavigate={onNavigate} />
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: 'var(--red)', padding: '0.75rem 1.25rem', marginBottom: '1rem' }}>
          {'\u274C'} {error}
        </div>
      )}

      {/* AI Analysis Panel */}
      {showAIPanel && (
        <div className="card" style={{ marginBottom: '1.5rem', borderColor: 'var(--accent)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <span style={{ fontSize: '1.1rem' }}>{'\uD83E\uDD16'}</span>
            <strong style={{ color: 'var(--accent)' }}>AI {'\uC2DC\uD669'} {'\uBD84\uC11D'}</strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              VIBE DB {'\uB370\uC774\uD130'} {'\uAE30\uBC18'} LLM {'\uBD84\uC11D'}
            </span>
          </div>

          {/* Preset question buttons */}
          <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
            {aiPresetQuestions.map((q, i) => (
              <button
                key={i}
                className="btn btn-outline btn-sm"
                onClick={() => { setAIQuestion(q); handleAIAnalyze(q) }}
                disabled={aiLoading}
                style={{ fontSize: '0.75rem' }}
              >
                {q.length > 25 ? q.slice(0, 25) + '...' : q}
              </button>
            ))}
          </div>

          {/* Custom question input */}
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input
              type="text"
              placeholder={'\uC9C8\uBB38\uC744 \uC785\uB825\uD558\uC138\uC694... (ex: \uBC18\uB3C4\uCCB4 \uC139\uD130 \uC804\uB9DD\uC740?)'}
              value={aiQuestion}
              onChange={e => setAIQuestion(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !aiLoading && handleAIAnalyze()}
              style={{
                flex: 1, padding: '0.5rem 0.75rem', borderRadius: '0.5rem',
                background: 'var(--bg-primary)', border: '1px solid var(--border)',
                color: 'var(--text-primary)', fontSize: '0.85rem',
              }}
            />
            <button
              className="btn btn-primary"
              onClick={() => handleAIAnalyze()}
              disabled={aiLoading}
              style={{ whiteSpace: 'nowrap' }}
            >
              {aiLoading ? (
                <><span className="spinner" style={{ width: 14, height: 14 }} /> {'\uBD84\uC11D \uC911'}...</>
              ) : (
                '\u27A4 \uBD84\uC11D'
              )}
            </button>
          </div>

          {/* AI Result */}
          {aiResult && (
            <div style={{
              marginTop: '1rem', padding: '1rem', borderRadius: '0.5rem',
              background: 'var(--bg-primary)', border: '1px solid var(--border)',
            }}>
              {aiResult.status === 'error' ? (
                <div style={{ color: 'var(--red)' }}>
                  {'\u274C'} {aiResult.message}
                </div>
              ) : (
                <>
                  <div style={{ marginBottom: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--accent)' }}>
                      {'\u2728'} {aiResult.question}
                    </span>
                    <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                      {aiResult.metadata?.model || 'N/A'} | {aiResult.metadata?.generated_at ? new Date(aiResult.metadata.generated_at).toLocaleTimeString('ko-KR') : '-'}
                    </span>
                  </div>
                  <div style={{
                    lineHeight: 1.8, color: 'var(--text-primary)',
                    whiteSpace: 'pre-line', fontSize: '0.9rem',
                  }}>
                    {aiResult.analysis || '분석 결과가 비어 있습니다.'}
                  </div>
                  {aiResult.metadata?.context_snapshot && (
                    <div style={{
                      marginTop: '0.75rem', paddingTop: '0.5rem',
                      borderTop: '1px solid var(--border)',
                      display: 'flex', gap: '1rem', flexWrap: 'wrap',
                    }}>
                      {[
                        { label: '\uC2DC\uADF8\uB110', val: aiResult.metadata.context_snapshot?.signal_markets?.join(', ') || '-' },
                        { label: '\uC8FC\uC694\uC885\uBAA9', val: `${aiResult.metadata.context_snapshot?.top_movers_count ?? 0}\uAC1C` },
                        { label: '\uD3EC\uD2B8\uD3F4\uB9AC\uC624', val: `${aiResult.metadata.context_snapshot?.portfolio_positions ?? 0}\uC885\uBAA9` },
                      ].map(({ label, val }, i) => (
                        <span key={i} style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          {label}: <strong style={{ color: 'var(--text-secondary)' }}>{val}</strong>
                        </span>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}

      {!briefing ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
          <p style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>아직 생성된 시황 브리핑이 없습니다.</p>
          <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>
            파이프라인 실행 후 자동 생성되거나, 위의 "브리핑 생성" 버튼을 클릭하세요.
          </p>
          <button className="btn btn-primary" onClick={handleGenerate} disabled={generating}>
            {generating ? '생성 중...' : '지금 생성하기'}
          </button>
        </div>
      ) : (
        <>
          {/* LLM 해설 (있을 경우) */}
          {llmSummary && (
            <div className="card" style={{ marginBottom: '1.5rem', borderColor: 'var(--accent)', borderWidth: '2px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '1.1rem' }}>{'\uD83E\uDD16'}</span>
                <strong style={{ color: 'var(--accent)' }}>AI 시황 해설</strong>
                <span className="badge" style={{ background: 'var(--accent)', color: '#fff', fontSize: '0.65rem' }}>LLM</span>
              </div>
              <p style={{ lineHeight: 1.7, color: 'var(--text-primary)', whiteSpace: 'pre-line' }}>
                {llmSummary}
              </p>
            </div>
          )}

          {/* Macro + Sentiment Cards */}
          <div className="card-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
            {/* VIX */}
            <div className="card">
              <div className="card-label">VIX</div>
              <div className={`card-value ${(macro.vix || 0) > 25 ? 'red' : (macro.vix || 0) > 20 ? 'orange' : 'green'}`}>
                {macro.vix?.toFixed(1) || 'N/A'}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{macro.vix_label || ''}</div>
            </div>
            {/* Fear & Greed */}
            <div className="card">
              <div className="card-label">Fear & Greed</div>
              <div className="card-value" style={{ color: fgColor(sentiment.fear_greed) }}>
                {sentiment.fear_greed ?? 'N/A'}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{sentiment.fear_greed_label || ''}</div>
              {sentiment.fear_greed != null && (
                <div style={{ marginTop: '0.5rem' }}>
                  <div className="gauge-bar">
                    <div className="gauge-fill" style={{
                      width: `${sentiment.fear_greed}%`,
                      background: `linear-gradient(90deg, #ef4444, #f97316, #eab308, #22c55e)`,
                    }} />
                  </div>
                </div>
              )}
            </div>
            {/* USD/KRW */}
            <div className="card">
              <div className="card-label">USD/KRW</div>
              <div className="card-value blue">{macro.usd_krw?.toLocaleString() || 'N/A'}</div>
            </div>
            {/* DXY */}
            <div className="card">
              <div className="card-label">DXY</div>
              <div className="card-value blue">{macro.dxy?.toFixed(1) || 'N/A'}</div>
            </div>
          </div>

          {/* Row 2: Yield, WTI, Gold, Put/Call */}
          <div className="card-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
            <div className="card">
              <div className="card-label">US 10Y</div>
              <div className="card-value blue">{macro.us_10y ? `${macro.us_10y.toFixed(2)}%` : 'N/A'}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                Spread: {macro.yield_spread?.toFixed(2) || 'N/A'} ({macro.yield_label || ''})
              </div>
            </div>
            <div className="card">
              <div className="card-label">WTI 원유</div>
              <div className="card-value blue">${macro.wti?.toFixed(1) || 'N/A'}</div>
            </div>
            <div className="card">
              <div className="card-label">금 (Gold)</div>
              <div className="card-value" style={{ color: '#eab308' }}>${macro.gold?.toFixed(0) || 'N/A'}</div>
            </div>
            <div className="card">
              <div className="card-label">Put/Call Ratio</div>
              <div className={`card-value ${(sentiment.put_call_ratio || 0) > 1.0 ? 'red' : 'green'}`}>
                {sentiment.put_call_ratio?.toFixed(2) || 'N/A'}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                VIX 구조: {sentiment.vix_term_structure || 'N/A'}
              </div>
            </div>
          </div>

          {/* Signal Summary */}
          <div className="card-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
            <div className="card">
              <div className="card-label">KR 시그널 ({signals.date || '-'})</div>
              <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
                <div>
                  <span className="badge" style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}>BUY</span>
                  <span style={{ marginLeft: '0.25rem', fontWeight: 700 }}>{signalKR.BUY || 0}</span>
                </div>
                <div>
                  <span className="badge" style={{ background: 'rgba(239,68,68,0.15)', color: '#ef4444' }}>SELL</span>
                  <span style={{ marginLeft: '0.25rem', fontWeight: 700 }}>{signalKR.SELL || 0}</span>
                </div>
                <div>
                  <span className="badge" style={{ background: 'rgba(148,163,184,0.15)', color: '#94a3b8' }}>HOLD</span>
                  <span style={{ marginLeft: '0.25rem', fontWeight: 700 }}>{signalKR.HOLD || 0}</span>
                </div>
              </div>
            </div>
            <div className="card">
              <div className="card-label">US 시그널 ({signals.date || '-'})</div>
              <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
                <div>
                  <span className="badge" style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}>BUY</span>
                  <span style={{ marginLeft: '0.25rem', fontWeight: 700 }}>{signalUS.BUY || 0}</span>
                </div>
                <div>
                  <span className="badge" style={{ background: 'rgba(239,68,68,0.15)', color: '#ef4444' }}>SELL</span>
                  <span style={{ marginLeft: '0.25rem', fontWeight: 700 }}>{signalUS.SELL || 0}</span>
                </div>
                <div>
                  <span className="badge" style={{ background: 'rgba(148,163,184,0.15)', color: '#94a3b8' }}>HOLD</span>
                  <span style={{ marginLeft: '0.25rem', fontWeight: 700 }}>{signalUS.HOLD || 0}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Market Movers */}
          {movers.length > 0 && (
            <div className="table-container">
              <div className="table-header">
                <h3>{'\uD83D\uDD25'} 주요 종목 시그널</h3>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>종목</th>
                    <th>마켓</th>
                    <th>시그널</th>
                    <th>스코어</th>
                    <th>RSI</th>
                    <th>해설</th>
                  </tr>
                </thead>
                <tbody>
                  {movers.map((m, i) => (
                    <tr key={`${m.symbol}-${i}`}>
                      <td>
                        <strong>{m.name}</strong>
                        <br />
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{m.symbol}</span>
                      </td>
                      <td>{m.market}</td>
                      <td>
                        <span className="badge" style={{
                          background: m.signal === 'BUY' ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
                          color: m.signal === 'BUY' ? '#22c55e' : '#ef4444',
                        }}>
                          {m.signal}
                        </span>
                      </td>
                      <td style={{ fontWeight: 600, color: m.score > 0 ? 'var(--green)' : 'var(--red)' }}>
                        {m.score > 0 ? '+' : ''}{m.score}
                      </td>
                      <td>{m.rsi?.toFixed(1) || '-'}</td>
                      <td style={{ maxWidth: 300, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        {m.rationale || '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* News Headlines */}
          {news.length > 0 && (
            <div className="table-container">
              <div className="table-header">
                <h3>{'\uD83D\uDCF0'} 최근 뉴스</h3>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>날짜</th>
                    <th>종목</th>
                    <th>마켓</th>
                    <th>헤드라인</th>
                    <th>톤</th>
                  </tr>
                </thead>
                <tbody>
                  {news.map((n, i) => (
                    <tr key={i}>
                      <td style={{ whiteSpace: 'nowrap', fontSize: '0.8rem' }}>{n.date}</td>
                      <td>{n.symbol}</td>
                      <td>{n.market}</td>
                      <td style={{ fontSize: '0.8rem' }}>{n.title}</td>
                      <td>
                        {(n.score ?? 0) > 0 ? (
                          <span style={{ color: 'var(--green)', fontWeight: 600 }}>+{(n.score ?? 0).toFixed(1)}</span>
                        ) : (n.score ?? 0) < 0 ? (
                          <span style={{ color: 'var(--red)', fontWeight: 600 }}>{(n.score ?? 0).toFixed(1)}</span>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>0</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Briefing History */}
          {history.length > 1 && (
            <div className="card" style={{ marginTop: '1.5rem' }}>
              <h3 style={{ marginBottom: '0.75rem' }}>{'\uD83D\uDCC5'} 이전 브리핑</h3>
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {history.map((h) => (
                  <button
                    key={h.briefing_date}
                    className={`guide-tab ${h.briefing_date === (selectedDate || briefing?.briefing_date) ? 'active' : ''}`}
                    onClick={() => selectHistoryItem(h)}
                    style={{ padding: '0.375rem 0.75rem', fontSize: '0.8rem' }}
                  >
                    {h.briefing_date}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
