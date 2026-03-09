import { useState, useEffect } from 'react'
import { authStatus, authLogin, authRegister, getHealth, getStoredApiKey, setApiKey } from '../api'

export default function LoginGate({ children }) {
  const [state, setState] = useState('loading') // loading | setup | login | authenticated | apikey
  const [error, setError] = useState(null)
  const [checking, setChecking] = useState(false)

  // Form fields
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [apiKeyInput, setApiKeyInput] = useState('')

  useEffect(() => { checkAuth() }, [])

  const checkAuth = async () => {
    try {
      const s = await authStatus()
      if (s.authenticated) {
        setState('authenticated')
      } else if (s.needs_setup) {
        setState('setup')
      } else {
        setState('login')
      }
    } catch (err) {
      // /auth/status not available — try legacy health check
      try {
        const h = await getHealth()
        if (h && h.status) {
          // Server is up but auth endpoints not available — allow access
          setState('authenticated')
        } else {
          setState('login')
        }
      } catch (e2) {
        if (e2.message?.includes('401')) {
          setState('login')
        } else {
          // Server unreachable — show login with error
          setState('login')
          setError('\uC11C\uBC84\uC5D0 \uC5F0\uACB0\uD560 \uC218 \uC5C6\uC2B5\uB2C8\uB2E4. \uB124\uD2B8\uC6CC\uD06C\uB97C \uD655\uC778\uD574\uC8FC\uC138\uC694.')
        }
      }
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return
    if (password !== passwordConfirm) {
      setError('\uBE44\uBC00\uBC88\uD638\uAC00 \uC77C\uCE58\uD558\uC9C0 \uC54A\uC2B5\uB2C8\uB2E4')
      return
    }
    if (password.length < 4) {
      setError('\uBE44\uBC00\uBC88\uD638\uB294 4\uC790 \uC774\uC0C1\uC774\uC5B4\uC57C \uD569\uB2C8\uB2E4')
      return
    }
    setChecking(true)
    setError(null)
    try {
      const r = await authRegister(username.trim(), password)
      localStorage.setItem('vibe_auth_token', r.token)
      setState('authenticated')
    } catch (err) {
      setError(err.message || '\uACC4\uC815 \uC0DD\uC131 \uC2E4\uD328')
    } finally {
      setChecking(false)
    }
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return
    setChecking(true)
    setError(null)
    try {
      const r = await authLogin(username.trim(), password)
      localStorage.setItem('vibe_auth_token', r.token)
      setState('authenticated')
    } catch (err) {
      if (err.message?.includes('401')) {
        setError('\uC544\uC774\uB514 \uB610\uB294 \uBE44\uBC00\uBC88\uD638\uAC00 \uC62C\uBC14\uB974\uC9C0 \uC54A\uC2B5\uB2C8\uB2E4')
      } else {
        setError(err.message || '\uB85C\uADF8\uC778 \uC2E4\uD328')
      }
    } finally {
      setChecking(false)
    }
  }

  const handleApiKeyLogin = async (e) => {
    e.preventDefault()
    if (!apiKeyInput.trim()) return
    setChecking(true)
    setError(null)
    setApiKey(apiKeyInput.trim())
    try {
      const h = await getHealth()
      if (h && h.status) {
        setState('authenticated')
      } else {
        setApiKey(null)
        setError('API Key \uAC80\uC99D \uC2E4\uD328')
      }
    } catch (err) {
      setApiKey(null)
      if (err.message?.includes('401')) {
        setError('\uC798\uBABB\uB41C API Key')
      } else {
        setError(`\uC5F0\uACB0 \uC624\uB958: ${err.message}`)
      }
    } finally {
      setChecking(false)
    }
  }

  // Loading
  if (state === 'loading') {
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
  if (state === 'authenticated') {
    return children
  }

  // API Key login (legacy)
  if (state === 'apikey') {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', background: 'var(--bg-primary)',
      }}>
        <div style={{
          background: 'var(--bg-secondary)', border: '1px solid var(--border)',
          borderRadius: '1rem', padding: '2.5rem', width: '100%', maxWidth: '400px', textAlign: 'center',
        }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{'\uD83D\uDD11'}</div>
          <h2 style={{ fontSize: '1.25rem', color: 'var(--text-primary)', marginBottom: '1.5rem' }}>API Key Login</h2>

          <form onSubmit={handleApiKeyLogin}>
            <input type="password" placeholder="API Key" value={apiKeyInput}
              onChange={e => setApiKeyInput(e.target.value)} autoFocus
              style={inputStyle} />
            {error && <p style={errorStyle}>{'\u274C'} {error}</p>}
            <button type="submit" className="btn btn-primary" disabled={checking || !apiKeyInput.trim()}
              style={{ width: '100%', padding: '0.75rem', fontSize: '0.9rem' }}>
              {checking ? 'Verifying...' : '\uD83D\uDD13 Login'}
            </button>
          </form>

          <button onClick={() => { setError(null); setState('login') }}
            style={{ ...linkStyle, marginTop: '1.5rem' }}>
            {'\u2190'} ID/PW \uB85C\uADF8\uC778\uC73C\uB85C \uB3CC\uC544\uAC00\uAE30
          </button>
        </div>
      </div>
    )
  }

  // Setup (first time) or Login
  const isSetup = state === 'setup'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      height: '100vh', background: 'var(--bg-primary)',
    }}>
      <div style={{
        background: 'var(--bg-secondary)', border: '1px solid var(--border)',
        borderRadius: '1rem', padding: '2.5rem', width: '100%', maxWidth: '400px', textAlign: 'center',
      }}>
        <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>{'\uD83D\uDCC8'}</div>
        <h1 style={{ fontSize: '1.5rem', color: 'var(--text-primary)', marginBottom: '0.25rem' }}>VIBE</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
          Investment Intelligence Dashboard
        </p>

        {isSetup && (
          <div style={{
            background: 'rgba(34, 197, 94, 0.1)', border: '1px solid rgba(34, 197, 94, 0.3)',
            borderRadius: '0.5rem', padding: '0.75rem', marginBottom: '1.5rem',
            color: 'var(--green)', fontSize: '0.8rem',
          }}>
            {'\u2728'} {'\uCCAB \uC811\uC18D\uC785\uB2C8\uB2E4. \uAD00\uB9AC\uC790 \uACC4\uC815\uC744 \uC0DD\uC131\uD574\uC8FC\uC138\uC694.'}
          </div>
        )}

        <form onSubmit={isSetup ? handleRegister : handleLogin}>
          <input type="text" placeholder={'\uC544\uC774\uB514'} value={username}
            onChange={e => setUsername(e.target.value)} autoFocus autoComplete="username"
            style={{ ...inputStyle, marginBottom: '0.75rem' }} />
          <input type="password" placeholder={'\uBE44\uBC00\uBC88\uD638'} value={password}
            onChange={e => setPassword(e.target.value)} autoComplete={isSetup ? 'new-password' : 'current-password'}
            style={{ ...inputStyle, marginBottom: isSetup ? '0.75rem' : '1rem' }} />
          {isSetup && (
            <input type="password" placeholder={'\uBE44\uBC00\uBC88\uD638 \uD655\uC778'} value={passwordConfirm}
              onChange={e => setPasswordConfirm(e.target.value)} autoComplete="new-password"
              style={{ ...inputStyle, marginBottom: '1rem' }} />
          )}
          {error && <p style={errorStyle}>{'\u274C'} {error}</p>}
          <button type="submit" className="btn btn-primary"
            disabled={checking || !username.trim() || !password.trim() || (isSetup && !passwordConfirm.trim())}
            style={{ width: '100%', padding: '0.75rem', fontSize: '0.9rem' }}>
            {checking
              ? (isSetup ? '\uC0DD\uC131 \uC911...' : '\uB85C\uADF8\uC778 \uC911...')
              : (isSetup ? '\u2728 \uACC4\uC815 \uC0DD\uC131' : '\uD83D\uDD13 \uB85C\uADF8\uC778')
            }
          </button>
        </form>

        <button onClick={() => { setError(null); setState('apikey') }}
          style={{ ...linkStyle, marginTop: '1.5rem' }}>
          API Key{'\uB85C \uB85C\uADF8\uC778'}
        </button>
      </div>
    </div>
  )
}

const inputStyle = {
  width: '100%', padding: '0.75rem 1rem', borderRadius: '0.5rem',
  background: 'var(--bg-primary)', border: '1px solid var(--border)',
  color: 'var(--text-primary)', fontSize: '0.9rem', boxSizing: 'border-box',
}

const errorStyle = {
  color: 'var(--red)', fontSize: '0.8rem', marginBottom: '0.75rem',
}

const linkStyle = {
  background: 'none', border: 'none', color: 'var(--text-muted)',
  fontSize: '0.75rem', cursor: 'pointer', textDecoration: 'underline',
}
