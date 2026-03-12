import { useState, useEffect } from 'react'
import { useToast } from '../components/Toast'
import {
  getHealth, getDataStatus, getPipelineRuns,
  triggerPipeline, refreshPrices, backfillForex,
  generateBriefing, generateMonthlyReport, runScreeningScan,
} from '../api'

const ACTION_GROUPS = [
  {
    title: '가격 갱신',
    icon: '💰',
    actions: [
      { id: 'price-all', label: '전체 가격', desc: 'KR+US 전 종목 현재가', fn: () => refreshPrices('ALL') },
      { id: 'price-kr', label: '한국장', desc: 'KRX 종목 현재가', fn: () => refreshPrices('KR') },
      { id: 'price-us', label: '미장', desc: 'US 종목 현재가', fn: () => refreshPrices('US') },
    ],
  },
  {
    title: '파이프라인',
    icon: '⚙',
    actions: [
      { id: 'pipe-all', label: '전체 실행', desc: '전 시장 파이프라인 (S1→S7)', fn: () => triggerPipeline('ALL') },
      { id: 'pipe-kr', label: '한국장', desc: 'KR 파이프라인', fn: () => triggerPipeline('KR') },
      { id: 'pipe-us', label: '미장', desc: 'US 파이프라인', fn: () => triggerPipeline('US') },
    ],
  },
  {
    title: '분석 갱신',
    icon: '📊',
    actions: [
      { id: 'forex', label: 'Forex 백필', desc: '환율 30일 데이터', fn: () => backfillForex(30) },
      { id: 'briefing', label: '브리핑 생성', desc: '오늘의 마켓 브리핑', fn: () => generateBriefing() },
      { id: 'monthly', label: '월간 리포트', desc: '이번 달 리포트 생성', fn: () => generateMonthlyReport() },
      { id: 'screen-kr', label: '스크리닝 (KR)', desc: '한국장 스크리닝 스캔', fn: () => runScreeningScan('KR', 5) },
    ],
  },
]

