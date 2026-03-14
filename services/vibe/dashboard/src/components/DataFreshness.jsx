import { useState, useEffect } from 'react'

/**
 * Shared data freshness indicator component.
 * Shows relative time since last update with color-coded staleness.
 *
 * @param {string|Date} updatedAt - ISO string or Date of last update
 * @param {function} [onRefresh] - Optional refresh callback (renders button)
 * @param {boolean} [refreshing] - Whether refresh is in progress
 * @param {boolean} [compact] - Compact mode (dot + time only)
 */
export default function DataFreshness({ updatedAt, onRefresh, refreshing, compact }) {
  const [now, setNow] = useState(Date.now())

  // Tick every 30s to update relative time
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(timer)
  }, [])

  if (!updatedAt) return null

  const ts = updatedAt instanceof Date ? updatedAt.getTime() : new Date(updatedAt).getTime()
  if (isNaN(ts)) return null

  const diffMs = now - ts
  const diffMin = Math.floor(diffMs / 60000)
  const diffHr = Math.floor(diffMin / 60)

  // Relative time in Korean
  let label
  if (diffMin < 1) label = '방금 전'
  else if (diffMin < 60) label = `${diffMin}분 전`
  else if (diffHr < 24) label = `${diffHr}시간 전`
  else label = `${Math.floor(diffHr / 24)}일 전`

  // Color by staleness
  let color
  if (diffMin < 5) color = '#22c55e'       // green: fresh
  else if (diffMin < 30) color = '#eab308'  // yellow: aging
  else if (diffMin < 60) color = '#f97316'  // orange: stale
  else color = '#ef4444'                    // red: very stale

  if (compact) {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.65rem', color: 'var(--text-muted)' }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: color, display: 'inline-block', flexShrink: 0 }} />
        {label}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={refreshing}
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0, fontSize: '0.7rem' }}
            title="새로고침"
          >
            {refreshing ? '⏳' : '↻'}
          </button>
        )}
      </span>
    )
  }

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontSize: '0.7rem', color: 'var(--text-muted)',
      padding: '3px 8px', borderRadius: 6,
      background: `${color}11`, border: `1px solid ${color}33`,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: color, display: 'inline-block', flexShrink: 0 }} />
      <span>{label} 갱신</span>
      {onRefresh && (
        <button
          onClick={onRefresh}
          disabled={refreshing}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text-muted)', padding: '0 2px', fontSize: '0.75rem',
          }}
          title="새로고침"
        >
          {refreshing ? '⏳' : '↻'}
        </button>
      )}
    </div>
  )
}

/**
 * Hook to track data freshness with auto-stale detection.
 * Returns updatedAt timestamp and setter, plus isStale flag.
 *
 * @param {number} [staleMinutes=5] - Minutes before data is considered stale
 */
export function useDataFreshness(staleMinutes = 5) {
  const [updatedAt, setUpdatedAt] = useState(null)
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(timer)
  }, [])

  const isStale = updatedAt
    ? (now - (updatedAt instanceof Date ? updatedAt.getTime() : new Date(updatedAt).getTime())) > staleMinutes * 60000
    : true

  return { updatedAt, setUpdatedAt, isStale }
}
