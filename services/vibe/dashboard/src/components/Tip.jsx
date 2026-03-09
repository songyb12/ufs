/**
 * Tip — Lightweight hover tooltip component.
 *
 * Usage:
 *   <Tip text="설명 텍스트">
 *     <span>호버 대상</span>
 *   </Tip>
 *
 * Or inline with a dotted underline indicator:
 *   <Tip text="설명" indicator>RSI</Tip>
 */
import { useState, useRef, useEffect, useCallback } from 'react'

const STYLES = {
  wrapper: {
    position: 'relative',
    display: 'inline-flex',
    alignItems: 'center',
    cursor: 'help',
  },
  indicator: {
    borderBottom: '1px dotted rgba(148,163,184,0.5)',
  },
  bubble: {
    position: 'fixed',
    zIndex: 9999,
    maxWidth: '320px',
    minWidth: '160px',
    padding: '0.6rem 0.8rem',
    borderRadius: '0.5rem',
    background: '#1e293b',
    border: '1px solid #475569',
    boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
    color: '#e2e8f0',
    fontSize: '0.78rem',
    lineHeight: 1.55,
    pointerEvents: 'none',
    whiteSpace: 'pre-line',
  },
  arrow: {
    position: 'absolute',
    width: '8px',
    height: '8px',
    background: '#1e293b',
    border: '1px solid #475569',
    transform: 'rotate(45deg)',
    zIndex: -1,
  },
}

export default function Tip({ text, children, indicator = false, placement = 'top' }) {
  const [show, setShow] = useState(false)
  const [pos, setPos] = useState({ top: 0, left: 0, arrowStyle: {} })
  const wrapperRef = useRef(null)
  const bubbleRef = useRef(null)
  const timerRef = useRef(null)

  const computePosition = useCallback(() => {
    if (!wrapperRef.current || !bubbleRef.current) return
    const triggerRect = wrapperRef.current.getBoundingClientRect()
    const bubbleRect = bubbleRef.current.getBoundingClientRect()
    const gap = 8

    let top, left, arrowStyle = {}

    // Try preferred placement, fall back if off-screen
    if (placement === 'top' && triggerRect.top - bubbleRect.height - gap > 10) {
      top = triggerRect.top - bubbleRect.height - gap
      left = triggerRect.left + triggerRect.width / 2 - bubbleRect.width / 2
      arrowStyle = {
        bottom: '-5px',
        left: '50%',
        marginLeft: '-4px',
        borderTop: 'none',
        borderLeft: 'none',
      }
    } else {
      // Bottom fallback
      top = triggerRect.bottom + gap
      left = triggerRect.left + triggerRect.width / 2 - bubbleRect.width / 2
      arrowStyle = {
        top: '-5px',
        left: '50%',
        marginLeft: '-4px',
        borderBottom: 'none',
        borderRight: 'none',
      }
    }

    // Clamp horizontal to viewport
    const vw = window.innerWidth
    if (left < 10) left = 10
    if (left + bubbleRect.width > vw - 10) left = vw - bubbleRect.width - 10

    setPos({ top, left, arrowStyle })
  }, [placement])

  const handleEnter = () => {
    timerRef.current = setTimeout(() => setShow(true), 200)
  }
  const handleLeave = () => {
    clearTimeout(timerRef.current)
    setShow(false)
  }

  useEffect(() => {
    if (show) computePosition()
  }, [show, computePosition])

  useEffect(() => {
    return () => clearTimeout(timerRef.current)
  }, [])

  if (!text) return children

  return (
    <span
      ref={wrapperRef}
      style={{ ...STYLES.wrapper, ...(indicator ? STYLES.indicator : {}) }}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      onFocus={handleEnter}
      onBlur={handleLeave}
    >
      {children}
      {show && (
        <div ref={bubbleRef} style={{ ...STYLES.bubble, top: pos.top, left: pos.left }}>
          <div style={{ ...STYLES.arrow, ...pos.arrowStyle }} />
          {text}
        </div>
      )}
    </span>
  )
}
