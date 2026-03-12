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
          setError('서버에 연결할 수 없습니다. 네트워크를 확인해주세요.')
        }
      }
    }
  }

  const handleRegister = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return
    if (password !== passwordConfirm) {
      setError('비밀번호가 일치하지 않습니다')
      return
    }
    if (password.length < 4) {
      setError('비밀번호는 4자 이상이어야 합니다')
      return
    }
    setChecking(true)
    setError(null)
    try {
      const r = await authRegister(username.trim(), password)
      localStorage.setItem('vibe_auth_token', r.token)
      setState('authenticated')
    } catch (err) {
      setError(err.message || '계정 생성 실패')
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
        setError('아이디 또는 비밀번호가 올바르지 않습니다')
      } else {
        setError(err.message || '로그인 실패')
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
        setError('API Key 검증 실패')
      }
    } catch (err) {
      setApiKey(null)
      if (err.message?.includes('401')) {
        setError('잘못된 API Key')
      } else {
        setError(`연결 오류: ${err.message}`)
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
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{'🔑'}</div>
          <h2 style={{ fontSize: '1.25rem', color: 'var(--text-primary)', marginBottom: '1.5rem' }}>API Key Login</h2>

          <form onSubmit={handleApiKeyLogin}>
            <input type="password" placeholder="API Key" value={apiKeyInput}
              onChange={e => setApiKeyInput(e.target.value)} autoFocus
              style={inputStyle} />
            {error && <p style={errorStyle}>{'❌'} {error}</p>}
            <button type="submit" className="btn btn-primary" disabled={checking || !apiKeyInput.trim()}
              style={{ width: '100%', padding: '0.75rem', fontSize: '0.9rem' }}>
              {checking ? 'Verifying...' : '🔓 Login'}
            </button>
          </form>

          <button onClick={() => { setError(null); setState('login') }}
            style={{ ...linkStyle, marginTop: '1.5rem' }}>
            {'←'} ID/PW 로그인으로 돌아가기
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
        <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>{'📈'}</div>
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
            {'✨'} {'첫 접속입니다. 관리자 계정을 생성해주세요.'}
          </div>
        )}

        <form onSubmit={isSetup ? handleRegister : handleLogin}>
          <input type="text" placeholder={'아이디'} value={username}
            onChange={e => setUsername(e.target.value)} autoFocus autoComplete="username"
            style={{ ...inputStyle, marginBottom: '0.75rem' }} />
          <input type="password" placeholder={'비밀번호'} value={password}
            onChange={e => setPassword(e.target.value)} autoComplete={isSetup ? 'new-password' : 'current-password'}
            style={{ ...inputStyle, marginBottom: isSetup ? '0.75rem' : '1rem' }} />
          {isSetup && (
            <input type="password" placeholder={'비밀번호 확인'} value={passwordConfirm}
              onChange={e => setPasswordConfirm(e.target.value)} autoComplete="new-password"
              style={{ ...inputStyle, marginBottom: '1rem' }} />
          )}
          {error && <p style={errorStyle}>{'❌'} {error}</p>}
          <button type="submit" className="btn btn-primary"
            disabled={checking || !username.trim() || !password.trim() || (isSetup && !passwordConfirm.trim())}
            style={{ width: '100%', padding: '0.75rem', fontSize: '0.9rem' }}>
            {checking
              ? (isSetup ? '생성 중...' : '로그인 중...')
              : (isSetup ? '✨ 계정 생성' : '🔓 로그인')
            }
          </button>
        </form>

        <button onClick={() => { setError(null); setState('apikey') }}
          style={{ ...linkStyle, marginTop: '1.5rem' }}>
          API Key{'로 로그인'}
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
