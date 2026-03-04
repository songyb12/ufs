import { useState, useEffect } from 'react'
import { getHealth, getPipelineRuns, triggerPipeline } from '../api'

export default function System() {
  const [health, setHealth] = useState(null)
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState(false)
  const [triggerResult, setTriggerResult] = useState(null)

  const refresh = () => {
    setLoading(true)
    Promise.all([getHealth(), getPipelineRuns()])
      .then(([h, r]) => { setHealth(h); setRuns(r) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

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

  if (loading) return <div className="loading"><span className="spinner" /> Loading...</div>

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'\u2699'} System</h2>
          <p className="subtitle">Service health, scheduler, and pipeline management</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-primary" onClick={() => handleTrigger('KR')} disabled={triggering}>
            {triggering ? 'Running...' : '\u25B6 Run KR'}
          </button>
          <button className="btn btn-primary" onClick={() => handleTrigger('US')} disabled={triggering}>
            {triggering ? 'Running...' : '\u25B6 Run US'}
          </button>
          <button className="btn btn-outline" onClick={refresh}>
            {'\u21BB'} Refresh
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
          <div className="card-label">Status</div>
          <div className={`card-value ${health?.status === 'healthy' ? 'green' : 'red'}`}>
            {health?.status || 'unknown'}
          </div>
          <div className="card-sub">v{health?.version}</div>
        </div>
        <div className="card">
          <div className="card-label">Database</div>
          <div className={`card-value ${health?.database?.connected ? 'green' : 'red'}`}>
            {health?.database?.connected ? 'Connected' : 'Down'}
          </div>
          <div className="card-sub">{health?.database?.tables} tables</div>
        </div>
        <div className="card">
          <div className="card-label">Prices</div>
          <div className="card-value blue">{health?.database?.prices?.toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="card-label">Signals</div>
          <div className="card-value blue">{health?.database?.signals?.toLocaleString()}</div>
        </div>
      </div>

      {/* Scheduler Jobs */}
      <div className="table-container">
        <div className="table-header">
          <h3>{'\u23F0'} Scheduled Jobs</h3>
          <span className={`badge ${health?.scheduler?.running ? 'badge-completed' : 'badge-failed'}`}>
            {health?.scheduler?.running ? 'Running' : 'Stopped'}
          </span>
        </div>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Next Run</th>
            </tr>
          </thead>
          <tbody>
            {(health?.scheduler?.jobs || []).map((job, i) => (
              <tr key={i}>
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
          <h3>{'\uD83D\uDD04'} Pipeline Run History</h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Market</th>
              <th>Status</th>
              <th>Started</th>
              <th>Completed</th>
              <th>Stages</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r, i) => {
              let stages = 0
              try {
                const parsed = typeof r.stages_completed === 'string' ? JSON.parse(r.stages_completed) : r.stages_completed
                stages = Array.isArray(parsed) ? parsed.length : 0
              } catch {}
              return (
                <tr key={i}>
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
          <div className="card-label">KR Pipeline</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
            <span className={`status-dot ${health?.pipelines?.KR?.status === 'completed' ? 'green' : 'red'}`} />
            <span>{health?.pipelines?.KR?.status}</span>
          </div>
          <div className="card-sub">
            Last: {health?.pipelines?.KR?.last_run ? new Date(health.pipelines.KR.last_run).toLocaleString('ko-KR') : 'never'}
          </div>
          <div className="card-sub">
            Age: {health?.pipelines?.KR?.age_hours != null ? `${health.pipelines.KR.age_hours}h` : '-'}
          </div>
        </div>
        <div className="card">
          <div className="card-label">US Pipeline</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
            <span className={`status-dot ${health?.pipelines?.US?.status === 'completed' ? 'green' : 'red'}`} />
            <span>{health?.pipelines?.US?.status}</span>
          </div>
          <div className="card-sub">
            Last: {health?.pipelines?.US?.last_run ? new Date(health.pipelines.US.last_run).toLocaleString('ko-KR') : 'never'}
          </div>
          <div className="card-sub">
            Age: {health?.pipelines?.US?.age_hours != null ? `${health.pipelines.US.age_hours}h` : '-'}
          </div>
        </div>
      </div>
    </div>
  )
}
