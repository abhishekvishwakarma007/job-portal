import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'
import { ApiError } from '../lib/api'

interface LocationState {
  from?: string
}

/** Sign-in screen. */
export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Already signed in: send them where they were headed rather than showing a
  // login form that would immediately redirect after a pointless round trip.
  if (user) {
    const destination = (location.state as LocationState | null)?.from ?? '/'
    return <Navigate to={destination} replace />
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      const signedIn = await login(email, password)
      const state = location.state as LocationState | null
      // HR users land on their postings; candidates on the job list.
      const fallback = signedIn.role === 'HR' ? '/manage' : '/'
      navigate(state?.from ?? fallback, { replace: true })
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : 'Could not sign in. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="card" style={{ maxWidth: '26rem', margin: '0 auto' }}>
      <h1>Sign in</h1>

      {error && (
        <p className="alert alert--error" role="alert">
          {error}
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>

        <button className="button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>

      <p className="muted" style={{ marginTop: '1rem' }}>
        No account? <Link to="/register">Create one</Link>
      </p>
    </section>
  )
}
