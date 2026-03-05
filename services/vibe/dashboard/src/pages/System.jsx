import { useState, useEffect } from 'react'
import {
  getHealth, getPipelineRuns, triggerPipeline,
  getWatchlist, addWatchlistItem, removeWatchlistItem,
} from '../api'

export default function System() {
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

  const [error, setError] = useState(null)

  const refresh = () => {
    setLoading(true)
    Promise.all([getHealth(), getPipelineRuns(), getWatchlist()])
      .then(([h, r, wl]) => { setHealth(h); setRuns(r); setWatchlist(wl || []); setError(null) })
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
          <div className="card-value blue">{health?.database?.prices?.toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="card-label">시그널</div>
          <div className="card-value blue">{health?.database?.signals?.toLocaleString()}</div>
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
