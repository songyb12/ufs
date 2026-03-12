import { useState, useEffect, useCallback } from 'react'
import { getMarketBriefings, getLatestBriefing, generateBriefing, analyzeWithAI, getSentimentHistory } from '../api'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from 'recharts'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import { useToast } from '../components/Toast'

export default function MarketBrief({ onNavigate, refreshKey }) {
  const toast = useToast()
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
  const [aiHistory, setAIHistory] = useState([])

  // Sentiment history
  const [sentimentData, setSentimentData] = useState([])

  const loadData = useCallback(() => {
    setLoading(true)
    Promise.all([
      getLatestBriefing().catch(() => null),  // 404 graceful fallback
      getMarketBriefings(10),
      getSentimentHistory(30).catch(() => ({ sentiment: [] })),
    ])
      .then(([latest, hist, sentHist]) => {
        setBriefing(latest || null)
        setHistory(hist?.briefings || [])
        // Sentiment history for chart (reverse for chronological order)
        const sentArr = (sentHist?.sentiment || []).slice().reverse()
        setSentimentData(sentArr)
        setError(null)
      })
      .catch(err => { setError(err.message); toast.error('브리핑 로드 실패: ' + err.message) })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData, refreshKey])

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
      toast.error('브리핑 생성 실패: ' + err.message)
    } finally {
      setGenerating(false)
    }
  }

  const handleAIAnalyze = async (question = null) => {
    setAILoading(true)
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 90000) // 90s timeout
    try {
      const q = question || aiQuestion || undefined
      const result = await analyzeWithAI(q, { signal: controller.signal })
      // Multi-turn: append to history
      setAIHistory(prev => [...prev, result])
      setAIResult(result)
      setAIQuestion('')
    } catch (err) {
      const msg = err.name === 'AbortError' ? 'AI 분석 시간 초과 (90초). 다시 시도해주세요.' : err.message
      const errResult = { status: 'error', message: msg, question: question || aiQuestion || '(질문 없음)' }
      setAIHistory(prev => [...prev, errResult])
      setAIResult(errResult)
    } finally {
      clearTimeout(timeout)
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

  if (loading) return <div className="loading"><span className="spinner" /> 로딩 중...</div>

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
          <h2>{'📊'} 시황 브리핑</h2>
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
            {showAIPanel ? '✖ 닫기' : '🤖 AI 분석'}
          </button>
          <button
            className="btn btn-primary"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? '생성 중...' : '🔄 브리핑 생성'}
          </button>
          <button className="btn btn-outline" onClick={loadData}>{'↻'} Refresh</button>
          <HelpButton section="quickstart" onNavigate={onNavigate} />
        </div>
      </div>

      <PageGuide
        pageId="market-brief"
        title="시황 브리핑 읽는 법"
        steps={[
          '브리핑 생성 → 오늘의 매크로/심리 요약 자동 생성',
          'AI 분석 → 자유 질문 또는 프리셋으로 심층 분석',
          '매크로 지표 → VIX, F&G, 환율, DXY 한눈에',
          '시그널 요약 → 오늘 BUY/SELL 개수 확인',
        ]}
        color="#3b82f6"
      />

      {error && (
        <div className="card" style={{ borderColor: 'var(--red)', padding: '0.75rem 1.25rem', marginBottom: '1rem' }}>
          {'❌'} {error}
        </div>
      )}

      {/* AI Analysis Panel */}
      {showAIPanel && (
        <div className="card" style={{ marginBottom: '1.5rem', borderColor: 'var(--accent)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
            <span style={{ fontSize: '1.1rem' }}>{'🤖'}</span>
            <strong style={{ color: 'var(--accent)' }}>AI {'시황'} {'분석'}</strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              VIBE DB {'데이터'} {'기반'} LLM {'분석'}
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
              placeholder={'질문을 입력하세요... (ex: 반도체 섹터 전망은?)'}
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
                <><span className="spinner" style={{ width: 14, height: 14 }} /> {'분석 중'}...</>
              ) : (
                '➤ 분석'
              )}
            </button>
          </div>

          {/* AI Conversation History */}
          {aiHistory.length > 0 && (
            <div style={{
              marginTop: '1rem', maxHeight: '400px', overflowY: 'auto',
              display: 'flex', flexDirection: 'column', gap: '0.75rem',
            }}>
              {aiHistory.map((item, idx) => (
                <div key={idx} style={{
                  padding: '1rem', borderRadius: '0.5rem',
                  background: 'var(--bg-primary)', border: '1px solid var(--border)',
                }}>
                  {item.status === 'error' ? (
                    <div style={{ color: 'var(--red)' }}>
                      {'❌'} {item.message}
                    </div>
                  ) : (
                    <>
                      <div style={{ marginBottom: '0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--accent)' }}>
                          {'✨'} {item.question}
                        </span>
                        <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                          {item.metadata?.model || 'N/A'} | {item.metadata?.generated_at ? new Date(item.metadata.generated_at).toLocaleTimeString('ko-KR') : '-'}
                        </span>
                      </div>
                      <div style={{
                        lineHeight: 1.8, color: 'var(--text-primary)',
                        whiteSpace: 'pre-line', fontSize: '0.9rem',
                      }}>
                        {item.analysis || '분석 결과가 비어 있습니다.'}
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
          {aiHistory.length > 1 && (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => { setAIHistory([]); setAIResult(null) }}
              style={{ marginTop: '0.5rem', fontSize: '0.7rem' }}
            >
              대화 초기화
            </button>
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
                <span style={{ fontSize: '1.1rem' }}>{'🤖'}</span>
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

          {/* Row 2: Yield, Commodities */}
          <div className="card-grid" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
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
              <div className="card-label">구리 (Copper)</div>
              <div className="card-value" style={{ color: '#d97706' }}>${macro.copper?.toFixed(2) || 'N/A'}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Dr. Copper</div>
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

          {/* Sentiment Trend Chart */}
          {sentimentData.length >= 2 && (
            <div className="table-container" style={{ marginBottom: '1.5rem' }}>
              <div className="table-header">
                <h3>📈 센티먼트 추이 (최근 {sentimentData.length}일)</h3>
              </div>
              <div style={{ padding: '0.5rem 0' }}>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={sentimentData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis
                      dataKey="indicator_date"
                      tick={{ fill: '#94a3b8', fontSize: 10 }}
                      tickFormatter={v => v?.slice(5)}
                    />
                    <YAxis
                      yAxisId="fg"
                      domain={[0, 100]}
                      tick={{ fill: '#94a3b8', fontSize: 10 }}
                      label={{ value: 'F&G', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 10 }}
                    />
                    <YAxis
                      yAxisId="pc"
                      orientation="right"
                      domain={[0.5, 1.5]}
                      tick={{ fill: '#475569', fontSize: 10 }}
                      label={{ value: 'P/C', angle: 90, position: 'insideRight', fill: '#475569', fontSize: 10 }}
                    />
                    <Tooltip
                      contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.8rem' }}
                      formatter={(v, name) => {
                        if (name === 'fear_greed_index') return [v, 'Fear & Greed']
                        if (name === 'put_call_ratio') return [v?.toFixed(3), 'Put/Call']
                        return [v, name]
                      }}
                      labelFormatter={(l) => l}
                    />
                    <Legend
                      formatter={(val) => val === 'fear_greed_index' ? 'Fear & Greed' : 'Put/Call Ratio'}
                      wrapperStyle={{ fontSize: '0.75rem' }}
                    />
                    <Line
                      yAxisId="fg"
                      type="monotone"
                      dataKey="fear_greed_index"
                      stroke="#eab308"
                      strokeWidth={2}
                      dot={{ r: 3, fill: '#eab308' }}
                    />
                    <Line
                      yAxisId="pc"
                      type="monotone"
                      dataKey="put_call_ratio"
                      stroke="#ef4444"
                      strokeWidth={1.5}
                      strokeDasharray="5 5"
                      dot={{ r: 2, fill: '#ef4444' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
                {/* Reference lines description */}
                <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '0.25rem' }}>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>F&G: 0-25 극도공포 | 25-45 공포 | 45-55 중립 | 55-75 탐욕 | 75+ 극도탐욕</span>
                </div>
              </div>
            </div>
          )}

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
                <h3>{'🔥'} 주요 종목 시그널</h3>
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
                <h3>{'📰'} 최근 뉴스</h3>
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
              <h3 style={{ marginBottom: '0.75rem' }}>{'📅'} 이전 브리핑</h3>
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