export default function DataAdmin({ refreshKey }) {
  const toast = useToast()
  const [health, setHealth] = useState(null)
  const [dataStatus, setDataStatus] = useState(null)
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState({}) // { actionId: true/false }

  const loadAll = () => {
    setLoading(true)
    Promise.all([
      getHealth().catch(() => null),
      getDataStatus().catch(() => null),
      getPipelineRuns().catch(() => []),
    ])
      .then(([h, ds, r]) => {
        setHealth(h)
        setDataStatus(ds?.tables || null)
        setRuns(Array.isArray(r) ? r : r?.runs || [])
      })
      .catch(() => toast.error('데이터 로드 실패'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadAll() }, [refreshKey])

  const handleAction = async (action) => {
    setRunning(prev => ({ ...prev, [action.id]: true }))
    try {
      const result = await action.fn()
      const msg = result?.message || result?.status || '완료'
      toast.success(`${action.label}: ${msg}`)
      // Reload status after brief delay
      setTimeout(loadAll, 2000)
    } catch (err) {
      toast.error(`${action.label} 실패: ${err.message}`)
    } finally {
      setRunning(prev => ({ ...prev, [action.id]: false }))
    }
  }

  const handleRefreshAll = async () => {
    setRunning(prev => ({ ...prev, 'refresh-all': true }))
    try {
      // Price refresh → pipeline → briefing (sequential)
      toast.success('일괄 갱신 시작: 가격 → 파이프라인 → 브리핑')
      const priceRes = await refreshPrices('ALL')
      toast.success(`가격 갱신 완료 (${priceRes?.total_rows || 0}건)`)

      const pipeRes = await triggerPipeline('ALL')
      toast.success(`파이프라인 ${pipeRes?.status || '완료'}`)

      try { await generateBriefing() } catch { /* optional */ }
      toast.success('일괄 갱신 전체 완료!')
      setTimeout(loadAll, 2000)
    } catch (err) {
      toast.error(`일괄 갱신 중 오류: ${err.message}`)
    } finally {
      setRunning(prev => ({ ...prev, 'refresh-all': false }))
    }
  }

  if (loading) return <div className="loading">⏳ 시스템 데이터 로딩...</div>

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>📋 데이터 관리</h2>
          <p style={{ color: 'var(--text-muted)', margin: '0.25rem 0 0' }}>
            전체 시스템 데이터를 일괄 확인하고 갱신합니다
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn" onClick={loadAll} style={{ fontSize: '0.8rem' }}>↻ 새로고침</button>
          <button
            className="btn btn-primary"
            onClick={handleRefreshAll}
            disabled={running['refresh-all']}
            style={{ fontSize: '0.8rem', fontWeight: 700 }}
          >
            {running['refresh-all'] ? '⏳ 갱신 중...' : '🚀 일괄 전체 갱신'}
          </button>
        </div>
      </div>

      {/* Health Status */}
      {health && (
        <div className="card" style={{ marginBottom: '1rem', borderLeft: `4px solid ${health.status === 'healthy' ? 'var(--green)' : 'var(--red)'}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>
              {health.status === 'healthy' ? '🟢' : '🔴'} {health.service} v{health.version}
            </span>
            {health.uptime_seconds && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Uptime: {Math.floor(health.uptime_seconds / 3600)}h {Math.floor((health.uptime_seconds % 3600) / 60)}m
              </span>
            )}
            {health.scheduler_status && (
              <span style={{ fontSize: '0.75rem', padding: '0.15rem 0.5rem', borderRadius: '1rem', background: health.scheduler_status === 'running' ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)', color: health.scheduler_status === 'running' ? 'var(--green)' : 'var(--red)' }}>
                스케줄러: {health.scheduler_status}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Action Groups */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        {ACTION_GROUPS.map(group => (
          <div key={group.title} className="card">
            <h3 style={{ marginBottom: '0.75rem', fontSize: '0.9rem' }}>{group.icon} {group.title}</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {group.actions.map(action => (
                <button
                  key={action.id}
                  className="btn"
                  onClick={() => handleAction(action)}
                  disabled={running[action.id]}
                  style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '0.5rem 0.75rem', fontSize: '0.8rem', textAlign: 'left',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{action.label}</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{action.desc}</div>
                  </div>
                  <span style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                    {running[action.id] ? '⏳' : '▶'}
                  </span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Data Status Table */}
      {dataStatus && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginBottom: '0.75rem' }}>📊 데이터 현황</h3>
          <div className="table-container">
            <table className="table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>테이블</th>
                  <th style={{ textAlign: 'right' }}>행 수</th>
                  <th>최신 날짜</th>
                  <th>기간</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(dataStatus).map(([table, info]) => (
                  <tr key={table}>
                    <td style={{ fontWeight: 600, fontFamily: 'monospace', fontSize: '0.8rem' }}>{table}</td>
                    <td style={{ textAlign: 'right', fontWeight: 700 }}>{info.count?.toLocaleString() ?? '-'}</td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{info.latest_date || info.latest || '-'}</td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{info.date_range || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent Pipeline Runs */}
      {runs.length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: '0.75rem' }}>🔄 최근 파이프라인 실행</h3>
          <div className="table-container">
            <table className="table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>시간</th>
                  <th>마켓</th>
                  <th>상태</th>
                  <th>소요시간</th>
                  <th>결과</th>
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 15).map((r, i) => (
                  <tr key={i}>
                    <td style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                      {r.started_at ? new Date(r.started_at).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-'}
                    </td>
                    <td><span style={{ fontWeight: 700 }}>{r.market}</span></td>
                    <td>
                      <span style={{
                        padding: '0.1rem 0.4rem', borderRadius: '0.25rem', fontSize: '0.7rem', fontWeight: 700,
                        background: r.status === 'completed' ? 'rgba(34,197,94,0.15)' : r.status === 'failed' ? 'rgba(239,68,68,0.15)' : 'rgba(234,179,8,0.15)',
                        color: r.status === 'completed' ? 'var(--green)' : r.status === 'failed' ? 'var(--red)' : 'var(--yellow)',
                      }}>
                        {r.status}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.75rem' }}>{r.duration_seconds ? `${r.duration_seconds.toFixed(1)}s` : '-'}</td>
                    <td style={{ fontSize: '0.72rem', color: 'var(--text-muted)', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {r.error || r.summary || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
