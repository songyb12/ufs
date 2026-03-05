const BASE = ''

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

function authHeaders() {
  const headers = { 'Content-Type': 'application/json' }
  const key = getApiKey()
  if (key) headers['X-API-Key'] = key
  return headers
}

async function fetchJSON(path) {
  const key = getApiKey()
  const opts = key ? { headers: { 'X-API-Key': key } } : {}
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function getSummary(portfolioId = 1) {
  return fetchJSON(`/dashboard/summary?portfolio_id=${portfolioId}`)
}

export async function getSignals(market = null) {
  const q = market ? `?market=${market}` : ''
  return fetchJSON(`/signals${q}`)
}

export async function getSignalHistory(market = null, days = 30) {
  let q = `?days=${days}`
  if (market) q += `&market=${market}`
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
  if (!res.ok) throw new Error(`API error: ${res.status}`)
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
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function updatePortfolioGroup(groupId, name, description = null) {
  const res = await fetch(`${BASE}/portfolio/groups/${groupId}`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify({ name, description }),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function deletePortfolioGroup(groupId) {
  const res = await fetch(`${BASE}/portfolio/groups/${groupId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
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
  if (!res.ok) throw new Error(`API error: ${res.status}`)
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
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function getPriceChart(symbol, market = 'KR', days = 60) {
  return fetchJSON(`/dashboard/prices/${symbol}?market=${market}&days=${days}`)
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
  if (!res.ok) throw new Error(`API error: ${res.status}`)
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
  if (!res.ok) throw new Error(`API error: ${res.status}`)
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
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function getMonthlyReports(limit = 12) {
  return fetchJSON(`/dashboard/reports/monthly?limit=${limit}`)
}

export async function generateMonthlyReport(reportMonth = null) {
  const body = reportMonth ? { report_month: reportMonth } : {}
  const res = await fetch(`${BASE}/dashboard/reports/monthly/generate`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function triggerPipeline(market = 'ALL') {
  const res = await fetch('/pipeline/run', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ market }),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

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
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function deletePosition(market, symbol, portfolioId = 1) {
  const opts = { method: 'DELETE', headers: authHeaders() }
  const res = await fetch(`${BASE}/portfolio/position/${market}/${symbol}?portfolio_id=${portfolioId}`, opts)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function quickAddPositions(items, portfolioId = 1) {
  const res = await fetch(`${BASE}/portfolio/quick?portfolio_id=${portfolioId}`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(items),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function addWatchlistItem(data) {
  const res = await fetch(`${BASE}/watchlist`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function removeWatchlistItem(symbol, market = 'KR') {
  const opts = { method: 'DELETE', headers: authHeaders() }
  const res = await fetch(`${BASE}/watchlist/${symbol}?market=${market}`, opts)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
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
  URL.revokeObjectURL(url)
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
  URL.revokeObjectURL(url)
}
