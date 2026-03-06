import { useState, useEffect } from 'react'
import {
  getHealth, getPipelineRuns, triggerPipeline,
  getWatchlist, addWatchlistItem, removeWatchlistItem,
  getAlertConfig, updateAlertConfig, getAlertHistory,
  getMonthlyReports, generateMonthlyReport,
  getDataStatus, getLLMSettings, updateLLMSettings,
  getStoredApiKey, setApiKey,
} from '../api'

import HelpButton from '../components/HelpButton'

export default function System({ onNavigate }) {
  const [health, setHealth] = useState(null)
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState(false)
  const [triggerResult, setTriggerResult] = useState(null)

  // Watchlist state
  const [watchlist, setWatchlist] = useState([])
  const [wlFilter, setWlFilter] = useState('ALL')
  const [showWlAdd, setShowWlAdd] = useState(false)
  const [wlForm, setWlForm] = useState({ symbol: '', name: '', market: 'KR', asset_type: 'stock' })
  const [wlSubmitting, setWlSubmitting] = useState(false)
  const [wlMessage, setWlMessage] = useState(null)

  // Alert state
  const [alertConfig, setAlertConfig] = useState([])
  const [alertHistory, setAlertHistory] = useState([])
  const [alertEditing, setAlertEditing] = useState({})
  const [alertSaving, setAlertSaving] = useState(false)

  // Monthly report state
  const [monthlyReports, setMonthlyReports] = useState([])
  const [generatingReport, setGeneratingReport] = useState(false)

  // Data status state
  const [dataStatus, setDataStatus] = useState(null)

  // LLM settings state
  const [llmSettings, setLlmSettings] = useState(null)
  const [llmToggling, setLlmToggling] = useState(null)

  const [error, setError] = useState(null)

  const refresh = () => {
    setLoading(true)
    Promise.all([
      getHealth(), getPipelineRuns(), getWatchlist(),
      getAlertConfig().catch(() => ({ config: [] })),
      getAlertHistory(20).catch(() => ({ history: [] })),
      getMonthlyReports(6).catch(() => ({ reports: [] })),
      getDataStatus().catch(() => ({ tables: {} })),
      getLLMSettings().catch(() => null),
    ])
      .then(([h, r, wl, ac, ah, mr, ds, llm]) => {
        setHealth(h); setRuns(r); setWatchlist(wl || [])
        setAlertConfig(ac.config || [])
        setAlertHistory(ah.history || [])
        setMonthlyReports(mr.reports || [])
        setDataStatus(ds?.tables || null)
        setLlmSettings(llm)
        setError(null)
      })
      .catch(err => { console.error(err); setError(err.message) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  const showWlMsg = (text, type = 'success') => {
    setWlMessage({ text, type })
    setTimeout(() => setWlMessage(null), 3000)
  }

  const handleTrigger = async (market) => {
    setTriggering(true)
    setTriggerResult(null)
    try {
      const result = await triggerPipeline(market)
      setTriggerResult(result)
      setTimeout(refresh, 3000)
    } catch (e) {
      setTriggerResult({ status: 'error', message: e.message })
    } finally {
      setTriggering(false)
    }
  }

  const handleWlAdd = async (e) => {
    e.preventDefault()
    if (!wlForm.symbol || !wlForm.name) return
    setWlSubmitting(true)
    try {
      await addWatchlistItem(wlForm)
      showWlMsg(`${wlForm.symbol} (${wlForm.name}) 추가 완료`)
      setWlForm({ symbol: '', name: '', market: 'KR', asset_type: 'stock' })
      setShowWlAdd(false)
      const wl = await getWatchlist()
      setWatchlist(wl || [])
    } catch (err) {
      showWlMsg(`추가 실패: ${err.message}`, 'error')
    } finally {
      setWlSubmitting(false)
    }
  }

  const handleWlRemove = async (symbol, market) => {
    if (!confirm(`${symbol} (${market})을 Watchlist에서 제거하시겠습니까?`)) return
    try {
      await removeWatchlistItem(symbol, market)
      showWlMsg(`${symbol} 제거 완료`)
      const wl = await getWatchlist()
      setWatchlist(wl || [])
    } catch (err) {
      showWlMsg(`제거 실패: ${err.message}`, 'error')
    }
  }

  // Alert handlers
  const handleAlertSave = async (key) => {
    const newValue = alertEditing[key]
    if (newValue == null) return
    setAlertSaving(true)
    try {
      await updateAlertConfig([{ key, value: String(newValue) }])
      setAlertEditing(prev => { const n = { ...prev }; delete n[key]; return n })
      const ac = await getAlertConfig()
      setAlertConfig(ac.config || [])
    } catch (err) {
      console.error('Alert save failed:', err)
    } finally {
      setAlertSaving(false)
    }
  }

  // LLM toggle handler
  const handleLLMToggle = async (key) => {
    if (!llmSettings) return
    const currentValue = llmSettings.features[key]
    setLlmToggling(key)
    try {
      const result = await updateLLMSettings({ [key]: !currentValue })
      setLlmSettings(prev => ({
        ...prev,
        features: result.features,
      }))
    } catch (err) {
      console.error('LLM toggle failed:', err)
    } finally {
      setLlmToggling(null)
    }
  }

  // Monthly report handler
  const handleGenerateReport = async () => {
    setGeneratingReport(true)
    try {
      await generateMonthlyReport()
      const mr = await getMonthlyReports(6)
      setMonthlyReports(mr.reports || [])
    } catch (err) {
      console.error('Report generation failed:', err)
    } finally {
      setGeneratingReport(false)
    }
  }

  if (loading) return <div className="loading"><span className="spinner" /> Loading...</div>
  if (error) return <div className="loading" style={{ color: 'var(--red)' }}>Error: {error}</div>

  const filteredWl = wlFilter === 'ALL' ? watchlist : watchlist.filter(w => w.market === wlFilter)

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'\u2699'} 시스템</h2>
          <p className="subtitle">서비스 상태, 스케줄러, 파이프라인 관리</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-primary" onClick={() => handleTrigger('KR')} disabled={triggering}>
            {triggering ? '실행 중...' : '\u25B6 KR 실행'}
          </button>
          <button className="btn btn-primary" onClick={() => handleTrigger('US')} disabled={triggering}>
            {triggering ? '실행 중...' : '\u25B6 US 실행'}
          </button>
          <button className="btn btn-outline" onClick={refresh}>
            {'\u21BB'} 새로고침
          </button>
          <HelpButton section="system" onNavigate={onNavigate} />
        </div>
      </div>

      {triggerResult && (
        <div className="card" style={{ marginBottom: '1rem', borderColor: triggerResult.status === 'error' ? 'var(--red)' : 'var(--green)' }}>
          <strong>{triggerResult.status}</strong>: {triggerResult.message || JSON.stringify(triggerResult)}
        </div>
      )}

      {/* Health Status */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <div className="card">
          <div className="card-label">상태</div>
          <div className={`card-value ${health?.status === 'healthy' ? 'green' : 'red'}`}>
            {health?.status || 'unknown'}
          </div>
          <div className="card-sub">v{health?.version}</div>
        </div>
        <div className="card">
          <div className="card-label">데이터베이스</div>
          <div className={`card-value ${health?.database?.connected ? 'green' : 'red'}`}>
            {health?.database?.connected ? 'Connected' : 'Down'}
          </div>
          <div className="card-sub">{health?.database?.tables} tables</div>
        </div>
        <div className="card">
          <div className="card-label">가격 데이터</div>
          <div className="card-value blue">{(health?.database?.prices ?? 0).toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="card-label">시그널</div>
          <div className="card-value blue">{(health?.database?.signals ?? 0).toLocaleString()}</div>
        </div>
      </div>

      {/* Scheduler Jobs */}
      <div className="table-container">
        <div className="table-header">
          <h3>{'\u23F0'} 스케줄러</h3>
          <span className={`badge ${health?.scheduler?.running ? 'badge-completed' : 'badge-failed'}`}>
            {health?.scheduler?.running ? 'Running' : 'Stopped'}
          </span>
        </div>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>이름</th>
              <th>다음 실행</th>
            </tr>
          </thead>
          <tbody>
            {(health?.scheduler?.jobs || []).map((job) => (
              <tr key={job.id}>
                <td><code style={{ fontSize: '0.75rem' }}>{job.id}</code></td>
                <td>{job.name}</td>
                <td>
                  {job.next_run
                    ? new Date(job.next_run).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })
                    : '-'
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pipeline Runs */}
      <div className="table-container">
        <div className="table-header">
          <h3>{'\uD83D\uDD04'} 파이프라인 실행 이력</h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>Run ID</th>
              <th>마켓</th>
              <th>상태</th>
              <th>시작</th>
              <th>완료</th>
              <th>스테이지</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => {
              let stages = 0
              try {
                const parsed = typeof r.stages_completed === 'string' ? JSON.parse(r.stages_completed) : r.stages_completed
                stages = Array.isArray(parsed) ? parsed.length : 0
              } catch {}
              return (
                <tr key={r.run_id}>
                  <td><code style={{ fontSize: '0.7rem' }}>{r.run_id?.slice(0, 8)}</code></td>
                  <td>{r.market}</td>
                  <td>
                    <span className={`badge badge-${r.status}`}>
                      {r.status}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.75rem' }}>
                    {r.started_at ? new Date(r.started_at).toLocaleString('ko-KR') : '-'}
                  </td>
                  <td style={{ fontSize: '0.75rem' }}>
                    {r.completed_at ? new Date(r.completed_at).toLocaleString('ko-KR') : '-'}
                  </td>
                  <td>{stages}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pipeline Freshness */}
      <div className="grid-2">
        <div className="card">
          <div className="card-label">KR 파이프라인</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
            <span className={`status-dot ${health?.pipelines?.KR?.status === 'completed' ? 'green' : 'red'}`} />
            <span>{health?.pipelines?.KR?.status}</span>
          </div>
          <div className="card-sub">
            최근: {health?.pipelines?.KR?.last_run ? new Date(health.pipelines.KR.last_run).toLocaleString('ko-KR') : 'never'}
          </div>
          <div className="card-sub">
            경과: {health?.pipelines?.KR?.age_hours != null ? `${health.pipelines.KR.age_hours}시간` : '-'}
          </div>
        </div>
        <div className="card">
          <div className="card-label">US 파이프라인</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
            <span className={`status-dot ${health?.pipelines?.US?.status === 'completed' ? 'green' : 'red'}`} />
            <span>{health?.pipelines?.US?.status}</span>
          </div>
          <div className="card-sub">
            최근: {health?.pipelines?.US?.last_run ? new Date(health.pipelines.US.last_run).toLocaleString('ko-KR') : 'never'}
          </div>
          <div className="card-sub">
            경과: {health?.pipelines?.US?.age_hours != null ? `${health.pipelines.US.age_hours}시간` : '-'}
          </div>
        </div>
      </div>

      {/* LLM Settings */}
      {llmSettings && (
        <div className="table-container" style={{ marginTop: '1.5rem' }}>
          <div className="table-header">
            <h3>{'\uD83E\uDDE0'} LLM \uC124\uC815</h3>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Provider: <strong style={{ color: 'var(--text-primary)' }}>{llmSettings.config?.LLM_PROVIDER}</strong>
              </span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Model: <strong style={{ color: 'var(--text-primary)' }}>{llmSettings.config?.LLM_MODEL}</strong>
              </span>
              <span className={`badge ${llmSettings.config?.LLM_API_KEY_SET ? 'badge-completed' : 'badge-failed'}`}
                style={{ fontSize: '0.65rem' }}>
                API Key {llmSettings.config?.LLM_API_KEY_SET ? '\u2713 \uC124\uC815\uB428' : '\u2717 \uBBF8\uC124\uC815'}
              </span>
            </div>
          </div>

          <div style={{ padding: '1rem 1.25rem' }}>
            {/* Toggle cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
              {[
                {
                  key: 'LLM_RED_TEAM_ENABLED',
                  label: 'Red-Team \uAC80\uC99D',
                  desc: 'Stage 7: BUY \uC2DC\uADF8\uB110 LLM \uC5ED\uBC1C\uC0C1 \uAC80\uC99D',
                  icon: '\uD83D\uDEE1',
                  stage: 'S7',
                  costHint: '~\u20A9150/\uC2E4\uD589',
                },
                {
                  key: 'LLM_EXPLANATION_ENABLED',
                  label: '\uC2DC\uADF8\uB110 \uD574\uC124',
                  desc: 'Stage 8: \uD55C\uAD6D\uC5B4 \uC885\ubaa9\ubcc4 \uBD84\uC11D + \uC2DC\uD669 \uBE0C\uB9AC\uD551',
                  icon: '\uD83D\uDCDD',
                  stage: 'S8+\uBE0C\uB9AC\uD551',
                  costHint: '~\u20A9300/\uC2E4\uD589',
                },
                {
                  key: 'LLM_SCENARIO_ENABLED',
                  label: '\uD3EC\uD2B8\uD3F4\uB9AC\uC624 \uC2DC\uB098\uB9AC\uC624',
                  desc: 'Stage 9: \uBCF4\uC720/\uC9C4\uC785 \uC885\uBAA9 \uC2DC\uB098\uB9AC\uC624 \uBD84\uC11D',
                  icon: '\uD83C\uDFAF',
                  stage: 'S9',
                  costHint: '~\u20A9200/\uC2E4\uD589',
                },
              ].map(({ key, label, desc, icon, stage, costHint }) => {
                const enabled = llmSettings.features[key]
                const isToggling = llmToggling === key
                const apiKeySet = llmSettings.config?.LLM_API_KEY_SET
                return (
                  <div key={key} style={{
                    background: 'var(--bg-primary)',
                    border: `1px solid ${enabled ? 'var(--accent)' : 'var(--border)'}`,
                    borderRadius: '0.75rem',
                    padding: '1rem',
                    transition: 'border-color 0.2s',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <span style={{ fontSize: '1.1rem' }}>{icon} {label}</span>
                      <button
                        onClick={() => handleLLMToggle(key)}
                        disabled={isToggling || !apiKeySet}
                        title={!apiKeySet ? 'API Key\uAC00 \uC124\uC815\uB418\uC9C0 \uC54A\uC558\uC2B5\uB2C8\uB2E4 (.env\uC5D0\uC11C LLM_API_KEY \uC124\uC815 \uD544\uC694)' : ''}
                        style={{
                          width: '48px', height: '26px',
                          borderRadius: '13px',
                          border: 'none',
                          background: enabled ? 'var(--accent)' : 'rgba(148,163,184,0.3)',
                          cursor: !apiKeySet ? 'not-allowed' : 'pointer',
                          position: 'relative',
                          transition: 'background 0.2s',
                          opacity: !apiKeySet ? 0.4 : 1,
                        }}
                      >
                        <span style={{
                          position: 'absolute',
                          top: '3px',
                          left: enabled ? '24px' : '3px',
                          width: '20px', height: '20px',
                          borderRadius: '50%',
                          background: '#fff',
                          transition: 'left 0.2s',
                          boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
                        }} />
                      </button>
                    </div>
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', margin: '0 0 0.5rem 0', lineHeight: 1.4 }}>
                      {desc}
                    </p>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className={`badge ${enabled ? 'badge-buy' : ''}`}
                        style={!enabled ? { background: 'rgba(148,163,184,0.15)', color: '#94a3b8' } : {}}>
                        {stage}
                      </span>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{costHint}</span>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Rule-based status */}
            <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'var(--bg-primary)', borderRadius: '0.5rem', border: '1px solid var(--border)' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {'\u2139\uFE0F'} \uADDC\uCE59 \uAE30\uBC18 \uBD84\uC11D\uC740 LLM \uC124\uC815\uACFC \uBB34\uAD00\uD558\uAC8C \uD56D\uC0C1 \uD65C\uC131\uD654 \uC0C1\uD0DC\uC785\uB2C8\uB2E4.
                LLM\uC740 \uADDC\uCE59 \uAE30\uBC18 \uACB0\uACFC\uC5D0 \uCD94\uAC00 \uBCF4\uAC15\uD558\uB294 \uC5ED\uD560\uC744 \uD569\uB2C8\uB2E4.
                {!llmSettings.config?.LLM_API_KEY_SET && (
                  <span style={{ color: 'var(--yellow)', display: 'block', marginTop: '0.25rem' }}>
                    {'\u26A0'} LLM \uAE30\uB2A5\uC744 \uC0AC\uC6A9\uD558\uB824\uBA74 .env \uD30C\uC77C\uC5D0 LLM_API_KEY\uB97C \uC124\uC815\uD558\uC138\uC694.
                  </span>
                )}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Alert Settings */}
      <div className="table-container" style={{ marginTop: '1.5rem' }}>
        <div className="table-header">
          <h3>{'\uD83D\uDD14'} 알림 설정</h3>
          <span className="card-sub">{alertConfig.length} settings</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>설정</th>
              <th>설명</th>
              <th>현재값</th>
              <th>관리</th>
            </tr>
          </thead>
          <tbody>
            {alertConfig.length === 0 ? (
              <tr>
                <td colSpan={4} style={{ textAlign: 'center', padding: '1rem', color: 'var(--text-muted)' }}>
                  알림 설정이 없습니다. 파이프라인 실행 후 자동 생성됩니다.
                </td>
              </tr>
            ) : alertConfig.map((c) => (
              <tr key={c.key}>
                <td><code style={{ fontSize: '0.8rem' }}>{c.key}</code></td>
                <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{c.description || '-'}</td>
                <td>
                  <input
                    type="text"
                    value={alertEditing[c.key] ?? c.value}
                    onChange={e => setAlertEditing(prev => ({ ...prev, [c.key]: e.target.value }))}
                    style={{
                      width: '80px', padding: '0.25rem', borderRadius: '0.25rem',
                      background: 'var(--bg-primary)', border: `1px solid ${alertEditing[c.key] != null ? 'var(--accent)' : 'var(--border)'}`,
                      color: 'var(--text-primary)', fontSize: '0.8rem', textAlign: 'center',
                    }}
                  />
                </td>
                <td>
                  {alertEditing[c.key] != null && (
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => handleAlertSave(c.key)}
                      disabled={alertSaving}
                    >
                      {alertSaving ? '...' : '저장'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Alert History */}
      {alertHistory.length > 0 && (
        <div className="table-container">
          <div className="table-header">
            <h3>{'\u26A0'} 최근 알림 이력</h3>
            <span className="card-sub">{alertHistory.length} alerts</span>
          </div>
          <table>
            <thead>
              <tr>
                <th>시간</th>
                <th>유형</th>
                <th>내용</th>
                <th>발송</th>
              </tr>
            </thead>
            <tbody>
              {alertHistory.map((a) => (
                <tr key={a.id}>
                  <td style={{ whiteSpace: 'nowrap', fontSize: '0.75rem' }}>
                    {a.fired_at ? new Date(a.fired_at).toLocaleString('ko-KR') : '-'}
                  </td>
                  <td>
                    <span className="badge badge-sell">{a.alert_type}</span>
                  </td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', maxWidth: 300 }}>
                    {a.condition?.slice(0, 100) || '-'}
                  </td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{a.sent_to}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Data Status */}
      {dataStatus && (
        <div className="table-container" style={{ marginTop: '1.5rem' }}>
          <div className="table-header">
            <h3>{'\uD83D\uDDC4'} 수집 데이터 현황</h3>
          </div>
          <table>
            <thead>
              <tr>
                <th>데이터</th>
                <th>건수</th>
                <th>종목수</th>
                <th>최초</th>
                <th>최신</th>
                <th>상태</th>
              </tr>
            </thead>
            <tbody>
              {[
                { key: 'price_history', label: '가격 데이터', hasSymbols: true },
                { key: 'signals', label: '시그널', hasSymbols: true },
                { key: 'technical_indicators', label: '기술 지표', hasSymbols: false },
                { key: 'macro_indicators', label: '매크로 지표', hasSymbols: false },
                { key: 'sentiment_data', label: '센티먼트', hasSymbols: false },
                { key: 'news_data', label: '뉴스 데이터', hasSymbols: true },
                { key: 'fund_flow_kr', label: 'KR 수급', hasSymbols: true },
                { key: 'market_briefings', label: '시황 브리핑', hasSymbols: false },
                { key: 'llm_reviews', label: 'LLM 리뷰', hasSymbols: false },
              ].map(({ key, label, hasSymbols }) => {
                const d = dataStatus[key] || {}
                const cnt = d.cnt || 0
                const latest = d.latest
                const isStale = latest && (() => {
                  const diff = (Date.now() - new Date(latest).getTime()) / (1000*60*60*24)
                  return diff > 3
                })()
                return (
                  <tr key={key}>
                    <td style={{ fontWeight: 600 }}>{label}</td>
                    <td>{cnt.toLocaleString()}</td>
                    <td>{hasSymbols ? (d.symbols || '-') : '-'}</td>
                    <td style={{ fontSize: '0.8rem' }}>{d.earliest || '-'}</td>
                    <td style={{ fontSize: '0.8rem' }}>{latest || '-'}</td>
                    <td>
                      {cnt === 0 ? (
                        <span className="badge" style={{ background: 'rgba(148,163,184,0.15)', color: '#94a3b8' }}>없음</span>
                      ) : isStale ? (
                        <span className="badge" style={{ background: 'rgba(245,158,11,0.15)', color: '#f59e0b' }}>갱신 필요</span>
                      ) : (
                        <span className="badge" style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}>정상</span>
                      )}
                    </td>
                  </tr>
                )
              })}
              <tr>
                <td style={{ fontWeight: 600 }}>Watchlist</td>
                <td>{(dataStatus.watchlist_active?.cnt || 0).toLocaleString()}</td>
                <td colSpan={3}>활성 종목 수</td>
                <td>
                  <span className="badge" style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}>정상</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* Monthly Reports */}
      <div className="table-container" style={{ marginTop: '1.5rem' }}>
        <div className="table-header">
          <h3>{'\uD83D\uDCC5'} 월간 리포트</h3>
          <button
            className="btn btn-primary btn-sm"
            onClick={handleGenerateReport}
            disabled={generatingReport}
          >
            {generatingReport ? '생성 중...' : '+ 리포트 생성'}
          </button>
        </div>
        <table>
          <thead>
            <tr>
              <th>월</th>
              <th>총 시그널</th>
              <th>BUY / SELL</th>
              <th>Hit Rate T+5</th>
              <th>Hit Rate T+20</th>
              <th>파이프라인</th>
              <th>생성일</th>
            </tr>
          </thead>
          <tbody>
            {monthlyReports.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)' }}>
                  월간 리포트가 없습니다. "리포트 생성" 버튼으로 생성하세요.
                </td>
              </tr>
            ) : monthlyReports.map((r) => {
              const c = r.content || {}
              const sig = c.signals || {}
              const pipelines = c.pipeline_runs || {}
              const totalPipeline = Object.values(pipelines).reduce((s, v) => s + v, 0)
              return (
                <tr key={`${r.report_month}-${r.market}`}>
                  <td style={{ fontWeight: 600 }}>{r.report_month}</td>
                  <td>{c.total_signals ?? '-'}</td>
                  <td>
                    <span style={{ color: 'var(--green)' }}>{sig.BUY ?? 0}</span>
                    {' / '}
                    <span style={{ color: 'var(--red)' }}>{sig.SELL ?? 0}</span>
                  </td>
                  <td style={{ color: (c.hit_rate_t5 ?? 0) >= 50 ? 'var(--green)' : 'var(--yellow)' }}>
                    {c.hit_rate_t5 != null ? `${c.hit_rate_t5}%` : '-'}
                  </td>
                  <td style={{ color: (c.hit_rate_t20 ?? 0) >= 50 ? 'var(--green)' : 'var(--yellow)' }}>
                    {c.hit_rate_t20 != null ? `${c.hit_rate_t20}%` : '-'}
                  </td>
                  <td>{totalPipeline} runs</td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {r.created_at ? new Date(r.created_at).toLocaleDateString('ko-KR') : '-'}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Auth Status */}
      <div className="card" style={{ marginTop: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div className="card-label">{'\uD83D\uDD10'} {'\uC778\uC99D'} {'\uC0C1\uD0DC'}</div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginTop: '0.5rem' }}>
              <span className={`badge ${getStoredApiKey() ? 'badge-completed' : 'badge-hold'}`}>
                {getStoredApiKey() ? '\uD83D\uDD12 API Key \uC778\uC99D\uB428' : '\uD83D\uDD13 \uC778\uC99D \uC5C6\uC74C'}
              </span>
              {getStoredApiKey() && (
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Key: {getStoredApiKey().slice(0, 4)}{'****'}
                </span>
              )}
            </div>
          </div>
          {getStoredApiKey() && (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => {
                if (confirm('\uB85C\uADF8\uC544\uC6C3 \uD558\uC2DC\uACA0\uC2B5\uB2C8\uAE4C?')) {
                  setApiKey(null)
                  window.location.reload()
                }
              }}
              style={{ color: 'var(--red)', borderColor: 'var(--red)' }}
            >
              {'\uD83D\uDEAA'} {'\uB85C\uADF8\uC544\uC6C3'}
            </button>
          )}
        </div>
      </div>

      {/* Watchlist Management */}
      <div className="table-container" style={{ marginTop: '1.5rem' }}>
        <div className="table-header">
          <h3>{'\uD83D\uDCCB'} Watchlist 관리</h3>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <select
              value={wlFilter}
              onChange={e => setWlFilter(e.target.value)}
              style={{
                padding: '0.3rem 0.5rem', borderRadius: '0.375rem',
                background: 'var(--bg-primary)', border: '1px solid var(--border)',
                color: 'var(--text-primary)', fontSize: '0.8rem',
              }}
            >
              <option value="ALL">전체 ({watchlist.length})</option>
              <option value="KR">KR ({watchlist.filter(w => w.market === 'KR').length})</option>
              <option value="US">US ({watchlist.filter(w => w.market === 'US').length})</option>
            </select>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => setShowWlAdd(!showWlAdd)}
            >
              {showWlAdd ? '취소' : '+ 종목 추가'}
            </button>
          </div>
        </div>

        {/* Watchlist 알림 */}
        {wlMessage && (
          <div style={{
            padding: '0.5rem 1.25rem',
            borderBottom: '1px solid var(--border)',
            color: wlMessage.type === 'error' ? 'var(--red)' : 'var(--green)',
            fontSize: '0.8rem',
          }}>
            {wlMessage.type === 'error' ? '\u274C' : '\u2705'} {wlMessage.text}
          </div>
        )}

        {/* 종목 추가 폼 */}
        {showWlAdd && (
          <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border)' }}>
            <form onSubmit={handleWlAdd} style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <div>
                <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.15rem' }}>종목코드 *</label>
                <input
                  type="text"
                  placeholder="005930"
                  value={wlForm.symbol}
                  onChange={e => setWlForm(prev => ({ ...prev, symbol: e.target.value }))}
                  style={{
                    width: '100px', padding: '0.35rem', borderRadius: '0.25rem',
                    background: 'var(--bg-primary)', border: '1px solid var(--border)',
                    color: 'var(--text-primary)', fontSize: '0.8rem',
                  }}
                  required
                />
              </div>
              <div>
                <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.15rem' }}>종목명 *</label>
                <input
                  type="text"
                  placeholder="SK하이닉스"
                  value={wlForm.name}
                  onChange={e => setWlForm(prev => ({ ...prev, name: e.target.value }))}
                  style={{
                    width: '140px', padding: '0.35rem', borderRadius: '0.25rem',
                    background: 'var(--bg-primary)', border: '1px solid var(--border)',
                    color: 'var(--text-primary)', fontSize: '0.8rem',
                  }}
                  required
                />
              </div>
              <div>
                <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.15rem' }}>마켓</label>
                <select
                  value={wlForm.market}
                  onChange={e => setWlForm(prev => ({ ...prev, market: e.target.value }))}
                  style={{
                    padding: '0.35rem', borderRadius: '0.25rem',
                    background: 'var(--bg-primary)', border: '1px solid var(--border)',
                    color: 'var(--text-primary)', fontSize: '0.8rem',
                  }}
                >
                  <option value="KR">KR</option>
                  <option value="US">US</option>
                </select>
              </div>
              <button type="submit" className="btn btn-primary btn-sm" disabled={wlSubmitting}>
                {wlSubmitting ? '추가 중...' : '추가'}
              </button>
            </form>
          </div>
        )}

        <table>
          <thead>
            <tr>
              <th>종목코드</th>
              <th>종목명</th>
              <th>마켓</th>
              <th>유형</th>
              <th>등록일</th>
              <th>관리</th>
            </tr>
          </thead>
          <tbody>
            {filteredWl.map((w) => (
              <tr key={`${w.symbol}-${w.market}`}>
                <td><code style={{ fontSize: '0.8rem' }}>{w.symbol}</code></td>
                <td>{w.name}</td>
                <td>
                  <span className={`badge ${w.market === 'KR' ? 'badge-buy' : 'badge-hold'}`}>
                    {w.market}
                  </span>
                </td>
                <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{w.asset_type}</td>
                <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {w.created_at ? new Date(w.created_at).toLocaleDateString('ko-KR') : '-'}
                </td>
                <td>
                  <button
                    className="btn btn-outline btn-sm"
                    onClick={() => handleWlRemove(w.symbol, w.market)}
                    style={{ color: 'var(--red)', borderColor: 'var(--red)' }}
                    title="제거"
                  >
                    {'\u2716'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
