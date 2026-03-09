const BASE = ''

// ── User-Friendly Error Messages ──

const STATUS_MESSAGES = {
  400: '잘못된 요청입니다.',
  401: '인증이 필요합니다. 다시 로그인해주세요.',
  403: '접근 권한이 없습니다.',
  404: '요청한 데이터를 찾을 수 없습니다.',
  413: '파일 크기가 너무 큽니다.',
  422: '입력 데이터 형식이 올바르지 않습니다.',
  429: '요청이 너무 많습니다. 잠시 후 다시 시도해주세요.',
  500: '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
  502: '서버에 연결할 수 없습니다.',
  503: '서비스가 일시적으로 중단되었습니다.',
}

function friendlyError(status, serverDetail) {
  // For 4xx client errors, the server detail is usually meaningful (e.g. "Position not found")
  // For 5xx server errors, use a generic user-facing message
  if (status >= 500) {
    return STATUS_MESSAGES[status] || `서버 오류 (${status})`
  }
  // For client errors, prefer the server detail if it exists and is concise
  if (serverDetail && serverDetail.length < 200) {
    return serverDetail
  }
  return STATUS_MESSAGES[status] || `요청 실패 (${status})`
}

// ── Auth Token Management ──

function getAuthToken() {
  return localStorage.getItem('vibe_auth_token') || ''
}

function getApiKey() {
  // Priority: localStorage > build-time env
  return localStorage.getItem('vibe_api_key') || import.meta.env.VITE_API_KEY || ''
}

export function setApiKey(key) {
  if (key) {
    localStorage.setItem('vibe_api_key', key)
  } else {
    localStorage.removeItem('vibe_api_key')
  }
}

export function getStoredApiKey() {
  return getApiKey()
}

export function logout() {
  localStorage.removeItem('vibe_auth_token')
  localStorage.removeItem('vibe_api_key')
  window.location.reload()
}

function authHeaders() {
  const headers = { 'Content-Type': 'application/json' }
  // Priority: Bearer token > API key
  const token = getAuthToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  } else {
    const key = getApiKey()
    if (key) headers['X-API-Key'] = key
  }
  return headers
}

async function fetchJSON(path) {
  const hdrs = authHeaders()
  let res
  try {
    res = await fetch(`${BASE}${path}`, { headers: hdrs })
  } catch {
    throw new Error('서버에 연결할 수 없습니다. 네트워크를 확인해주세요.')
  }
  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = body?.detail || body?.message || ''
    } catch { /* non-JSON error response */ }
    throw new Error(friendlyError(res.status, detail))
  }
  return res.json()
}

// ── Auth API ──

export async function authStatus() {
  const token = getAuthToken()
  const opts = token ? { headers: { 'Authorization': `Bearer ${token}` } } : {}
  const res = await fetch(`${BASE}/auth/status`, opts)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(friendlyError(res.status, body?.detail))
  }
  return res.json()
}

export async function authLogin(username, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(friendlyError(res.status, body?.detail))
  }
  return res.json()
}

