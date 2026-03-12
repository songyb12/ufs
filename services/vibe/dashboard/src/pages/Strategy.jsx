import { useState, useEffect, useCallback } from 'react'
import { getStrategySettings, updateStrategySettings, resetStrategyParam } from '../api'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import { useToast } from '../components/Toast'

const CAT_ORDER = ['hard_limit', 'stance', 'position', 'cash']

export default function Strategy({ onNavigate, refreshKey }) {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState({}) // key → temp value
  const [saving, setSaving] = useState(false)
  const [showLog, setShowLog] = useState(false)

  const loadData = useCallback(() => {
    setLoading(true)
    getStrategySettings()
      .then(d => setData(d))
      .catch(err => toast.error('전략 설정 로드 실패: ' + err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData() }, [loadData, refreshKey])

  const handleSave = async (key) => {
    const val = editing[key]
    if (val == null) return
    setSaving(true)
    try {
      const result = await updateStrategySettings({ [key]: Number(val) })
      if (result.applied_count > 0 && result.applied?.length > 0) {
        const a = result.applied[0]
        toast.success(`${a.label}: ${a.old_value} → ${a.new_value}`)
      }
      setEditing(prev => { const n = { ...prev }; delete n[key]; return n })
      loadData()
    } catch (err) {
      toast.error('저장 실패: ' + err.message)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async (key) => {
    if (!confirm('이 파라미터를 기본값으로 되돌리시겠습니까?')) return
    try {
      const result = await resetStrategyParam(key)
      toast.success(result.message)
      loadData()
    } catch (err) {
      toast.error('초기화 실패: ' + err.message)
    }
  }

  if (loading) return <div className="loading"><span className="spinner" /> 로딩 중...</div>
  if (!data) return <div className="empty-state">No data</div>

  const { params, categories, change_log, modified_count } = data

  // Group params by category
  const grouped = {}
  for (const p of params) {
    if (!grouped[p.category]) grouped[p.category] = []
    grouped[p.category].push(p)
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'⚙️'} 전략 설정</h2>
          <p className="subtitle">VIBE 판단 기준값 조정 및 변경 이력</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button className="btn btn-outline" onClick={loadData}>{'↻'} Refresh</button>
          <HelpButton section="strategy" onNavigate={onNavigate} />
        </div>
      </div>

      <PageGuide
        pageId="strategy"
        title="전략 설정 가이드"
        steps={[
          'Hard Limit → 과매수 보호 기준. 보수적 운영 시 낮춤',
          '스탠스 기준 → 리스크 점수 기반 공격/방어 전환점',
          '포지션 관리 → 손절/익절/비중 기준',
          '변경 이력 → 언제 무엇이 바뀌었는지 추적',
        ]}
        color="#a855f7"
      />

      {/* Modified indicator */}
      {modified_count > 0 && (
        <div className="card" style={{ marginBottom: '1rem', borderLeft: '3px solid #a855f7', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 1rem' }}>
          <div>
            <span style={{ fontWeight: 600, color: '#a855f7' }}>{modified_count}개</span>
            <span style={{ color: 'var(--text-muted)', marginLeft: '0.5rem' }}>파라미터가 기본값에서 변경됨</span>
          </div>
          <button className="btn btn-sm btn-outline" onClick={() => setShowLog(!showLog)}>
            {showLog ? '설정 보기' : `변경 이력 (${change_log.length})`}
          </button>
        </div>
      )}

      {/* Change Log */}
      {showLog ? (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ fontSize: '0.9rem', marginBottom: '0.75rem' }}>{'📝'} 변경 이력</h3>
          {change_log.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>변경 이력이 없습니다.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
              {[...change_log].reverse().map((c, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: '0.5rem',
                  padding: '0.4rem 0.6rem', borderRadius: '4px',
                  background: c.reset ? 'rgba(168,85,247,0.06)' : 'var(--bg-primary)',
                  fontSize: '0.8rem',
                }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', minWidth: '120px' }}>
                    {c.changed_at?.replace('T', ' ')}
                  </span>
                  <span style={{ fontWeight: 600 }}>{c.label}</span>
                  <span style={{ color: 'var(--text-muted)' }}>{c.old_value}</span>
                  <span style={{ color: '#a855f7' }}>{'→'}</span>
                  <span style={{ fontWeight: 600, color: c.reset ? '#a855f7' : 'var(--text-primary)' }}>
                    {c.new_value}{c.reset ? ' (초기화)' : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <>
          {/* Parameter Groups */}
          {CAT_ORDER.map(catKey => {
            const cat = categories[catKey]
            if (!cat) return null
            const catParams = grouped[catKey] || []
            if (catParams.length === 0) return null

            return (
              <div key={catKey} className="card" style={{ marginBottom: '1rem', borderLeft: `3px solid ${cat.color}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                  <span style={{ fontSize: '1.1rem' }}>{cat.icon}</span>
                  <h3 style={{ fontSize: '0.9rem', margin: 0 }}>{cat.label}</h3>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>{cat.description}</div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {catParams.map(p => {
                    const isEditing = editing[p.key] != null
                    const displayVal = isEditing ? editing[p.key] : p.current_value
                    const isModified = p.is_modified

                    return (
                      <div key={p.key} style={{
                        display: 'grid', gridTemplateColumns: '1fr auto',
                        gap: '0.75rem', alignItems: 'center',
                        padding: '0.5rem 0.75rem', borderRadius: '6px',
                        background: isModified ? 'rgba(168,85,247,0.05)' : 'var(--bg-primary)',
                        border: isModified ? '1px solid rgba(168,85,247,0.2)' : '1px solid var(--border)',
                      }}>
                        <div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{p.label}</span>
                            {isModified && (
                              <span style={{ fontSize: '0.6rem', color: '#a855f7', fontWeight: 700, padding: '0 4px', background: 'rgba(168,85,247,0.1)', borderRadius: '3px' }}>
                                변경됨
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.1rem' }}>
                            {p.description}
                            {isModified && <span style={{ marginLeft: '0.5rem', color: '#a855f7' }}>(기본값: {p.default})</span>}
                          </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <input
                            type="number"
                            value={displayVal}
                            min={p.min}
                            max={p.max}
                            step={p.step}
                            onChange={e => setEditing(prev => ({ ...prev, [p.key]: e.target.value }))}
                            style={{
                              width: '80px', padding: '0.3rem 0.4rem', fontSize: '0.85rem',
                              textAlign: 'center', fontWeight: 600,
                              background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                              borderRadius: '4px', color: 'var(--text-primary)',
                            }}
                          />
                          {isEditing && (
                            <button className="btn btn-sm btn-primary"
                              disabled={saving}
                              onClick={() => handleSave(p.key)}
                              style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}>
                              {saving ? '...' : '저장'}
                            </button>
                          )}
                          {isModified && !isEditing && (
                            <button className="btn btn-sm btn-outline"
                              onClick={() => handleReset(p.key)}
                              style={{ fontSize: '0.65rem', padding: '0.15rem 0.4rem', color: '#a855f7', borderColor: '#a855f7' }}>
                              초기화
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </>
      )}

      {/* Footer note */}
      <div className="card" style={{ borderLeft: '3px solid var(--accent)', fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        <strong>{'ℹ️'} 참고</strong>
        <div style={{ marginTop: '0.25rem' }}>
          변경된 파라미터는 다음 파이프라인 실행부터 적용됩니다.
          현재는 표시 전용이며, 실제 파이프라인 코드에 반영하려면 별도 연동이 필요합니다.
          변경 이력은 자동으로 기록되어 추적 가능합니다.
        </div>
      </div>
    </div>
  )
}
