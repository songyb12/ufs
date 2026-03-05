import { useState, useEffect, useCallback } from 'react'
import {
  getSummary, getPortfolio, getPortfolioScenarios, getWatchlist,
  addPosition, deletePosition, quickAddPositions, exportPortfolioCSV,
  getPortfolioGroups, createPortfolioGroup, deletePortfolioGroup,
} from '../api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from 'recharts'
import SymbolModal from '../components/SymbolModal'
import HelpButton from '../components/HelpButton'

export default function Portfolio({ onNavigate }) {
  const [summary, setSummary] = useState(null)
  const [scenarios, setScenarios] = useState(null)
  const [positions, setPositions] = useState([])
  const [watchlist, setWatchlist] = useState([])
  const [loading, setLoading] = useState(true)

  // Portfolio group state
  const [groups, setGroups] = useState([])
  const [activeGroupId, setActiveGroupId] = useState(1)
  const [showGroupForm, setShowGroupForm] = useState(false)
  const [newGroupName, setNewGroupName] = useState('')

  // CRUD state
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingSymbol, setEditingSymbol] = useState(null)
  const [editData, setEditData] = useState({})
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState(null)
  const [formData, setFormData] = useState({
    symbol: '', market: 'KR', position_size: '', entry_price: '', entry_date: '', sector: ''
  })

  const [error, setError] = useState(null)
  const [selectedSymbol, setSelectedSymbol] = useState(null)

  const loadGroups = useCallback(() => {
    return getPortfolioGroups()
      .then(data => {
        const g = data?.groups || []
        setGroups(g)
        // If activeGroupId not in groups, reset to first
        if (g.length > 0 && !g.find(x => x.id === activeGroupId)) {
          setActiveGroupId(g[0].id)
        }
        return g
      })
      .catch(err => { console.error('Groups load error:', err) })
  }, [activeGroupId])

  const loadData = useCallback((groupId) => {
    const gid = groupId || activeGroupId
    setLoading(true)
    Promise.all([getSummary(gid), getPortfolio(null, gid), getPortfolioScenarios(), getWatchlist()])
      .then(([s, p, sc, wl]) => {
        setSummary(s)
        setPositions(p?.positions || [])
        setScenarios(sc)
        setWatchlist(wl || [])
        setError(null)
      })
      .catch(err => { console.error(err); setError(err.message) })
      .finally(() => setLoading(false))
  }, [activeGroupId])

  useEffect(() => {
    loadGroups().then(() => loadData())
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Reload data when group changes
  const switchGroup = (gid) => {
    setActiveGroupId(gid)
    loadData(gid)
  }

  const showMessage = (text, type = 'success') => {
    setMessage({ text, type })
    setTimeout(() => setMessage(null), 3000)
  }

  // ---- 그룹 추가 ----
  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) return
    setSubmitting(true)
    try {
      const res = await createPortfolioGroup(newGroupName.trim())
      showMessage(`포트폴리오 "${newGroupName}" 생성 완료`)
      setNewGroupName('')
      setShowGroupForm(false)
      await loadGroups()
      switchGroup(res.id)
    } catch (err) {
      showMessage(`생성 실패: ${err.message}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  // ---- 그룹 삭제 ----
  const handleDeleteGroup = async (gid) => {
    const g = groups.find(x => x.id === gid)
    if (!g || g.is_default) return
    if (!confirm(`"${g.name}" 포트폴리오를 삭제하시겠습니까?\n포함된 모든 종목이 함께 삭제됩니다.`)) return
    setSubmitting(true)
    try {
      await deletePortfolioGroup(gid)
      showMessage(`"${g.name}" 삭제 완료`)
      await loadGroups()
      switchGroup(1) // back to default
    } catch (err) {
      showMessage(`삭제 실패: ${err.message}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  // ---- 종목 추가 ----
  const handleAdd = async (e) => {
    e.preventDefault()
    if (!formData.symbol || !formData.position_size) return
    setSubmitting(true)
    try {
      if (formData.entry_price) {
        await addPosition({
          symbol: formData.symbol,
          market: formData.market,
          position_size: parseFloat(formData.position_size),
          entry_price: parseFloat(formData.entry_price),
          entry_date: formData.entry_date || undefined,
          sector: formData.sector || undefined,
          portfolio_id: activeGroupId,
        })
      } else {
        await quickAddPositions([{
          symbol: formData.symbol,
          market: formData.market,
          position_size: parseFloat(formData.position_size),
        }], activeGroupId)
      }
      showMessage(`${formData.symbol} 추가 완료`)
      setFormData({ symbol: '', market: 'KR', position_size: '', entry_price: '', entry_date: '', sector: '' })
      setShowAddForm(false)
      loadData()
    } catch (err) {
      showMessage(`추가 실패: ${err.message}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  // ---- 종목 삭제 ----
  const handleDelete = async (market, symbol) => {
    if (!confirm(`${symbol} (${market}) 종목을 삭제하시겠습니까?`)) return
    setSubmitting(true)
    try {
      await deletePosition(market, symbol, activeGroupId)
      showMessage(`${symbol} 삭제 완료`)
      loadData()
    } catch (err) {
      showMessage(`삭제 실패: ${err.message}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  // ---- 종목 수정 ----
  const startEdit = (p) => {
    setEditingSymbol(p.symbol)
    setEditData({
      position_size: p.position_size || '',
      entry_price: p.entry_price || '',
    })
  }

  const cancelEdit = () => {
    setEditingSymbol(null)
    setEditData({})
  }

  const handleSaveEdit = async (p) => {
    setSubmitting(true)
    try {
      await addPosition({
        symbol: p.symbol,
        market: p.market,
        position_size: parseFloat(editData.position_size),
        entry_price: editData.entry_price ? parseFloat(editData.entry_price) : p.entry_price,
        entry_date: p.entry_date,
        sector: p.sector,
        portfolio_id: activeGroupId,
      })
      showMessage(`${p.symbol} 수정 완료`)
      setEditingSymbol(null)
      setEditData({})
      loadData()
    } catch (err) {
      showMessage(`수정 실패: ${err.message}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  // ---- Watchlist 드롭다운에서 종목 선택 ----
  const handleWatchlistSelect = (e) => {
    const val = e.target.value
    if (!val) {
      setFormData(prev => ({ ...prev, symbol: '', market: 'KR' }))
      return
    }
    const [sym, mkt] = val.split('|')
    setFormData(prev => ({ ...prev, symbol: sym, market: mkt }))
  }

  if (loading) return <div className="loading"><span className="spinner" /> Loading...</div>
  if (error) return <div className="loading" style={{ color: 'var(--red)' }}>Error: {error}</div>

  const pnlPct = summary?.portfolio?.total_pnl_pct || 0
  const activeGroup = groups.find(g => g.id === activeGroupId)

  // P&L chart data
  const pnlData = positions.map(p => ({
    name: p.name || p.symbol,
    pnl: p.pnl_pct || 0,
    market: p.market,
  })).sort((a, b) => b.pnl - a.pnl)

  const held = scenarios?.held_scenarios || []
  const entry = scenarios?.entry_scenarios || []

  // held_scenarios를 symbol 기반 map으로 변환
  const heldMap = {}
  if (Array.isArray(held)) {
    held.forEach(s => { heldMap[s.symbol] = s })
  }

  // entry_scenarios를 symbol 기반 map으로 변환
  const entryMap = {}
  if (Array.isArray(entry)) {
    entry.forEach(s => { entryMap[s.symbol] = s })
  }

  const formatKRW = (v) => {
    if (v == null) return '-'
    if (v >= 100000000) return `${(v / 100000000).toFixed(1)}억`
    if (v >= 10000) return `${(v / 10000).toFixed(0)}만`
    return v?.toLocaleString() || '-'
  }

  const totalInvested = positions.reduce((sum, p) => sum + (p.position_size || 0), 0)

  // Watchlist를 마켓별로 그룹화
  const wlKR = watchlist.filter(w => w.market === 'KR')
  const wlUS = watchlist.filter(w => w.market === 'US')

  const inputStyle = {
    width: '100%', padding: '0.5rem', borderRadius: '0.375rem',
    background: 'var(--bg-primary)', border: '1px solid var(--border)',
    color: 'var(--text-primary)', fontSize: '0.8125rem',
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>{'\uD83D\uDCBC'} 포트폴리오</h2>
          <p className="subtitle">
            {activeGroup?.name || '기본 포트폴리오'} — {positions.length}개 보유 종목
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button
            className="btn btn-primary"
            onClick={() => setShowAddForm(!showAddForm)}
          >
            {showAddForm ? '취소' : '+ 종목 추가'}
          </button>
          {positions.length > 0 && (
            <button
              className="btn btn-outline"
              onClick={() => exportPortfolioCSV(positions)}
              title="CSV 내보내기"
            >
              {'\u2B07'} CSV
            </button>
          )}
          <div className={`card-value ${pnlPct >= 0 ? 'green' : 'red'}`} style={{ fontSize: '1.5rem' }}>
            {pnlPct >= 0 ? '+' : ''}{pnlPct}%
          </div>
          <HelpButton section="portfolio" onNavigate={onNavigate} />
        </div>
      </div>

      {/* Portfolio Group Selector */}
      <div className="card" style={{ marginBottom: '1rem', padding: '0.75rem 1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>
            포트폴리오 그룹:
          </span>
          {groups.map(g => (
            <div key={g.id} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <button
                className={`guide-tab ${g.id === activeGroupId ? 'active' : ''}`}
                onClick={() => switchGroup(g.id)}
                style={{ padding: '0.375rem 0.75rem', fontSize: '0.8rem' }}
              >
                {g.name}
                {g.is_default ? '' : ` (${g.id})`}
              </button>
              {!g.is_default && g.id === activeGroupId && (
                <button
                  className="btn btn-outline btn-sm"
                  onClick={() => handleDeleteGroup(g.id)}
                  style={{ color: 'var(--red)', borderColor: 'var(--red)', padding: '0.2rem 0.4rem', fontSize: '0.7rem' }}
                  title="그룹 삭제"
                >
                  {'\u2716'}
                </button>
              )}
            </div>
          ))}
          {showGroupForm ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
              <input
                type="text"
                placeholder="그룹 이름"
                value={newGroupName}
                onChange={e => setNewGroupName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleCreateGroup()}
                style={{
                  padding: '0.375rem 0.625rem', borderRadius: '0.375rem',
                  background: 'var(--bg-primary)', border: '1px solid var(--accent)',
                  color: 'var(--text-primary)', fontSize: '0.8rem', width: '140px',
                }}
                autoFocus
              />
              <button className="btn btn-primary btn-sm" onClick={handleCreateGroup} disabled={submitting}>
                {submitting ? '...' : '생성'}
              </button>
              <button className="btn btn-outline btn-sm" onClick={() => { setShowGroupForm(false); setNewGroupName('') }}>
                취소
              </button>
            </div>
          ) : (
            <button
              className="btn btn-outline btn-sm"
              onClick={() => setShowGroupForm(true)}
              style={{ fontSize: '0.8rem' }}
            >
              + 새 그룹
            </button>
          )}
        </div>
      </div>

      {/* 알림 메시지 */}
      {message && (
        <div className="card" style={{
          marginBottom: '1rem',
          borderColor: message.type === 'error' ? 'var(--red)' : 'var(--green)',
          padding: '0.75rem 1.25rem',
        }}>
          {message.type === 'error' ? '\u274C' : '\u2705'} {message.text}
        </div>
      )}

      {/* Summary Cards */}
      <div className="card-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
        <div className="card">
          <div className="card-label">보유 종목 수</div>
          <div className="card-value blue">{positions.length}</div>
        </div>
        <div className="card">
          <div className="card-label">총 투자금액</div>
          <div className="card-value blue">{formatKRW(totalInvested)}</div>
        </div>
        <div className="card">
          <div className="card-label">총 수익률</div>
          <div className={`card-value ${pnlPct >= 0 ? 'green' : 'red'}`}>
            {pnlPct >= 0 ? '+' : ''}{pnlPct}%
          </div>
        </div>
      </div>

      {/* 종목 추가 폼 */}
      {showAddForm && (
        <div className="card" style={{ marginBottom: '1.5rem', padding: '1.5rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>종목 추가 ({activeGroup?.name || '기본'})</h3>
          <form onSubmit={handleAdd}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem', marginBottom: '0.75rem' }}>
              {/* Watchlist 드롭다운 */}
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                  종목 선택 *
                </label>
                <select
                  value={formData.symbol ? `${formData.symbol}|${formData.market}` : ''}
                  onChange={handleWatchlistSelect}
                  style={inputStyle}
                  required
                >
                  <option value="">종목을 선택하세요</option>
                  {wlKR.length > 0 && (
                    <optgroup label="KR (한국)">
                      {wlKR.map(w => (
                        <option key={`${w.symbol}-KR`} value={`${w.symbol}|KR`}>
                          {w.symbol} - {w.name}
                        </option>
                      ))}
                    </optgroup>
                  )}
                  {wlUS.length > 0 && (
                    <optgroup label="US (미국)">
                      {wlUS.map(w => (
                        <option key={`${w.symbol}-US`} value={`${w.symbol}|US`}>
                          {w.symbol} - {w.name}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
              </div>
              {/* 마켓 (자동 세팅) */}
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                  마켓
                </label>
                <select
                  value={formData.market}
                  onChange={e => setFormData(prev => ({ ...prev, market: e.target.value }))}
                  style={inputStyle}
                >
                  <option value="KR">KR</option>
                  <option value="US">US</option>
                </select>
              </div>
              {/* 투자금액 */}
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                  투자금액 *
                </label>
                <input
                  type="number"
                  placeholder="5000000"
                  value={formData.position_size}
                  onChange={e => setFormData(prev => ({ ...prev, position_size: e.target.value }))}
                  style={inputStyle}
                  required
                />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.75rem', marginBottom: '1rem' }}>
              {/* 매입가 */}
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                  매입가 (미입력 시 자동)
                </label>
                <input
                  type="number"
                  placeholder="자동 조회"
                  value={formData.entry_price}
                  onChange={e => setFormData(prev => ({ ...prev, entry_price: e.target.value }))}
                  style={inputStyle}
                />
              </div>
              {/* 매입일 */}
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                  매입일
                </label>
                <input
                  type="date"
                  value={formData.entry_date}
                  onChange={e => setFormData(prev => ({ ...prev, entry_date: e.target.value }))}
                  style={inputStyle}
                />
              </div>
              {/* 섹터 */}
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.25rem' }}>
                  섹터
                </label>
                <input
                  type="text"
                  placeholder="Semiconductor"
                  value={formData.sector}
                  onChange={e => setFormData(prev => ({ ...prev, sector: e.target.value }))}
                  style={inputStyle}
                />
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? '저장 중...' : '저장'}
              </button>
              <button type="button" className="btn btn-outline" onClick={() => setShowAddForm(false)}>
                취소
              </button>
            </div>
          </form>
        </div>
      )}

      {/* P&L Bar Chart */}
      {pnlData.length > 0 && (
        <div className="chart-container">
          <h3>종목별 수익률 (%)</h3>
          <ResponsiveContainer width="100%" height={Math.max(200, pnlData.length * 32)}>
            <BarChart data={pnlData} layout="vertical" margin={{ left: 20 }}>
              <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }}
                tickFormatter={v => `${v > 0 ? '+' : ''}${v}%`} />
              <YAxis dataKey="name" type="category" width={100}
                tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155' }}
                formatter={v => [`${v.toFixed(2)}%`, 'P&L']}
              />
              <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
                {pnlData.map((d) => (
                  <Cell key={d.name} fill={d.pnl >= 0 ? '#22c55e' : '#ef4444'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Holdings Table */}
      <div className="table-container">
        <div className="table-header">
          <h3>보유 종목</h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>종목</th>
              <th>마켓</th>
              <th>매입가</th>
              <th>현재가</th>
              <th>수익률</th>
              <th>투자금액</th>
              <th>시나리오</th>
              <th>관리</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => {
              const sc = heldMap[p.symbol]
              const isEditing = editingSymbol === p.symbol
              return (
                <tr key={`${p.symbol}-${p.market}`}>
                  <td
                    className="symbol-link"
                    onClick={() => setSelectedSymbol({ symbol: p.symbol, market: p.market })}
                  >
                    <strong>{p.name || p.symbol}</strong>
                    <br />
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{p.symbol}</span>
                  </td>
                  <td>{p.market}</td>
                  <td>
                    {isEditing ? (
                      <input
                        type="number"
                        value={editData.entry_price}
                        onChange={e => setEditData(prev => ({ ...prev, entry_price: e.target.value }))}
                        style={{
                          width: '100px', padding: '0.25rem', borderRadius: '0.25rem',
                          background: 'var(--bg-primary)', border: '1px solid var(--accent)',
                          color: 'var(--text-primary)', fontSize: '0.8rem',
                        }}
                      />
                    ) : (
                      p.market === 'KR' ? `\u20A9${p.entry_price?.toLocaleString() || '-'}` : `$${p.entry_price?.toFixed(2) || '-'}`
                    )}
                  </td>
                  <td>{p.market === 'KR' ? `\u20A9${p.current_price?.toLocaleString() || '-'}` : `$${p.current_price?.toFixed(2) || '-'}`}</td>
                  <td>
                    <span style={{ color: (p.pnl_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                      {(p.pnl_pct || 0) >= 0 ? '+' : ''}{p.pnl_pct || 0}%
                    </span>
                  </td>
                  <td>
                    {isEditing ? (
                      <input
                        type="number"
                        value={editData.position_size}
                        onChange={e => setEditData(prev => ({ ...prev, position_size: e.target.value }))}
                        style={{
                          width: '100px', padding: '0.25rem', borderRadius: '0.25rem',
                          background: 'var(--bg-primary)', border: '1px solid var(--accent)',
                          color: 'var(--text-primary)', fontSize: '0.8rem',
                        }}
                      />
                    ) : (
                      formatKRW(p.position_size)
                    )}
                  </td>
                  <td style={{ maxWidth: 220, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    {sc?.scenario_rule || '-'}
                  </td>
                  <td>
                    {isEditing ? (
                      <div style={{ display: 'flex', gap: '0.25rem' }}>
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => handleSaveEdit(p)}
                          disabled={submitting}
                        >
                          {submitting ? '...' : '저장'}
                        </button>
                        <button
                          className="btn btn-outline btn-sm"
                          onClick={cancelEdit}
                        >
                          취소
                        </button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: '0.25rem' }}>
                        <button
                          className="btn btn-outline btn-sm"
                          onClick={() => startEdit(p)}
                          title="수정"
                        >
                          {'\u270F'}
                        </button>
                        <button
                          className="btn btn-outline btn-sm"
                          onClick={() => handleDelete(p.market, p.symbol)}
                          disabled={submitting}
                          title="삭제"
                          style={{ color: 'var(--red)', borderColor: 'var(--red)' }}
                        >
                          {'\u2716'}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              )
            })}
            {positions.length === 0 && (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  보유 종목이 없습니다. 위의 "+ 종목 추가" 버튼으로 추가하세요.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Entry Opportunities */}
      {Object.keys(entryMap).length > 0 && (
        <div className="table-container">
          <div className="table-header">
            <h3>{'\uD83C\uDD95'} 신규 진입 기회 (BUY 시그널, 미보유)</h3>
          </div>
          <table>
            <thead>
              <tr>
                <th>종목</th>
                <th>마켓</th>
                <th>현재가</th>
                <th>목표가</th>
                <th>손절가</th>
                <th>R:R</th>
                <th>시나리오</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(entryMap).map(([sym, sc]) => {
                let targets = {}
                try { targets = typeof sc.target_prices_json === 'string' ? JSON.parse(sc.target_prices_json) : (sc.target_prices_json || {}) } catch {}
                return (
                  <tr key={`entry-${sym}-${sc.market}`}>
                    <td><strong>{sym}</strong></td>
                    <td>{sc.market}</td>
                    <td>{sc.current_price?.toLocaleString()}</td>
                    <td style={{ color: 'var(--green)' }}>{targets.target_10pct?.toLocaleString() || '-'}</td>
                    <td style={{ color: 'var(--red)' }}>{targets.stop_loss?.toLocaleString() || '-'}</td>
                    <td>{(targets.target_10pct && targets.stop_loss && sc.current_price && sc.current_price > targets.stop_loss)
                      ? ((targets.target_10pct - sc.current_price) / (sc.current_price - targets.stop_loss)).toFixed(1)
                      : '-'}</td>
                    <td style={{ maxWidth: 250, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {sc.scenario_rule || '-'}
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
