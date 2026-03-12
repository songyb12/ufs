/**
 * PageGuide — Dismissible contextual guide shown at top of each page.
 *
 * Guides are dismissed per-page and remembered in localStorage.
 * Reset all: localStorage.removeItem('vibe_dismissed_guides')
 */
import { useState, useEffect } from 'react'

const STORAGE_KEY = 'vibe_dismissed_guides'

function getDismissed() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

export default function PageGuide({ pageId, title, steps, color = 'var(--accent)' }) {
  const [dismissed, setDismissed] = useState(true)

  useEffect(() => {
    const d = getDismissed()
    setDismissed(!!d[pageId])
  }, [pageId])

  const handleDismiss = () => {
    const d = getDismissed()
    d[pageId] = true
    localStorage.setItem(STORAGE_KEY, JSON.stringify(d))
    setDismissed(true)
  }

  if (dismissed || !steps?.length) return null

  return (
    <div style={{
      background: `linear-gradient(135deg, ${color}10, ${color}05)`,
      border: `1px solid ${color}30`,
      borderRadius: '0.75rem',
      padding: '0.85rem 1.25rem',
      marginBottom: '1.25rem',
      display: 'flex',
      alignItems: 'flex-start',
      gap: '1rem',
    }}>
      <span style={{ fontSize: '1.1rem', marginTop: '0.1rem' }}>{'💡'}</span>
      <div style={{ flex: 1 }}>
        {title && (
          <div style={{ fontWeight: 600, fontSize: '0.82rem', marginBottom: '0.35rem', color: 'var(--text-primary)' }}>
            {title}
          </div>
        )}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem 1.25rem' }}>
          {steps.map((step, i) => (
            <span key={i} style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              <span style={{ color, fontWeight: 600, marginRight: '0.3rem' }}>{i + 1}.</span>
              {step}
            </span>
          ))}
        </div>
      </div>
      <button
        onClick={handleDismiss}
        style={{
          background: 'none', border: 'none', color: 'var(--text-muted)',
          cursor: 'pointer', fontSize: '0.85rem', padding: '0.2rem',
          lineHeight: 1, flexShrink: 0,
        }}
        title="닫기 (다시 보려면 가이드 페이지 참고)"
      >
        {'✕'}
      </button>
    </div>
  )
}
