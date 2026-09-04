import { useState } from 'react'
import { login, register } from '../api.js'

export default function AuthPanel({ onAuthenticated }) {
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const data = mode === 'login' ? await login(email, password) : await register(email, password)
      onAuthenticated(data.token, data.user)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-panel">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h2 className="auth-title">{mode === 'login' ? 'Log in' : 'Create an account'}</h2>
        <label className="auth-field">
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </label>
        <label className="auth-field">
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            required
          />
        </label>
        {error && (
          <p className="status" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="primary" disabled={submitting}>
          {mode === 'login' ? 'Log in' : 'Create account'}
        </button>
        <button
          type="button"
          className="auth-toggle"
          onClick={() => {
            setMode(mode === 'login' ? 'register' : 'login')
            setError('')
          }}
        >
          {mode === 'login' ? 'Need an account? Create one' : 'Already have one? Log in'}
        </button>
      </form>
    </div>
  )
}
