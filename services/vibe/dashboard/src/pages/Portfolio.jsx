import { useState, useEffect, useCallback } from 'react'
import {
  getSummary, getPortfolio, getPortfolioScenarios, getWatchlist,
  addPosition, deletePosition, quickAddPositions, exportPortfolioCSV,
  getPortfolioGroups, createPortfolioGroup, deletePortfolioGroup,
  togglePositionHidden, exitPosition, batchExitStopLoss, getExitHistory,
  importFromImage, importFromText, confirmImport, refreshPrices,
  analyzeWithAI,
} from '../api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend
} from 'recharts'
import SymbolModal from '../components/SymbolModal'
import HelpButton from '../components/HelpButton'
import PageGuide from '../components/PageGuide'
import { useToast } from '../components/Toast'

export default function Portfolio({ onNavigate, refreshKey }) {
  const toast = useToast()
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
  const [formData, setFormData] = useState({
    symbol: '', market: 'KR', position_size: '', entry_price: '', entry_date: '', sector: ''
  })
  const [inputMode, setInputMode] = useState('amount') // 'amount' | 'shares'
  const [sharesCount, setSharesCount] = useState('')
  const [editInputMode, setEditInputMode] = useState('amount')
  const [editSharesCount, setEditSharesCount] = useState('')

  const [error, setError] = useState(null)
  const [selectedSymbol, setSelectedSymbol] = useState(null)
  const [showHidden, setShowHidden] = useState(false)
  const [exitHistory, setExitHistory] = useState([])
  const [showExitHistory, setShowExitHistory] = useState(false)
  const [exitHistoryLimit, setExitHistoryLimit] = useState(50)
  const [showImport, setShowImport] = useState(false)
  const [importPreview, setImportPreview] = useState(null)
  const [importLoading, setImportLoading] = useState(false)
  const [importText, setImportText] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const STOP_LOSS_PCT = -7.0

  // AI Portfolio Analysis state
  const [aiAnalyzing, setAiAnalyzing] = useState(false)
  const [aiHistory, setAiHistory] = useState([])
  const [aiQuestion, setAiQuestion] = useState('')
  const [showAiPanel, setShowAiPanel] = useState(false)

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
      .catch(err => { console.error('Groups load error:', err); toast.error('그룹 로드 실패: ' + err.message) })
  }, [activeGroupId])

  const loadData = useCallback((groupId, hidden) => {
    const gid = groupId || activeGroupId
    const inclHidden = hidden !== undefined ? hidden : showHidden
    setLoading(true)
    Promise.all([getSummary(gid), getPortfolio(null, gid, inclHidden), getPortfolioScenarios(), getWatchlist()])
      .then(([s, p, sc, wl]) => {
        setSummary(s)
        setPositions(p?.positions || [])
        setScenarios(sc)
        setWatchlist(wl || [])
        setError(null)
      })
      .catch(err => { console.error(err); setError(err.message); toast.error('데이터 로드 실패: ' + err.message) })
      .finally(() => setLoading(false))
  }, [activeGroupId, showHidden])

  useEffect(() => {
    loadGroups().then(() => loadData())
  }, [refreshKey]) // eslint-disable-line react-hooks/exhaustive-deps

  // Reload data when group changes
  const switchGroup = (gid) => {
    setActiveGroupId(gid)
    setInputMode('amount')
    setSharesCount('')
    setEditInputMode('amount')
    setEditSharesCount('')
    setEditingSymbol(null)
    setEditData({})
    setShowAddForm(false)
    setFormData({ symbol: '', market: 'KR', position_size: '', entry_price: '', entry_date: '', sector: '' })
    loadData(gid)
  }

  const showMessage = (text, type = 'success') => {
    // Toast-only notification (removed redundant inline card)
    if (type === 'error') toast.error(text)
    else toast.success(text)
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
    // Calculate position_size based on input mode
    let posSize
    if (inputMode === 'shares') {
      if (!sharesCount || !formData.entry_price) {
        showMessage('주식수 모드에서는 주식수와 매입가 모두 필요합니다', 'error')
        return
      }
      posSize = parseFloat(sharesCount) * parseFloat(formData.entry_price)
    } else {
      posSize = parseFloat(formData.position_size)
    }
    if (!formData.symbol || !posSize) return
    setSubmitting(true)
    try {
      if (formData.entry_price) {
        await addPosition({
          symbol: formData.symbol,
          market: formData.market,
          position_size: posSize,
          entry_price: parseFloat(formData.entry_price),
          entry_date: formData.entry_date || undefined,
          sector: formData.sector || undefined,
          portfolio_id: activeGroupId,
        })
      } else {
        await quickAddPositions([{
          symbol: formData.symbol,
          market: formData.market,
          position_size: posSize,
        }], activeGroupId)
      }
      showMessage(`${formData.symbol} 추가 완료`)
      setFormData({ symbol: '', market: 'KR', position_size: '', entry_price: '', entry_date: '', sector: '' })
      setSharesCount('')
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

  // ---- 종목 숨기기/보이기 토글 ----
  const handleToggleHidden = async (market, symbol) => {
    setSubmitting(true)
    try {
      const res = await togglePositionHidden(market, symbol, activeGroupId)
      showMessage(`${symbol} ${res.is_hidden ? '숨김' : '표시'} 처리 완료`)
      loadData()
    } catch (err) {
      showMessage(`처리 실패: ${err.message}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const handleToggleShowHidden = () => {
    const next = !showHidden
    setShowHidden(next)
    loadData(activeGroupId, next)
  }

  // ---- 현재가 갱신 ----
  const handleRefreshPrices = async () => {
    setRefreshing(true)
    try {
      const res = await refreshPrices('ALL')
      const totalRows = res.total_rows || 0
      toast.success(`현재가 갱신 완료 (${totalRows}건)`)
      loadData()
    } catch (err) {
      toast.error(`가격 갱신 실패: ${err.message}`)
    } finally {
      setRefreshing(false)
    }
  }

  // ---- AI 포트폴리오 분석 ----
  const AI_PRESETS = [
    { label: '종합 분석', q: '현재 포트폴리오의 종합적인 분석과 매수/매도 추천을 해주세요. 각 종목별로 현재 보유 유지, 추가 매수, 비중 축소 중 하나를 추천하고 근거를 설명해주세요.' },
    { label: '리스크 진단', q: '현재 포트폴리오의 리스크 요인을 분석해주세요. 섹터 집중도, 손실 종목, 상관관계 문제 등을 점검하고 리밸런싱 방안을 제시해주세요.' },
    { label: '매수 후보', q: '현재 시장 상황과 포트폴리오 구성을 고려했을 때, 워치리스트 중 신규 매수 우선순위 상위 3개 종목과 적정 매수 타이밍을 추천해주세요.' },
    { label: '손절/익절 판단', q: '현재 포트폴리오에서 손절 또는 익절이 필요한 종목이 있는지 분석해주세요. 각 종목의 기술적 지표, 수급, 매크로 상황을 종합적으로 판단해주세요.' },
  ]

  const handleAiAnalyze = async (question) => {
    const q = question || aiQuestion
    if (!q.trim()) return
    setAiAnalyzing(true)
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 90000) // 90s timeout
    try {
      const result = await analyzeWithAI(q, {
        include_portfolio: true,
        portfolio_id: activeGroupId,
        signal: controller.signal,
      })
      setAiHistory(prev => [...prev, { question: q, answer: result.analysis || result.content || JSON.stringify(result), timestamp: new Date().toLocaleTimeString('ko-KR') }])
      setAiQuestion('')
    } catch (err) {
      const msg = err.name === 'AbortError' ? 'AI 분석 시간 초과 (90초). 다시 시도해주세요.' : err.message
      setAiHistory(prev => [...prev, { question: q, answer: `Error: ${msg}`, timestamp: new Date().toLocaleTimeString('ko-KR'), isError: true }])
      toast.error(err.name === 'AbortError' ? msg : 'AI 분석 실패: ' + err.message)
    } finally {
      clearTimeout(timeout)
      setAiAnalyzing(false)
    }
  }

  // ---- 종목 퇴출 (손절/익절/수동) ----
  const handleExit = async (market, symbol, reason = 'manual') => {
    const label = reason === 'stop_loss' ? '손절' : reason === 'profit_taking' ? '익절' : '퇴출'
    if (!confirm(`${symbol} (${market}) 종목을 ${label} 처리하시겠습니까?`)) return
    setSubmitting(true)
    try {
      await exitPosition(market, symbol, reason, activeGroupId)
      showMessage(`${symbol} ${label} 완료`)
      loadData()
    } catch (err) {
      showMessage(`${label} 실패: ${err.message}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const handleBatchExit = async () => {
    const breached = positions.filter(p => p.pnl_pct != null && p.pnl_pct <= STOP_LOSS_PCT)
    if (breached.length === 0) { showMessage('손절 대상 종목 없음'); return }
    if (!confirm(`${breached.length}개 종목 일괄 손절 처리하시겠습니까?`)) return
    setSubmitting(true)
    try {
      const res = await batchExitStopLoss(activeGroupId)
      showMessage(`${res.exited_count}개 종목 손절 완료`)
      loadData()
    } catch (err) {
      showMessage(`일괄 손절 실패: ${err.message}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const loadExitHistory = async () => {
    try {
      const data = await getExitHistory(activeGroupId)
      setExitHistory(data?.exits || [])
      setShowExitHistory(true)
    } catch (err) {
      showMessage(`퇴출 이력 조회 실패: ${err.message}`, 'error')
    }
  }

  // ---- 이미지/텍스트 임포트 ----
  const handleImageImport = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImportLoading(true)
    try {
      const res = await importFromImage(file, activeGroupId)
      setImportPreview(res.positions || [])
      showMessage(`${res.positions?.length || 0}개 종목 감지됨`)
    } catch (err) {
      showMessage(`이미지 분석 실패: ${err.message}`, 'error')
    } finally {
      setImportLoading(false)
    }
  }

  const handleTextImport = async () => {
    if (!importText.trim()) return
    setImportLoading(true)
    try {
      const res = await importFromText(importText.trim(), 'KR')
      setImportPreview(res.positions || [])
      showMessage(`${res.positions?.length || 0}개 종목 파싱됨`)
    } catch (err) {
      showMessage(`텍스트 파싱 실패: ${err.message}`, 'error')
    } finally {
      setImportLoading(false)
    }
  }

  const handleConfirmImport = async () => {
    if (!importPreview?.length) return
    setSubmitting(true)
    try {
      const res = await confirmImport(importPreview, activeGroupId)
      showMessage(`${res.imported}개 종목 등록 완료`)
      setImportPreview(null)
      setShowImport(false)
      setImportText('')
      loadData()
    } catch (err) {
      showMessage(`등록 실패: ${err.message}`, 'error')
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
    setEditInputMode('amount')
    setEditSharesCount(p.entry_price > 0 && p.position_size != null ? Math.round(p.position_size / p.entry_price) : '')
  }

  const cancelEdit = () => {
    setEditingSymbol(null)
    setEditData({})
    setEditInputMode('amount')
    setEditSharesCount('')
  }

  const handleSaveEdit = async (p) => {
    let posSize
    if (editInputMode === 'shares') {
      const ep = editData.entry_price ? parseFloat(editData.entry_price) : p.entry_price
      if (!editSharesCount || !ep) {
        showMessage('주식수 모드에서는 주식수와 매입가 모두 필요합니다', 'error')
        return
      }
      posSize = parseFloat(editSharesCount) * ep
    } else {
      posSize = parseFloat(editData.position_size)
    }
    setSubmitting(true)
    try {
      await addPosition({
        symbol: p.symbol,
        market: p.market,
        position_size: posSize,
        entry_price: editData.entry_price ? parseFloat(editData.entry_price) : p.entry_price,
        entry_date: p.entry_date,
        sector: p.sector,
        portfolio_id: activeGroupId,
      })
      showMessage(`${p.symbol} 수정 완료`)
      setEditingSymbol(null)
      setEditData({})
      setEditSharesCount('')
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

  if (loading) return <div className="loading"><span className="spinner" /> 로딩 중...</div>
  if (error) return <div className="loading" style={{ color: 'var(--red)' }}>오류: {error}</div>

  const pnlPct = parseFloat((summary?.portfolio?.total_pnl_pct ?? 0).toFixed(2))
  const activeGroup = groups.find(g => g.id === activeGroupId)

  // P&L chart data (null pnl_pct 제외 — 현재가 없는 종목은 차트에서 제외)
  const pnlData = positions
    .filter(p => p.pnl_pct != null)
    .map(p => ({
      name: p.name || p.symbol,
      pnl: p.pnl_pct,
      market: p.market,
    })).sort((a, b) => b.pnl - a.pnl)
  const noPriceCount = positions.filter(p => p.pnl_pct == null).length

  // Sector exposure data for pie chart
  const SECTOR_COLORS = ['#3b82f6', '#22c55e', '#eab308', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#06b6d4']
  const sectorMap = {}
  positions.forEach(p => {
    const sector = p.sector || '미분류'
    const value = p.position_size || 0
    sectorMap[sector] = (sectorMap[sector] || 0) + value
  })
  const sectorData = Object.entries(sectorMap)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value)
  const totalValue = sectorData.reduce((s, d) => s + d.value, 0)

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
          <button
            className={`btn ${showImport ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => { setShowImport(!showImport); setImportPreview(null); setImportText('') }}
          >
            {showImport ? '취소' : '📷 임포트'}
          </button>
          <button
            className="btn btn-outline"
            onClick={handleRefreshPrices}
            disabled={refreshing}
            title="pykrx/yfinance에서 최신 현재가를 가져옵니다"
          >
            {refreshing ? '\u23F3 갱신 중...' : '🔄 현재가 갱신'}
          </button>
          {positions.length > 0 && (
            <button
              className="btn btn-outline"
              onClick={() => { exportPortfolioCSV(positions); toast.success(`${positions.length}개 종목 CSV 다운로드 완료`) }}
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

      <PageGuide
        pageId="portfolio"
        title="이 페이지에서 확인할 것"
        steps={[
          '전체 P&L → 수익률 추이 확인',
          '빨간색 종목 → 손절선 도달 여부 점검',
          '시나리오 탭 → 급락 시 예상 손실 시뮬레이션',
          '종목 추가/임포트 → 스크린샷·텍스트로 빠르게 등록',
        ]}
        color="#a855f7"
      />

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

      {/* 임포트 패널 */}
      {showImport && (
        <div className="card" style={{ marginBottom: '1.5rem', padding: '1.5rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>📷 포트폴리오 임포트</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            {/* 이미지 업로드 */}
            <div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                증권사 앱 스크린샷을 업로드하면 AI가 종목 정보를 추출합니다.
              </p>
              <label style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: '2px dashed var(--border)', borderRadius: '0.5rem',
                padding: '2rem', cursor: 'pointer', color: 'var(--text-muted)',
                transition: 'border-color 0.2s',
              }}>
                <input type="file" accept="image/*" onChange={handleImageImport} style={{ display: 'none' }} />
                {importLoading ? '⏳ AI 분석 중...' : '📷 이미지 선택 또는 드래그'}
              </label>
            </div>
            {/* 텍스트 붙여넣기 */}
            <div>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                종목코드, 종목명, 수량, 단가, 금액을 탭/쉼표로 구분하여 붙여넣기
              </p>
              <textarea
                value={importText}
                onChange={e => setImportText(e.target.value)}
                placeholder={'005930\t삼성전자\t100\t56000\t5600000\n000660\tSK하이닉스\t50\t180000\t9000000'}
                rows={5}
                style={{
                  width: '100%', padding: '0.5rem', borderRadius: '0.25rem',
                  background: 'var(--bg-primary)', border: '1px solid var(--border)',
                  color: 'var(--text-primary)', fontSize: '0.8rem', fontFamily: 'monospace',
                  resize: 'vertical',
                }}
              />
              <button className="btn btn-outline btn-sm" onClick={handleTextImport} disabled={importLoading} style={{ marginTop: '0.5rem' }}>
                {'\u27A4'} 텍스트 파싱
              </button>
            </div>
          </div>

          {/* 미리보기 테이블 */}
          {importPreview && importPreview.length > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <h4>{importPreview.length}개 종목 감지됨</h4>
                <button className="btn btn-primary btn-sm" onClick={handleConfirmImport} disabled={submitting}>
                  {submitting ? '등록 중...' : `\u2705 ${importPreview.length}개 종목 등록`}
                </button>
              </div>
              <table>
                <thead>
                  <tr><th>종목코드</th><th>종목명</th><th>마켓</th><th>수량</th><th>매입단가</th><th>매입금액</th></tr>
                </thead>
                <tbody>
                  {importPreview.map((p, i) => (
                    <tr key={i}>
                      <td style={{ fontFamily: 'monospace' }}>{p.symbol}</td>
                      <td>{p.name || '-'}</td>
                      <td>{p.market}</td>
                      <td>{p.quantity?.toLocaleString() || '-'}</td>
                      <td>{p.entry_price?.toLocaleString() || '-'}</td>
                      <td>{p.position_size?.toLocaleString() || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

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
              {/* 투자금액 / 주식수 */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                  <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {inputMode === 'amount' ? '투자금액' : '주식수'} *
                  </label>
                  <button
                    type="button"
                    onClick={() => setInputMode(inputMode === 'amount' ? 'shares' : 'amount')}
                    style={{
                      fontSize: '0.65rem', padding: '0.1rem 0.4rem', borderRadius: '0.25rem',
                      background: 'var(--bg-primary)', border: '1px solid var(--border)',
                      color: 'var(--accent)', cursor: 'pointer',
                    }}
                  >
                    {inputMode === 'amount' ? '주식수로 전환' : '금액으로 전환'}
                  </button>
                </div>
                {inputMode === 'amount' ? (
                  <input
                    type="number"
                    placeholder="5000000"
                    value={formData.position_size}
                    onChange={e => setFormData(prev => ({ ...prev, position_size: e.target.value }))}
                    style={inputStyle}
                    required
                  />
                ) : (
                  <input
                    type="number"
                    placeholder="100"
                    value={sharesCount}
                    onChange={e => setSharesCount(e.target.value)}
                    style={inputStyle}
                    required
                  />
                )}
                {inputMode === 'shares' && sharesCount && formData.entry_price && (
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    = {formatKRW(parseFloat(sharesCount) * parseFloat(formData.entry_price))}
                  </div>
                )}
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
      {positions.length > 0 && (
        <div className="chart-container">
          <h3>종목별 수익률 (%)</h3>
          {pnlData.length > 0 ? (
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
          ) : (
            <div style={{ height: 120, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              현재가 데이터가 없습니다. 파이프라인을 실행하면 수익률이 계산됩니다.
            </div>
          )}
          {noPriceCount > 0 && pnlData.length > 0 && (
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
              * {noPriceCount}개 종목은 현재가 데이터 없음 (파이프라인 실행 필요)
            </p>
          )}
        </div>
      )}

      {/* Sector Exposure + Charts Grid */}
      {positions.length > 0 && sectorData.length > 1 && (
        <div className="chart-container">
          <h3>섹터별 투자 비중</h3>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={sectorData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={90}
                  paddingAngle={2}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={{ stroke: '#64748b', strokeWidth: 1 }}
                  style={{ fontSize: '0.7rem' }}
                >
                  {sectorData.map((d, i) => (
                    <Cell key={d.name} fill={SECTOR_COLORS[i % SECTOR_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', fontSize: '0.8rem' }}
                  formatter={(v) => [totalValue > 0 ? `${(v / totalValue * 100).toFixed(1)}% (${v.toLocaleString()}원)` : v.toLocaleString(), '비중']}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* AI Portfolio Analysis */}
      {positions.length > 0 && (
        <div className="table-container" style={{ marginBottom: '1.5rem' }}>
          <div className="table-header">
            <h3>{'\uD83E\uDD16'} AI 포트폴리오 분석</h3>
            <button
              className={`btn btn-sm ${showAiPanel ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setShowAiPanel(!showAiPanel)}
            >
              {showAiPanel ? '접기' : '펼치기'}
            </button>
          </div>
          {showAiPanel && (
            <div style={{ padding: '1rem 1.25rem' }}>
              {/* Preset buttons */}
              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
                {AI_PRESETS.map((p, i) => (
                  <button
                    key={i}
                    className="btn btn-outline btn-sm"
                    onClick={() => handleAiAnalyze(p.q)}
                    disabled={aiAnalyzing}
                    style={{ fontSize: '0.75rem' }}
                  >
                    {p.label}
                  </button>
                ))}
              </div>

              {/* Custom question input */}
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <input
                  type="text"
                  value={aiQuestion}
                  onChange={e => setAiQuestion(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !aiAnalyzing && handleAiAnalyze()}
                  placeholder="포트폴리오에 대해 질문하세요... (예: SOXL 비중 줄여야 할까?)"
                  style={{
                    flex: 1, padding: '0.5rem 0.75rem', borderRadius: '0.375rem',
                    background: 'var(--bg-primary)', border: '1px solid var(--border)',
                    color: 'var(--text-primary)', fontSize: '0.85rem',
                  }}
                />
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() => handleAiAnalyze()}
                  disabled={aiAnalyzing || !aiQuestion.trim()}
                >
                  {aiAnalyzing ? '\u23F3' : '\u27A4'}
                </button>
              </div>

              {/* Conversation history */}
              {aiHistory.length > 0 && (
                <div style={{ maxHeight: '500px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {aiHistory.map((h, i) => (
                    <div key={i}>
                      {/* Question */}
                      <div style={{
                        display: 'flex', justifyContent: 'flex-end', marginBottom: '0.25rem',
                      }}>
                        <div style={{
                          maxWidth: '80%', padding: '0.5rem 0.75rem', borderRadius: '0.75rem 0.75rem 0 0.75rem',
                          background: 'rgba(59,130,246,0.15)', fontSize: '0.8rem', color: 'var(--text-primary)',
                        }}>
                          {h.question}
                        </div>
                      </div>
                      {/* Answer */}
                      <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                        <div style={{
                          maxWidth: '90%', padding: '0.75rem', borderRadius: '0.75rem 0.75rem 0.75rem 0',
                          background: h.isError ? 'rgba(239,68,68,0.1)' : 'var(--bg-primary)',
                          border: '1px solid var(--border)', fontSize: '0.8rem',
                          color: h.isError ? 'var(--red)' : 'var(--text-primary)',
                          whiteSpace: 'pre-wrap', lineHeight: 1.6,
                        }}>
                          {h.answer}
                          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '0.25rem', textAlign: 'right' }}>
                            {h.timestamp}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                  {aiAnalyzing && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem', color: 'var(--text-muted)' }}>
                      <span className="spinner" /> AI가 포트폴리오를 분석하고 있습니다...
                    </div>
                  )}
                </div>
              )}

              {aiHistory.length > 1 && (
                <div style={{ textAlign: 'right', marginTop: '0.5rem' }}>
                  <button
                    className="btn btn-outline btn-sm"
                    onClick={() => setAiHistory([])}
                    style={{ fontSize: '0.7rem' }}
                  >
                    대화 초기화
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Holdings Table */}
      <div className="table-container">
        <div className="table-header">
          <h3>보유 종목</h3>
          <button
            className={`btn btn-sm ${showHidden ? 'btn-primary' : 'btn-outline'}`}
            onClick={handleToggleShowHidden}
            style={{ fontSize: '0.75rem' }}
          >
            {showHidden ? '\uD83D\uDC41 숨긴 종목 포함' : '\uD83D\uDC41\u200D\uD83D\uDDE8 숨긴 종목 보기'}
          </button>
          {positions.some(p => p.pnl_pct != null && p.pnl_pct <= STOP_LOSS_PCT) && (
            <button
              className="btn btn-sm"
              onClick={handleBatchExit}
              disabled={submitting}
              style={{ fontSize: '0.75rem', backgroundColor: 'var(--red)', color: '#fff', border: 'none' }}
            >
              {'🚨'} 일괄 손절 ({positions.filter(p => p.pnl_pct != null && p.pnl_pct <= STOP_LOSS_PCT).length}건)
            </button>
          )}
          <button
            className="btn btn-outline btn-sm"
            onClick={loadExitHistory}
            style={{ fontSize: '0.75rem' }}
          >
            {'📋'} 퇴출 이력
          </button>
        </div>
        <table>
          <thead>
            <tr>
              <th>종목</th>
              <th className="hide-on-mobile">마켓</th>
              <th>매입가</th>
              <th>현재가</th>
              <th>수익률</th>
              <th className="hide-on-tablet">투자금액</th>
              <th className="hide-on-tablet">시나리오</th>
              <th>관리</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => {
              const sc = heldMap[p.symbol]
              const isEditing = editingSymbol === p.symbol
              const hasPrice = p.current_price != null && p.entry_price > 0
              const pnl = p.pnl_pct ?? null
              const isBreached = hasPrice && pnl != null && pnl <= STOP_LOSS_PCT
              const isApproaching = hasPrice && pnl != null && !isBreached && pnl <= STOP_LOSS_PCT + 2
              const rowBg = isBreached ? 'rgba(239,68,68,0.12)'
                : isApproaching ? 'rgba(234,179,8,0.08)' : 'transparent'
              return (
                <tr key={`${p.symbol}-${p.market}`} style={{
                  ...(p.is_hidden ? { opacity: 0.45 } : {}),
                  backgroundColor: rowBg,
                }}>
                  <td
                    className="symbol-link"
                    onClick={() => setSelectedSymbol({ symbol: p.symbol, market: p.market })}
                  >
                    <strong>{p.name || p.symbol}</strong>
                    {isBreached && <span style={{ fontSize: '0.6rem', color: 'var(--red)', marginLeft: '0.3rem' }}>손절</span>}
                    {isApproaching && <span style={{ fontSize: '0.6rem', color: '#eab308', marginLeft: '0.3rem' }}>주의</span>}
                    <br />
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{p.symbol}</span>
                  </td>
                  <td className="hide-on-mobile">{p.market}</td>
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
                  <td>
                    {p.current_price != null ? (
                      <div>
                        {p.market === 'KR' ? `\u20A9${Math.round(p.current_price).toLocaleString()}` : `$${p.current_price.toFixed(2)}`}
                        {p.price_date && (() => {
                          const daysDiff = (Date.now() - new Date(p.price_date).getTime()) / (1000*60*60*24)
                          // Business-day aware: weekends add 2 extra days tolerance
                          const dow = new Date().getDay() // 0=Sun, 6=Sat
                          const tolerance = dow === 0 ? 4 : dow === 1 ? 5 : dow === 6 ? 4 : 3
                          const isStale = daysDiff > tolerance
                          return (
                            <div style={{ fontSize: '0.6rem', color: isStale ? '#f59e0b' : 'var(--text-muted)' }}
                                 title={isStale ? `${Math.floor(daysDiff)}일 전 데이터 — 현재가 갱신 필요` : ''}>
                              {isStale ? '\u26A0 ' : ''}{p.price_date}
                            </div>
                          )
                        })()}
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}
                            title="파이프라인 실행 후 현재가가 업데이트됩니다">
                        -
                      </span>
                    )}
                  </td>
                  <td>
                    {pnl != null ? (
                      <span style={{ color: pnl >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                        {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}
                            title={!p.entry_price ? '매입가 미입력' : '현재가 데이터 없음 — 파이프라인 실행 필요'}>
                        -
                      </span>
                    )}
                  </td>
                  <td className="hide-on-tablet">
                    {isEditing ? (
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', marginBottom: '0.2rem' }}>
                          <button
                            type="button"
                            onClick={() => setEditInputMode(editInputMode === 'amount' ? 'shares' : 'amount')}
                            style={{
                              fontSize: '0.6rem', padding: '0.1rem 0.3rem', borderRadius: '0.2rem',
                              background: 'var(--bg-primary)', border: '1px solid var(--border)',
                              color: 'var(--accent)', cursor: 'pointer', whiteSpace: 'nowrap',
                            }}
                          >
                            {editInputMode === 'amount' ? '주식수' : '금액'}
                          </button>
                        </div>
                        {editInputMode === 'amount' ? (
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
                          <div>
                            <input
                              type="number"
                              placeholder="주식수"
                              value={editSharesCount}
                              onChange={e => setEditSharesCount(e.target.value)}
                              style={{
                                width: '80px', padding: '0.25rem', borderRadius: '0.25rem',
                                background: 'var(--bg-primary)', border: '1px solid var(--accent)',
                                color: 'var(--text-primary)', fontSize: '0.8rem',
                              }}
                            />
                            {editSharesCount && (editData.entry_price || p.entry_price) && (
                              <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                                = {formatKRW(parseFloat(editSharesCount) * parseFloat(editData.entry_price || p.entry_price))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ) : (
                      formatKRW(p.position_size)
                    )}
                  </td>
                  <td className="hide-on-tablet" style={{ maxWidth: 220, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
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
                          onClick={() => handleToggleHidden(p.market, p.symbol)}
                          disabled={submitting}
                          title={p.is_hidden ? '종목 표시' : '종목 숨기기'}
                          style={{ opacity: p.is_hidden ? 0.5 : 1 }}
                        >
                          {p.is_hidden ? '\uD83D\uDC41' : '\uD83D\uDE48'}
                        </button>
                        <button
                          className="btn btn-outline btn-sm"
                          onClick={() => handleExit(p.market, p.symbol, pnl <= STOP_LOSS_PCT ? 'stop_loss' : pnl >= 10 ? 'profit_taking' : 'manual')}
                          disabled={submitting}
                          title={pnl <= STOP_LOSS_PCT ? '손절 퇴출' : pnl >= 10 ? '익절 퇴출' : '퇴출'}
                          style={{ color: pnl <= STOP_LOSS_PCT ? 'var(--red)' : '#eab308' }}
                        >
                          {'\u21AA'}
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

      {/* Exit History */}
      {showExitHistory && (
        <div className="table-container">
          <div className="table-header">
            <h3>{'📋'} 퇴출 이력</h3>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <span className="card-sub">
                {exitHistory.length > exitHistoryLimit
                  ? `${exitHistoryLimit} / ${exitHistory.length}건`
                  : `${exitHistory.length}건`}
              </span>
              <button className="btn btn-outline btn-sm" onClick={() => { setShowExitHistory(false); setExitHistoryLimit(50) }}>닫기</button>
            </div>
          </div>
          {exitHistory.length === 0 ? (
            <p style={{ padding: '1rem', color: 'var(--text-muted)', textAlign: 'center' }}>퇴출 이력이 없습니다.</p>
          ) : (
            <>
            <table>
              <thead>
                <tr>
                  <th>종목</th>
                  <th>마켓</th>
                  <th>매입가</th>
                  <th>퇴출가</th>
                  <th>수익률</th>
                  <th>사유</th>
                  <th>퇴출일</th>
                </tr>
              </thead>
              <tbody>
                {exitHistory.slice(0, exitHistoryLimit).map((e, i) => (
                  <tr key={e.id || i}>
                    <td><strong>{e.name || e.symbol}</strong></td>
                    <td>{e.market}</td>
                    <td>{e.market === 'KR' ? `\u20A9${e.entry_price?.toLocaleString() || '-'}` : `$${e.entry_price?.toFixed(2) || '-'}`}</td>
                    <td>{e.market === 'KR' ? `\u20A9${e.exit_price?.toLocaleString() || '-'}` : `$${e.exit_price?.toFixed(2) || '-'}`}</td>
                    <td>
                      <span style={{ color: (e.pnl_pct ?? 0) >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                        {(e.pnl_pct ?? 0) >= 0 ? '+' : ''}{(e.pnl_pct ?? 0).toFixed(2)}%
                      </span>
                    </td>
                    <td>
                      <span className={`badge badge-${e.exit_reason === 'stop_loss' ? 'SELL' : e.exit_reason === 'profit_taking' ? 'BUY' : 'HOLD'}`}>
                        {e.exit_reason === 'stop_loss' ? '손절' : e.exit_reason === 'profit_taking' ? '익절' : '수동'}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.75rem' }}>{e.exit_date || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {exitHistory.length > exitHistoryLimit && (
              <div style={{ textAlign: 'center', padding: '1rem' }}>
                <button
                  className="btn btn-outline"
                  onClick={() => setExitHistoryLimit(prev => prev + 50)}
                >
                  더 보기 ({exitHistory.length - exitHistoryLimit}건 남음)
                </button>
              </div>
            )}
            </>
          )}
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
