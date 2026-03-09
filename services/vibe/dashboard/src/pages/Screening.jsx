import { useState, useEffect, useCallback } from 'react'
import { getScreeningCandidates, runScreeningScan, updateScreeningStatus } from '../api'
import SymbolModal from '../components/SymbolModal'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import { useToast } from '../components/Toast'

const TRIGGER_INFO = {
  volume_spike: { label: '거래량 급증', icon: '📈', color: '#3b82f6', desc: '20일 평균 대비 3배 이상' },
  new_high: { label: '신고가', icon: '⬆', color: '#22c55e', desc: '52주 최고가 돌파' },
  breakout: { label: '돌파', icon: '🚀', color: '#a855f7', desc: '볼린저밴드 상단 + 거래량 확인' },
  capitulation: { label: '투매', icon: '📉', color: '#ef4444', desc: '거래량 2배 + 5일간 -3% 하락' },
}

export default function Screening({ onNavigate, refreshKey }) {
  const toast = useToast()
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [market, setMarket] = useState('KR')
  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState(null)
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [sortKey, setSortKey] = useState('score')
  const [sortDir, setSortDir] = useState('desc')
  const [daysBack, setDaysBack] = useState(5)
  const [triggerFilter, setTriggerFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [viewMode, setViewMode] = useState('card') // 'card' or 'table'

  const loadCandidates = useCallback(() => {
    setLoading(true)
    getScreeningCandidates(market)
      .then(data => { setCandidates(data.candidates || []); setError(null) })
      .catch(err => { console.error(err); setError(err.message); toast.error('스크리닝 로드 실패: ' + err.message) })
      .finally(() => setLoading(false))
  }, [market])

  useEffect(() => { loadCandidates() }, [loadCandidates, refreshKey])

  const handleScan = async () => {
    setScanning(true)
    setScanResult(null)
    try {
      const r = await runScreeningScan(market, daysBack)
      setScanResult({ type: 'success', text: `${r.candidates_found}개 후보 발견, ${r.stored}개 저장` })
      toast.success(`${market} 스크리닝 완료: ${r.candidates_found}개 후보`)
      loadCandidates()
    } catch (err) {
      setScanResult({ type: 'error', text: `실패: ${err.message}` })
      toast.error('스크리닝 실패: ' + err.message)
    } finally {
      setScanning(false)
    }
  }

  const handleStatusChange = async (ids, newStatus) => {
    const idList = Array.isArray(ids) ? ids : [ids]
    try {
      for (const id of idList) {
        await updateScreeningStatus(id, newStatus)
      }
      toast.success(`상태 변경: ${newStatus}`)
      setCandidates(prev => prev.map(c =>
        idList.includes(c.id) ? { ...c, status: newStatus } : c
      ))
    } catch (err) {
      toast.error('상태 변경 실패: ' + err.message)
    }
  }

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir(prev => prev === 'desc' ? 'asc' : 'desc')
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  // Group candidates by (symbol, market, detected_date)
  const grouped = (() => {
    const map = new Map()
    candidates.forEach(c => {
      const key = `${c.symbol}|${c.market}|${c.detected_date || c.scan_date || ''}`
      if (map.has(key)) {
        const existing = map.get(key)
        if (c.trigger_type && !existing.triggers.includes(c.trigger_type)) {
          existing.triggers.push(c.trigger_type)
        }
        const cScore = c.score || c.composite_score || 0
        if (cScore > (existing.score || 0)) existing.score = cScore
        if (!existing.ids) existing.ids = [existing.id]
        existing.ids.push(c.id)
      } else {
        map.set(key, { ...c, triggers: [c.trigger_type].filter(Boolean), ids: [c.id] })
      }
    })
    return [...map.values()]
  })()

  // Apply filters
  const filtered = grouped.filter(c => {
    if (triggerFilter !== 'all' && !(c.triggers || []).includes(triggerFilter)) return false
    if (statusFilter !== 'all' && c.status !== statusFilter) return false
    return true
  })

  const sorted = [...filtered].sort((a, b) => {
    let av = a[sortKey], bv = b[sortKey]
    if (typeof av === 'string') av = av?.toLowerCase() || ''
    if (typeof bv === 'string') bv = bv?.toLowerCase() || ''
    if (av == null) return 1
    if (bv == null) return -1
    return sortDir === 'desc' ? (bv > av ? 1 : -1) : (av > bv ? 1 : -1)
  })

  // Stats
  const avgScore = grouped.length > 0
    ? grouped.reduce((sum, c) => sum + (c.score || c.composite_score || 0), 0) / grouped.length : 0
  const highConviction = grouped.filter(c => (c.score || c.composite_score || 0) >= 7).length
  const triggerCounts = {}
  grouped.forEach(c => (c.triggers || []).forEach(t => { triggerCounts[t] = (triggerCounts[t] || 0) + 1 }))

  const scoreColor = (score) => score >= 7 ? 'var(--green)' : score >= 5 ? 'var(--yellow)' : 'var(--red)'
  const scoreBg = (score) => score >= 7 ? 'rgba(34,197,94,0.12)' : score >= 5 ? 'rgba(234,179,8,0.12)' : 'rgba(239,68,68,0.12)'

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div>
          <h2>🔍 스크리닝</h2>
          <p className="subtitle">매수 후보 종목 자동 발굴</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <select value={daysBack} onChange={e => setDaysBack(Number(e.target.value))}
            style={{ padding: '0.4rem 0.5rem', borderRadius: '0.375rem', background: 'var(--bg-secondary)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: '0.8rem' }}>
            <option value={3}>3일</option>
            <option value={5}>5일</option>
            <option value={10}>10일</option>
            <option value={30}>30일</option>
          </select>
          <button className="btn btn-primary" onClick={handleScan} disabled={scanning}>
            {scanning ? '⏳ 스캔 중...' : `🔍 ${market} 스캔`}
          </button>
          <button className="btn btn-outline" onClick={loadCandidates}>↻</button>
          <HelpButton section="screening" onNavigate={onNavigate} />
        </div>
      </div>

      <PageGuide
        pageId="screening"
        title="이 페이지에서 확인할 것"
        steps={[
          '스캔 실행 → 워치리스트 종목에서 기술적 후보 자동 발굴',
          '거래량 급증 + 신고가/돌파 = 관심 후보',
          '투매(Capitulation) 감지 → 역발상 매수 후보',
          '승인한 종목 → 다음 파이프라인에서 시그널 생성',
        ]}
        color="#22c55e"
      />

      {/* Scan Result Banner */}
      {scanResult && (
        <div style={{
          marginBottom: '1rem', padding: '0.6rem 1rem', borderRadius: '0.5rem',
          background: scanResult.type === 'error' ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)',
          border: `1px solid ${scanResult.type === 'error' ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)'}`,
          color: scanResult.type === 'error' ? 'var(--red)' : 'var(--green)',
          fontSize: '0.85rem',
        }}>
          {scanResult.type === 'error' ? '❌' : '✅'} {scanResult.text}
        </div>
      )}

      {/* Filter Bar */}
      <div style={{
        display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center',
        marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '0.5rem',
        background: 'var(--bg-secondary)', border: '1px solid var(--border)',
      }}>
        {/* Market */}
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          {['KR', 'US'].map(m => (
            <button key={m} onClick={() => setMarket(m)}
              style={{
                padding: '0.3rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.8rem', fontWeight: 600,
                border: '1px solid var(--border)', cursor: 'pointer',
                background: market === m ? 'var(--accent)' : 'transparent',
                color: market === m ? '#fff' : 'var(--text-secondary)',
              }}>
              {m === 'KR' ? '🇰🇷 KR' : '🇺🇸 US'}
            </button>
          ))}
        </div>

        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>│</span>

        {/* Trigger Filter */}
        <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
          <button onClick={() => setTriggerFilter('all')}
            style={{
              padding: '0.25rem 0.5rem', borderRadius: '0.375rem', fontSize: '0.75rem',
              border: '1px solid var(--border)', cursor: 'pointer',
              background: triggerFilter === 'all' ? 'var(--bg-primary)' : 'transparent',
              color: triggerFilter === 'all' ? 'var(--text-primary)' : 'var(--text-muted)',
              fontWeight: triggerFilter === 'all' ? 600 : 400,
            }}>
            전체 {grouped.length}
          </button>
          {Object.entries(TRIGGER_INFO).map(([key, info]) => {
            const count = triggerCounts[key] || 0
            if (count === 0) return null
            return (
              <button key={key} onClick={() => setTriggerFilter(triggerFilter === key ? 'all' : key)}
                style={{
                  padding: '0.25rem 0.5rem', borderRadius: '0.375rem', fontSize: '0.75rem',
                  border: `1px solid ${triggerFilter === key ? info.color : 'var(--border)'}`,
                  cursor: 'pointer',
                  background: triggerFilter === key ? `${info.color}18` : 'transparent',
                  color: triggerFilter === key ? info.color : 'var(--text-muted)',
                  fontWeight: triggerFilter === key ? 600 : 400,
                }}>
                {info.icon} {info.label} {count}
              </button>
            )
          })}
        </div>

        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>│</span>

        {/* Status Filter */}
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          {[
            { key: 'all', label: '전체' },
            { key: 'new', label: '신규' },
            { key: 'approved', label: '승인' },
            { key: 'rejected', label: '거절' },
          ].map(f => (
            <button key={f.key} onClick={() => setStatusFilter(f.key)}
              style={{
                padding: '0.25rem 0.5rem', borderRadius: '0.375rem', fontSize: '0.75rem',
                border: '1px solid var(--border)', cursor: 'pointer',
                background: statusFilter === f.key ? 'var(--bg-primary)' : 'transparent',
                color: statusFilter === f.key ? 'var(--text-primary)' : 'var(--text-muted)',
                fontWeight: statusFilter === f.key ? 600 : 400,
              }}>
              {f.label}
            </button>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* View Mode Toggle */}
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          <button onClick={() => setViewMode('card')} title="카드 뷰"
            style={{
              padding: '0.3rem 0.5rem', borderRadius: '0.375rem', fontSize: '0.8rem',
              border: '1px solid var(--border)', cursor: 'pointer',
              background: viewMode === 'card' ? 'var(--accent)' : 'transparent',
              color: viewMode === 'card' ? '#fff' : 'var(--text-muted)',
            }}>▦</button>
          <button onClick={() => setViewMode('table')} title="테이블 뷰"
            style={{
              padding: '0.3rem 0.5rem', borderRadius: '0.375rem', fontSize: '0.8rem',
              border: '1px solid var(--border)', cursor: 'pointer',
              background: viewMode === 'table' ? 'var(--accent)' : 'transparent',
              color: viewMode === 'table' ? '#fff' : 'var(--text-muted)',
            }}>☰</button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', marginBottom: '1rem' }}>
        <div className="card">
          <div className="card-label">후보 종목</div>
          <div className="card-value blue">{grouped.length}</div>
          <div className="card-sub">{filtered.length !== grouped.length ? `필터 적용: ${filtered.length}개` : `${market} 마켓`}</div>
        </div>
        <div className="card">
          <div className="card-label">고확신</div>
          <div className="card-value green">{highConviction}</div>
          <div className="card-sub">스코어 ≥ 7</div>
        </div>
        <div className="card">
          <div className="card-label">평균 스코어</div>
          <div className={`card-value ${avgScore >= 6 ? 'green' : avgScore >= 4 ? 'yellow' : 'red'}`}>
            {avgScore.toFixed(1)}
          </div>
        </div>
        <div className="card">
          <div className="card-label">마지막 스캔</div>
          <div className="card-value blue" style={{ fontSize: '0.9rem' }}>
            {candidates.length > 0 && candidates[0]?.scan_date ? candidates[0].scan_date : 'N/A'}
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '0.5rem', background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', color: 'var(--red)', fontSize: '0.85rem' }}>
          ❌ {error}
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="loading"><span className="spinner" /> 로딩 중...</div>
      ) : sorted.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🔍</div>
          <p style={{ marginBottom: '0.5rem' }}>
            {grouped.length === 0 ? `${market} 스크리닝 후보가 없습니다.` : '필터 조건에 맞는 후보가 없습니다.'}
          </p>
          {grouped.length === 0 && (
            <button className="btn btn-primary" onClick={handleScan} disabled={scanning} style={{ marginTop: '0.5rem' }}>
              🔍 {market} 스캔 시작
            </button>
          )}
        </div>
      ) : viewMode === 'card' ? (
        /* ── Card View ── */
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '0.75rem',
        }}>
          {sorted.map((c, idx) => {
            const score = c.score || c.composite_score || 0
            const rsi = c.rsi ?? c.rsi_14
            const isApproved = c.status === 'approved'
            const isRejected = c.status === 'rejected'
            return (
              <div key={`${c.symbol}-${c.market}-${idx}`} style={{
                background: 'var(--bg-secondary)', border: `1px solid ${isApproved ? 'rgba(34,197,94,0.4)' : isRejected ? 'rgba(239,68,68,0.2)' : 'var(--border)'}`,
                borderRadius: '0.75rem', padding: '1rem', position: 'relative',
                opacity: isRejected ? 0.55 : 1,
                transition: 'all 0.15s ease',
              }}>
                {/* Top Row: Symbol + Score */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.6rem' }}>
                  <div>
                    <span style={{ fontWeight: 700, fontSize: '1.05rem', cursor: 'pointer', color: 'var(--accent)' }}
                      onClick={() => setSelectedSymbol({ symbol: c.symbol, market: c.market || market })}>
                      {c.symbol}
                    </span>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.1rem' }}>
                      {c.name || '-'}
                    </div>
                  </div>
                  <div style={{
                    padding: '0.2rem 0.6rem', borderRadius: '9999px', fontSize: '0.85rem', fontWeight: 700,
                    background: scoreBg(score), color: scoreColor(score),
                    minWidth: '2.5rem', textAlign: 'center',
                  }}>
                    {score.toFixed(1)}
                  </div>
                </div>

                {/* Triggers */}
                <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap', marginBottom: '0.6rem' }}>
                  {(c.triggers || []).map(t => {
                    const info = TRIGGER_INFO[t] || { label: t, icon: '📌', color: '#94a3b8' }
                    return (
                      <span key={t} style={{
                        display: 'inline-flex', alignItems: 'center', gap: '0.2rem',
                        padding: '0.2rem 0.5rem', borderRadius: '0.375rem',
                        fontSize: '0.7rem', fontWeight: 600,
                        background: `${info.color}15`, color: info.color,
                        border: `1px solid ${info.color}30`,
                      }}>
                        {info.icon} {info.label}
                      </span>
                    )
                  })}
                </div>

                {/* Metrics Row */}
                <div style={{
                  display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
                  gap: '0.5rem', marginBottom: '0.6rem',
                  padding: '0.5rem', borderRadius: '0.5rem',
                  background: 'var(--bg-primary)',
                }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.15rem' }}>RSI</div>
                    <div style={{
                      fontSize: '0.85rem', fontWeight: 600,
                      color: rsi != null ? (rsi > 65 ? 'var(--red)' : rsi < 35 ? 'var(--green)' : 'var(--text-primary)') : 'var(--text-muted)',
                    }}>
                      {rsi != null ? rsi.toFixed(1) : '-'}
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.15rem' }}>거래량비</div>
                    <div style={{
                      fontSize: '0.85rem', fontWeight: 600,
                      color: c.volume_ratio != null ? (c.volume_ratio >= 3 ? '#3b82f6' : 'var(--text-primary)') : 'var(--text-muted)',
                    }}>
                      {c.volume_ratio != null ? `${c.volume_ratio.toFixed(1)}x` : '-'}
                    </div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.15rem' }}>등락</div>
                    <div style={{
                      fontSize: '0.85rem', fontWeight: 600,
                      color: c.price_change != null ? (c.price_change >= 0 ? 'var(--green)' : 'var(--red)') : 'var(--text-muted)',
                    }}>
                      {c.price_change != null ? `${c.price_change >= 0 ? '+' : ''}${c.price_change.toFixed(1)}%` : '-'}
                    </div>
                  </div>
                </div>

                {/* Bottom: Date + Status Actions */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    {c.detected_date || c.scan_date || c.created_at?.slice(0, 10) || '-'}
                  </span>
                  <div style={{ display: 'flex', gap: '0.3rem' }}>
                    {isApproved ? (
                      <button onClick={() => handleStatusChange(c.ids || [c.id], 'new')}
                        style={{ padding: '0.2rem 0.5rem', borderRadius: '0.375rem', fontSize: '0.7rem', fontWeight: 600, border: '1px solid var(--green)', background: 'rgba(34,197,94,0.12)', color: 'var(--green)', cursor: 'pointer' }}>
                        ✅ 승인됨
                      </button>
                    ) : isRejected ? (
                      <button onClick={() => handleStatusChange(c.ids || [c.id], 'new')}
                        style={{ padding: '0.2rem 0.5rem', borderRadius: '0.375rem', fontSize: '0.7rem', fontWeight: 600, border: '1px solid var(--red)', background: 'rgba(239,68,68,0.12)', color: 'var(--red)', cursor: 'pointer' }}>
                        ❌ 거절됨
                      </button>
                    ) : (
                      <>
                        <button onClick={() => handleStatusChange(c.ids || [c.id], 'approved')}
                          style={{ padding: '0.2rem 0.5rem', borderRadius: '0.375rem', fontSize: '0.7rem', border: '1px solid var(--green)', background: 'transparent', color: 'var(--green)', cursor: 'pointer', fontWeight: 600 }}>
                          승인
                        </button>
                        <button onClick={() => handleStatusChange(c.ids || [c.id], 'rejected')}
                          style={{ padding: '0.2rem 0.5rem', borderRadius: '0.375rem', fontSize: '0.7rem', border: '1px solid var(--red)', background: 'transparent', color: 'var(--red)', cursor: 'pointer', fontWeight: 600 }}>
                          거절
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        /* ── Table View ── */
        <div className="table-container">
          <div className="table-header">
            <h3>스크리닝 후보</h3>
            <span className="card-sub">{filtered.length}개 ({candidates.length} 트리거)</span>
          </div>
          <table>
            <thead>
              <tr>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('symbol')}>
                  종목 {sortKey === 'symbol' ? (sortDir === 'desc' ? '▼' : '▲') : ''}
                </th>
                <th className="hide-on-mobile">이름</th>
                <th style={{ cursor: 'pointer' }} onClick={() => handleSort('score')}>
                  스코어 {sortKey === 'score' ? (sortDir === 'desc' ? '▼' : '▲') : ''}
                </th>
                <th className="hide-on-tablet">RSI</th>
                <th className="hide-on-tablet">거래량비</th>
                <th className="hide-on-mobile" style={{ cursor: 'pointer' }} onClick={() => handleSort('price_change')}>
                  등락 {sortKey === 'price_change' ? (sortDir === 'desc' ? '▼' : '▲') : ''}
                </th>
                <th>트리거</th>
                <th className="hide-on-mobile">상태</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((c, idx) => {
                const score = c.score || c.composite_score || 0
                const rsi = c.rsi ?? c.rsi_14
                return (
                  <tr key={`${c.symbol}-${c.market}-${idx}`} style={{ opacity: c.status === 'rejected' ? 0.5 : 1 }}>
                    <td className="symbol-link" onClick={() => setSelectedSymbol({ symbol: c.symbol, market: c.market || market })}>
                      <strong>{c.symbol}</strong>
                    </td>
                    <td className="hide-on-mobile" style={{ maxWidth: 130, fontSize: '0.8rem' }}>{c.name || '-'}</td>
                    <td>
                      <span style={{
                        display: 'inline-block', padding: '0.125rem 0.5rem', borderRadius: '9999px',
                        fontSize: '0.75rem', fontWeight: 700, background: scoreBg(score), color: scoreColor(score),
                      }}>
                        {score.toFixed(1)}
                      </span>
                    </td>
                    <td className="hide-on-tablet">{rsi != null ? rsi.toFixed(1) : '-'}</td>
                    <td className="hide-on-tablet">{c.volume_ratio != null ? `${c.volume_ratio.toFixed(1)}x` : '-'}</td>
                    <td className="hide-on-mobile" style={{ color: (c.price_change || 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                      {c.price_change != null ? `${c.price_change >= 0 ? '+' : ''}${c.price_change.toFixed(2)}%` : '-'}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.2rem', flexWrap: 'wrap' }}>
                        {(c.triggers || []).map(t => {
                          const info = TRIGGER_INFO[t] || { label: t, icon: '📌', color: '#94a3b8' }
                          return (
                            <span key={t} style={{
                              display: 'inline-block', padding: '0.1rem 0.3rem', borderRadius: '4px',
                              fontSize: '0.6rem', fontWeight: 600,
                              background: `${info.color}15`, color: info.color,
                              border: `1px solid ${info.color}30`,
                            }}>
                              {info.icon} {info.label}
                            </span>
                          )
                        })}
                      </div>
                    </td>
                    <td className="hide-on-mobile">
                      <div style={{ display: 'flex', gap: '0.2rem', alignItems: 'center' }}>
                        {c.status === 'approved' ? (
                          <span style={{ fontSize: '0.7rem', color: 'var(--green)', fontWeight: 600, cursor: 'pointer' }}
                            onClick={() => handleStatusChange(c.ids || [c.id], 'new')}>✅ 승인</span>
                        ) : c.status === 'rejected' ? (
                          <span style={{ fontSize: '0.7rem', color: 'var(--red)', fontWeight: 600, cursor: 'pointer' }}
                            onClick={() => handleStatusChange(c.ids || [c.id], 'new')}>❌ 거절</span>
                        ) : (
                          <>
                            <button style={{ padding: '0.1rem 0.3rem', fontSize: '0.6rem', borderRadius: '3px', border: '1px solid var(--green)', background: 'transparent', color: 'var(--green)', cursor: 'pointer' }}
                              onClick={() => handleStatusChange(c.ids || [c.id], 'approved')}>승인</button>
                            <button style={{ padding: '0.1rem 0.3rem', fontSize: '0.6rem', borderRadius: '3px', border: '1px solid var(--red)', background: 'transparent', color: 'var(--red)', cursor: 'pointer' }}
                              onClick={() => handleStatusChange(c.ids || [c.id], 'rejected')}>거절</button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

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
