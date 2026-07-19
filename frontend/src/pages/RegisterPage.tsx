import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import {
  PASSWORD_HINT,
  validateEmail,
  validateFullName,
  validatePassword,
} from '../auth/passwordPolicy'
import { useAuth } from '../auth/useAuth'
import { ApiError } from '../lib/api'
import type { UserRole } from '../types'

type FieldErrors = Partial<Record<'email' | 'password' | 'full_name', string>>

/** Registration screen for both roles. */
export default function RegisterPage() {
  const { user, register } = useAuth()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<UserRole>('CANDIDATE')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (user) return <Navigate to="/" replace />

  /** Run the client-side mirror of the server's rules. */
  function validate(): FieldErrors {
    const errors: FieldErrors = {}

    const nameError = validateFullName(fullName)
    if (nameError) errors.full_name = nameError

    const emailError = validateEmail(email)
    if (emailError) errors.email = emailError

    const passwordError = validatePassword(password)
    if (passwordError) errors.password = passwordError

    return errors
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    const errors = validate()
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return

    setIsSubmitting(true)

    try {
      const created = await register({
        email,
        password,
        full_name: fullName,
        role,
      })
      navigate(created.role === 'HR' ? '/manage' : '/jobs', { replace: true })
    } catch (cause) {
      if (cause instanceof ApiError) {
        // The server's per-field messages win over the client's: it validated
        // the same input with the authoritative rules.
        setFieldErrors(cause.fieldErrors as FieldErrors)
        setError(
          Object.keys(cause.fieldErrors).length > 0 ? null : cause.message,
        )
      } else {
        setError('Could not create the account. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="card" style={{ maxWidth: '30rem', margin: '0 auto' }}>
      <h1>Create an account</h1>

      {error && (
        <p className="alert alert--error" role="alert">
          {error}
        </p>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="full_name">Full name</label>
          <input
            id="full_name"
            name="full_name"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            aria-invalid={Boolean(fieldErrors.full_name)}
            aria-describedby={fieldErrors.full_name ? 'full_name-error' : undefined}
            required
          />
          {fieldErrors.full_name && (
            <span className="field__error" id="full_name-error">
              {fieldErrors.full_name}
            </span>
          )}
        </div>

        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            aria-invalid={Boolean(fieldErrors.email)}
            aria-describedby={fieldErrors.email ? 'email-error' : undefined}
            required
          />
          {fieldErrors.email && (
            <span className="field__error" id="email-error">
              {fieldErrors.email}
            </span>
          )}
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            aria-invalid={Boolean(fieldErrors.password)}
            aria-describedby="password-hint"
            required
          />
          <span className="field__hint" id="password-hint">
            {PASSWORD_HINT}
          </span>
          {fieldErrors.password && (
            <span className="field__error">{fieldErrors.password}</span>
          )}
        </div>

        <fieldset
          className="field"
          style={{ border: 0, padding: 0, margin: '0 0 1rem' }}
        >
          <legend style={{ fontWeight: 600, fontSize: '0.9rem' }}>
            I am a
          </legend>
          <div className="row">
            <label className="row" style={{ fontWeight: 400 }}>
              <input
                type="radio"
                name="role"
                value="CANDIDATE"
                checked={role === 'CANDIDATE'}
                onChange={() => setRole('CANDIDATE')}
                style={{ width: 'auto' }}
              />
              Candidate looking for work
            </label>
            <label className="row" style={{ fontWeight: 400 }}>
              <input
                type="radio"
                name="role"
                value="HR"
                checked={role === 'HR'}
                onChange={() => setRole('HR')}
                style={{ width: 'auto' }}
              />
              HR posting roles
            </label>
          </div>
        </fieldset>

        <button className="button" type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>

      <p className="muted" style={{ marginTop: '1rem' }}>
        Already registered? <Link to="/login">Sign in</Link>
      </p>
    </section>
  )
}
