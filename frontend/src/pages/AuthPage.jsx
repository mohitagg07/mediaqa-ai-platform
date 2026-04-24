import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import toast from 'react-hot-toast'
import './AuthPage.css'

export default function AuthPage() {
  const [mode, setMode]     = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const navigate            = useNavigate()
  const { login, register } = useAuth()

  const submit = async () => {
    if (!username.trim() || !password.trim()) {
      return toast.error('Please fill in all fields')
    }
    setLoading(true)
    try {
      if (mode === 'login') {
        // login() updates AuthContext state + sets localStorage
        await login(username, password)
        toast.success('Signed in successfully!')
        navigate('/dashboard')
      } else {
        // email is optional — pass empty string
        await register(username, '', password)
        toast.success('Account created — signing you in…')
        // auto-login after register
        await login(username, password)
        navigate('/dashboard')
      }
    } catch (e) {
      const msg = e.response?.data?.detail || 'Authentication failed'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const onKey = (e) => { if (e.key === 'Enter') submit() }

  return (
    <div className="auth-root">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="auth-logo">media<span>QA</span></span>
          <p className="auth-sub">
            {mode === 'login' ? 'Sign in to your account' : 'Create a new account'}
          </p>
        </div>

        <div className="auth-fields">
          <div className="auth-field">
            <label>Username</label>
            <input
              className="input"
              value={username}
              onChange={e => setUsername(e.target.value)}
              onKeyDown={onKey}
              placeholder="Enter your username"
              autoFocus
            />
          </div>
          <div className="auth-field">
            <label>Password</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={onKey}
              placeholder="Enter your password"
            />
          </div>
        </div>

        <button
          className="btn btn-primary auth-submit"
          onClick={submit}
          disabled={loading}
        >
          {loading
            ? <span className="spin" />
            : mode === 'login' ? 'Sign in' : 'Create account'
          }
        </button>

        <p className="auth-switch">
          {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}
          {' '}
          <button
            className="auth-link"
            onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
          >
            {mode === 'login' ? 'Register' : 'Sign in'}
          </button>
        </p>

        <div className="auth-divider"><span>or</span></div>

        <button
          className="btn btn-ghost auth-guest"
          onClick={() => navigate('/dashboard')}
        >
          Continue without account
        </button>
      </div>
    </div>
  )
}