export async function authRegister(username, password) {
  const res = await fetch(`${BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(friendlyError(res.status, body?.detail))
  }
  return res.json()
}

export async function authChangePassword(currentPassword, newPassword) {
  const res = await fetch(`${BASE}/auth/change-password`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(friendlyError(res.status, body?.detail))
  }
  return res.json()
}

export async function getSummary(portfolioId = 1) {
  return fetchJSON(`/dashboard/summary?portfolio_id=${portfolioId}`)
}

export async function getSignals(market = null) {
  const q = market ? `?market=${market}` : ''
  return fetchJSON(`/signals${q}`)
}

export async function getSignalHistory(market = null, days = 30, symbol = null) {
  let q = `?days=${days}`
  if (market) q += `&market=${market}`
  if (symbol) q += `&symbol=${encodeURIComponent(symbol)}`
  return fetchJSON(`/dashboard/signals/history${q}`)
}

export async function getSignalPerformance(market = null) {
  const q = market ? `?market=${market}` : ''
  return fetchJSON(`/signals/performance${q}`)
}

export async function getPortfolio(market = null, portfolioId = 1, includeHidden = false) {
  let q = `?portfolio_id=${portfolioId}`
  if (market) q += `&market=${market}`
  if (includeHidden) q += '&include_hidden=true'
  return fetchJSON(`/portfolio${q}`)
}

export async function togglePositionHidden(market, symbol, portfolioId = 1) {
  const res = await fetch(`${BASE}/portfolio/position/${market}/${symbol}/hide?portfolio_id=${portfolioId}`, {
    method: 'PATCH',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function getPortfolioScenarios(market = null) {
  const q = market ? `?market=${market}` : ''
  return fetchJSON(`/portfolio/scenarios${q}`)
}

// ── Portfolio Groups ──

export async function getPortfolioGroups() {
  return fetchJSON('/portfolio/groups')
}

export async function createPortfolioGroup(name, description = null) {
  const res = await fetch(`${BASE}/portfolio/groups`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ name, description }),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function updatePortfolioGroup(groupId, name, description = null) {
  const res = await fetch(`${BASE}/portfolio/groups/${groupId}`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify({ name, description }),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function deletePortfolioGroup(groupId) {
  const res = await fetch(`${BASE}/portfolio/groups/${groupId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

// ── Portfolio Import ──

export async function importFromImage(file, portfolioId = 1) {
  const formData = new FormData()
  formData.append('file', file)
  // For FormData, do NOT set Content-Type (browser sets it with boundary).
  // But we still need auth headers (Bearer token or API key).
  const token = getAuthToken()
  const key = getApiKey()
  const headers = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  } else if (key) {
    headers['X-API-Key'] = key
  }
  const res = await fetch(`${BASE}/portfolio/import/image?portfolio_id=${portfolioId}`, {
    method: 'POST', headers, body: formData,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(friendlyError(res.status, body?.detail))
  }
  return res.json()
}

export async function importFromText(text, market = 'KR') {
  const res = await fetch(`${BASE}/portfolio/import/text`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify({ text, market }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(friendlyError(res.status, body?.detail))
  }
  return res.json()
}

export async function confirmImport(positions, portfolioId = 1) {
  const res = await fetch(`${BASE}/portfolio/import/confirm`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify({ positions, portfolio_id: portfolioId }),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

// ── Position Exits ──

export async function exitPosition(market, symbol, exitReason = 'manual', portfolioId = 1) {
  const res = await fetch(`${BASE}/portfolio/position/${market}/${symbol}/exit?exit_reason=${exitReason}&portfolio_id=${portfolioId}`, {
    method: 'POST', headers: authHeaders(),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function batchExitStopLoss(portfolioId = 1) {
  const res = await fetch(`${BASE}/portfolio/batch-exit?portfolio_id=${portfolioId}`, {
    method: 'POST', headers: authHeaders(),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function getExitHistory(portfolioId = 1, limit = 50) {
  return fetchJSON(`/portfolio/exits?portfolio_id=${portfolioId}&limit=${limit}`)
}

// ── General ──

export async function getHealth() {
  return fetchJSON('/health')
}

export async function getPipelineRuns() {
  return fetchJSON('/pipeline/runs')
}

export async function getMarketBriefings(limit = 10) {
  return fetchJSON(`/briefing?limit=${limit}`)
}

export async function getLatestBriefing() {
  return fetchJSON('/briefing/latest')
}

export async function generateBriefing() {
  const res = await fetch(`${BASE}/briefing/generate`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function analyzeWithAI(question = null, options = {}) {
  const body = {}
  if (question) body.question = question
  if (options.markets) body.markets = options.markets
  if (options.include_portfolio != null) body.include_portfolio = options.include_portfolio
  if (options.portfolio_id) body.portfolio_id = options.portfolio_id
  const res = await fetch(`${BASE}/briefing/analyze`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
    signal: options.signal,
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function getPriceChart(symbol, market = 'KR', days = 60) {
  return fetchJSON(`/dashboard/prices/${encodeURIComponent(symbol)}?market=${market}&days=${days}`)
}

export async function getLatestSentiment() {
  return fetchJSON('/sentiment/latest')
}

export async function getSentimentHistory(days = 7) {
  return fetchJSON(`/sentiment?days=${days}`)
}

export async function getBacktestResults(limit = 20) {
  return fetchJSON(`/backtest/results?limit=${limit}`)
}

export async function getBacktestDetail(backtestId) {
  return fetchJSON(`/backtest/results/${backtestId}`)
}

export async function triggerBacktest(data) {
  const res = await fetch(`${BASE}/backtest/run`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function getAlertConfig() {
  return fetchJSON('/alerts/config')
}

export async function updateAlertConfig(updates) {
  const res = await fetch(`${BASE}/alerts/config`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(updates),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function getAlertHistory(limit = 50) {
  return fetchJSON(`/alerts/history?limit=${limit}`)
}

export async function getDataStatus() {
  return fetchJSON('/dashboard/data-status')
}

export async function getLLMSettings() {
  return fetchJSON('/settings/llm')
}

export async function updateLLMSettings(updates) {
  const res = await fetch(`${BASE}/settings/llm`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(updates),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function getMonthlyReports(limit = 12) {
  return fetchJSON(`/dashboard/reports/monthly?limit=${limit}`)
}

export async function generateMonthlyReport(reportMonth = null) {
  const params = reportMonth ? `?report_month=${encodeURIComponent(reportMonth)}` : ''
  const res = await fetch(`${BASE}/dashboard/reports/monthly/generate${params}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function triggerPipeline(market = 'ALL') {
  const res = await fetch(`${BASE}/pipeline/run`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ market }),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function refreshPrices(market = 'ALL') {
  const res = await fetch(`${BASE}/data/prices/refresh?market=${market}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

// ── Screening ──

export async function runScreeningScan(market = 'KR', daysBack = 5) {
  const res = await fetch(`${BASE}/screening/scan?market=${market}&days_back=${daysBack}`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function getScreeningCandidates(market = 'KR', status = null) {
  let q = `?market=${market}`
  if (status) q += `&status=${status}`
  return fetchJSON(`/screening/candidates${q}`)
}

export async function updateScreeningStatus(candidateId, status) {
  const res = await fetch(`${BASE}/screening/candidates/${candidateId}/status`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ status }),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function getRuntimeSettings() {
  return fetchJSON('/settings/runtime')
}

export async function updateRuntimeSetting(key, value) {
  const res = await fetch(`${BASE}/settings/runtime`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ [key]: String(value) }),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

// ── Risk ──

export async function getRiskPortfolio(market = null) {
  const q = market ? `?market=${market}` : ''
  return fetchJSON(`/risk/portfolio${q}`)
}

export async function getRiskEvents(market = 'KR', daysAhead = 30) {
  return fetchJSON(`/risk/events?market=${market}&days_ahead=${daysAhead}`)
}

export async function seedRiskEvents() {
  const res = await fetch(`${BASE}/risk/events/seed`, {
    method: 'POST',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function getRiskSectors() {
  return fetchJSON('/risk/sectors')
}

// ── Macro Intelligence ──

export async function getMacroRegime() {
  return fetchJSON('/macro-intel/regime')
}

export async function getStagflation() {
  return fetchJSON('/macro-intel/stagflation')
}

export async function getCrossMarket() {
  return fetchJSON('/macro-intel/cross-market')
}

export async function getMacroTrends(days = 30) {
  return fetchJSON(`/macro-intel/macro-trends?days=${days}`)
}

export async function getSectorFundFlow(days = 5) {
  return fetchJSON(`/macro-intel/fund-flow/sectors?days=${days}`)
}

export async function getCrossMarketFlow(days = 30) {
  return fetchJSON(`/macro-intel/fund-flow/cross-market?days=${days}`)
}

export async function getSectorRotation() {
  return fetchJSON('/macro-intel/sector-rotation')
}

export async function getThemeRanking() {
  return fetchJSON('/macro-intel/theme-ranking')
}

export async function getMarketSeason() {
  return fetchJSON('/macro-intel/market-season')
}

export async function getInvestmentClock() {
  return fetchJSON('/macro-intel/investment-clock')
}

export async function getYieldPhase() {
  return fetchJSON('/macro-intel/yield-phase')
}

export async function getStrategyMatch() {
  return fetchJSON('/macro-intel/strategy-match')
}

export async function getUnifiedRiskScore() {
  return fetchJSON('/macro-intel/risk-score')
}

export async function getSectorMacroImpact() {
  return fetchJSON('/macro-intel/sector-impact')
}

export async function getFearGauge() {
  return fetchJSON('/macro-intel/fear-gauge')
}

export async function getCapitulationScan(market = 'KR') {
  return fetchJSON(`/macro-intel/capitulation-scan?market=${market}`)
}

export async function getCrisisHedge(days = 20) {
  return fetchJSON(`/macro-intel/crisis-hedge?days=${days}`)
}

export async function getEntryScenarios() {
  return fetchJSON('/macro-intel/entry-scenarios')
}

// ── Guru Insights ──

export async function getGuruInsights() {
  return fetchJSON('/guru/insights')
}

export async function getGuruDetail(guruId) {
  return fetchJSON(`/guru/${guruId}`)
}

export async function getGuruLLMAnalysis(guruId, opts = {}) {
  const res = await fetch(`${BASE}/guru/${guruId}/analyze`, {
    method: 'POST',
    headers: authHeaders(),
    signal: opts.signal,
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

// ── Action Plan ──

export async function getActionPlan() {
  return fetchJSON('/action-plan/daily')
}

// ── Strategy Settings ──

export async function getStrategySettings() {
  return fetchJSON('/settings/strategy')
}

export async function updateStrategySettings(changes) {
  const res = await fetch(`${BASE}/settings/strategy`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify({ changes }),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function resetStrategyParam(key) {
  const res = await fetch(`${BASE}/settings/strategy/reset`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ key }),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

// ── Academy ──

export async function getAcademyToday() {
  return fetchJSON('/academy/today')
}

export async function getAcademyConcepts() {
  return fetchJSON('/academy/concepts')
}

export async function getAcademyConcept(conceptId) {
  return fetchJSON(`/academy/concepts/${conceptId}`)
}

export async function getAcademyPatterns() {
  return fetchJSON('/academy/patterns')
}

// ── Notification Schedule ──

export async function getNotificationSchedule() {
  return fetchJSON('/notifications/schedule')
}

export async function updateNotificationSchedule(schedule) {
  const res = await fetch(`${BASE}/notifications/schedule`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(schedule),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function testNotificationCheck() {
  return fetchJSON('/notifications/test')
}

// ── Watchlist ──

export async function getWatchlist(market = null) {
  const q = market ? `?market=${market}` : ''
  return fetchJSON(`/watchlist${q}`)
}

export async function addPosition(data) {
  const res = await fetch(`${BASE}/portfolio/position`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function deletePosition(market, symbol, portfolioId = 1) {
  const opts = { method: 'DELETE', headers: authHeaders() }
  const res = await fetch(`${BASE}/portfolio/position/${market}/${symbol}?portfolio_id=${portfolioId}`, opts)
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function quickAddPositions(items, portfolioId = 1) {
  const res = await fetch(`${BASE}/portfolio/quick?portfolio_id=${portfolioId}`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(items),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function addWatchlistItem(data) {
  const res = await fetch(`${BASE}/watchlist`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

export async function removeWatchlistItem(symbol, market = 'KR') {
  const opts = { method: 'DELETE', headers: authHeaders() }
  const res = await fetch(`${BASE}/watchlist/${symbol}?market=${market}`, opts)
  if (!res.ok) throw new Error(friendlyError(res.status, null))
  return res.json()
}

function escapeCSV(val) {
  const str = String(val ?? '')
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

export function exportPortfolioCSV(positions) {
  const headers = ['Symbol', 'Name', 'Market', 'Entry Price', 'Current Price', 'P&L %', 'Position Size', 'Entry Date', 'Sector']
  const rows = positions.map(p => [
    escapeCSV(p.symbol), escapeCSV(p.name || p.symbol), escapeCSV(p.market),
    escapeCSV(p.entry_price || ''), escapeCSV(p.current_price || ''),
    escapeCSV(p.pnl_pct != null ? p.pnl_pct.toFixed(2) : ''),
    escapeCSV(p.position_size || ''), escapeCSV(p.entry_date || ''), escapeCSV(p.sector || '')
  ])
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `vibe_portfolio_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 100)
}

export function exportSignalsCSV(signals) {
  const headers = ['Date', 'Symbol', 'Name', 'Market', 'Signal', 'Score', 'RSI', 'Hard Limit', 'Rationale']
  const rows = signals.map(s => [
    escapeCSV(s.signal_date), escapeCSV(s.symbol), escapeCSV(s.name || s.symbol),
    escapeCSV(s.market), escapeCSV(s.final_signal),
    escapeCSV(s.raw_score?.toFixed(1) ?? ''), escapeCSV(s.rsi_value?.toFixed(1) ?? ''),
    escapeCSV(s.hard_limit_triggered ? 'YES' : 'NO'), escapeCSV(s.rationale || '')
  ])
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `vibe_signals_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 100)
}
