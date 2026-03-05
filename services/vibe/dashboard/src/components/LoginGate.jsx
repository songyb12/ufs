import { useState, useEffect } from 'react'
import { getStoredApiKey, setApiKey, getHealth } from '../api'

export default function LoginGate({ children }) {
  const [authenticated, setAuthenticated] = useState(null) // null = checking
  const [keyInput, setKeyInput] = useState('')
  const [error, setError] = useState(null)
  const [checking, setChecking] = useState(false)

  useEffect(() => {
    // Check if we can access the API
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const h = await getHealth()
      if (h && h.status) {
        setAuthenticated(true)
      } else {
        setAuthenticated(false)
      }
    } catch (err) {
      if (err.message?.includes('401')) {
        // Auth required but no valid key
        setAuthenticated(false)
      } else {
        // Network error or server down — show dashboard anyway
        setAuthenticated(true)
      }
    }
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!keyInput.trim()) return
    setChecking(true)
    setError(null)
    // Temporarily set key and test
    setApiKey(keyInput.trim())
    try {
      const h = await getHealth()
      if (h && h.status) {
        setAuthenticated(true)
      } else {
        setApiKey(null)
        setError('API key validation failed')
      }
    } catch (err) {
      setApiKey(null)
      if (err.message?.includes('401')) {
        setError('Invalid API key')
      } else {
        setError(`Connection error: ${err.message}`)
      }
    } finally {
      setChecking(false)
    }
  }

  // Still checking
  if (authenticated === null) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', background: 'var(--bg-primary)',
      }}>
        <div style={{ textAlign: 'center' }}>
          <span className="spinner" style={{ width: 32, height: 32 }} />
          <p style={{ color: 'var(--text-muted)', marginTop: '1rem' }}>Connecting...</p>
        </div>
      </div>
    )
  }

  // Authenticated
  if (authenticated) {
    return children
  }

  // Login screen
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', background: 'var(--bg-primary)',
    }}>
      <div style={{
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        borderRadius: '1rem',
        padding: '2.5rem',
        width: '100%',
        maxWidth: '400px',
        textAlign: 'center',
      }}>
        <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>{'\uD83D\uDCC8'}</div>
        <h1 style={{ fontSize: '1.5rem', color: 'var(--text-primary)', marginBottom: '0.25rem' }}>VIBE</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '2rem' }}>
          Investment Intelligence Dashboard
        </p>

        <form onSubmit={handleLogin}>
          <input
            type="password"
            placeholder="API Key"
            value={keyInput}
            onChange={e => setKeyInput(e.target.value)}
            autoFocus
            style={{
              width: '100%', padding: '0.75rem 1rem', borderRadius: '0.5rem',
              background: 'var(--bg-primary)', border: '1px solid var(--border)',
              color: 'var(--text-primary)', fontSize: '0.9rem',
              boxSizing: 'border-box',
              marginBottom: '1rem',
            }}
          />
          {error && (
            <p style={{ color: 'var(--red)', fontSize: '0.8rem', marginBottom: '0.75rem' }}>
              {'\u274C'} {error}
            </p>
          )}
          <button
            type="submit"
            className="btn btn-primary"
            disabled={checking || !keyInput.trim()}
            style={{ width: '100%', padding: '0.75rem', fontSize: '0.9rem' }}
          >
            {checking ? 'Verifying...' : '\uD83D\uDD13 Login'}
          </button>
        </form>

        <p style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginTop: '1.5rem' }}>
          .env {'\uD30C\uC77C\uC758'} API_KEY {'\uAC12\uC744'} {'\uC785\uB825\uD558\uC138\uC694'}
        </p>
      </div>
    </div>
  )
}
