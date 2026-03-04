const BASE = import.meta.env.PROD ? '' : ''

async function fetchJSON(path) {
  const res = await fetch(`${BASE}${path}`)
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ market }),
  })
  return res.json()
}

export async function exportSignalsCSV(signals) {
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
