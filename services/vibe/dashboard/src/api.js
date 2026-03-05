const BASE = ''
const API_KEY = import.meta.env.VITE_API_KEY || ''

function authHeaders() {
  const headers = { 'Content-Type': 'application/json' }
  if (API_KEY) headers['X-API-Key'] = API_KEY
  return headers
}

async function fetchJSON(path) {
  const opts = API_KEY ? { headers: { 'X-API-Key': API_KEY } } : {}
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function getSummary() {
  return fetchJSON('/dashboard/summary')
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

export async function getPortfolio(market = null) {
  const q = market ? `?market=${market}` : ''
  return fetchJSON(`/portfolio${q}`)
}

export async function getPortfolioScenarios(market = null) {
  const q = market ? `?market=${market}` : ''
  return fetchJSON(`/portfolio/scenarios${q}`)
}

export async function getHealth() {
  return fetchJSON('/health')
}

export async function getPipelineRuns() {
  return fetchJSON('/pipeline/runs')
}

export async function getPriceChart(symbol, market = 'KR', days = 60) {
  return fetchJSON(`/dashboard/prices/${symbol}?market=${market}&days=${days}`)
}

export async function triggerPipeline(market = 'ALL') {
  const res = await fetch('/pipeline/run', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ market }),
  })
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

export async function deletePosition(market, symbol) {
  const opts = { method: 'DELETE' }
  if (API_KEY) opts.headers = { 'X-API-Key': API_KEY }
  const res = await fetch(`${BASE}/portfolio/position/${market}/${symbol}`, opts)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function quickAddPositions(items) {
  const res = await fetch(`${BASE}/portfolio/quick`, {
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
  const opts = { method: 'DELETE' }
  if (API_KEY) opts.headers = { 'X-API-Key': API_KEY }
  const res = await fetch(`${BASE}/watchlist/${symbol}?market=${market}`, opts)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export function exportPortfolioCSV(positions) {
  const headers = ['Symbol', 'Name', 'Market', 'Entry Price', 'Current Price', 'P&L %', 'Position Size', 'Entry Date', 'Sector']
  const rows = positions.map(p => [
    p.symbol, p.name || p.symbol, p.market,
    p.entry_price || '', p.current_price || '',
    p.pnl_pct != null ? p.pnl_pct.toFixed(2) : '',
    p.position_size || '', p.entry_date || '', p.sector || ''
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
    s.signal_date, s.symbol, s.name || s.symbol, s.market,
    s.final_signal, s.raw_score?.toFixed(1), s.rsi_value?.toFixed(1),
    s.hard_limit_triggered ? 'YES' : 'NO', `"${(s.rationale || '').replace(/"/g, '""')}"`
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
