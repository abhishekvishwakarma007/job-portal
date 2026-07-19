import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'
import AsyncBoundary from '../components/AsyncBoundary'
import { COVER_LETTER_MAX_LENGTH } from '../constants'
import { useApiResource } from '../hooks/useApiResource'
import { ApiError, request } from '../lib/api'
import { EMPLOYMENT_TYPE_LABELS, type Application, type Job } from '../types'

/** Job detail, with the apply form for signed-in candidates. */
export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const { user } = useAuth()

  const { data: job, isLoading, error } = useApiResource<Job>(`/jobs/${jobId}`)

  const [coverLetter, setCoverLetter] = useState('')
  const [applyError, setApplyError] = useState<string | null>(null)
  const [hasApplied, setHasApplied] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleApply(event: FormEvent) {
    event.preventDefault()
    setApplyError(null)

    if (!coverLetter.trim()) {
      setApplyError('A cover letter is required.')
      return
    }

    setIsSubmitting(true)

    try {
      await request<Application>('/applications', {
        method: 'POST',
        body: { job_id: jobId, cover_letter: coverLetter },
      })
      setHasApplied(true)
    } catch (cause) {
      // 409 is the duplicate-apply guard. Treated as success-ish: the outcome
      // the candidate wanted is already true, so telling them off would be
      // confusing.
      if (cause instanceof ApiError && cause.status === 409) {
        setHasApplied(true)
        return
      }

      setApplyError(
        cause instanceof ApiError
          ? cause.message
          : 'Could not submit the application. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="stack">
      <p>
        <Link to="/jobs">← Back to all roles</Link>
      </p>

      <AsyncBoundary isLoading={isLoading} error={error}>
        {job && (
          <>
            <article className="card">
              <div className="row row--between">
                <h1>{job.title}</h1>
                {!job.is_published && (
                  <span className="badge badge--neutral">Draft</span>
                )}
              </div>
              <p style={{ color: 'var(--accent)', fontWeight: 600, margin: 0 }}>
                {job.company}
              </p>
              <p className="muted">
                {job.location} · {EMPLOYMENT_TYPE_LABELS[job.employment_type]} ·
                posted by {job.created_by.full_name}
              </p>
              {/* Rendered as text, never as HTML: the description is
                  user-supplied, and dangerouslySetInnerHTML here would be a
                  stored-XSS hole. white-space preserves the author's line
                  breaks without needing markup. */}
              <p style={{ whiteSpace: 'pre-wrap' }}>{job.description}</p>
            </article>

            {hasApplied && (
              <p className="alert alert--success" role="status">
                Your application has been submitted. Track it under{' '}
                <Link to="/applications">My applications</Link>.
              </p>
            )}

            {!hasApplied && user?.role === 'CANDIDATE' && (
              <form className="card" onSubmit={handleApply} noValidate>
                <h2>Apply for this role</h2>

                {applyError && (
                  <p className="alert alert--error" role="alert">
                    {applyError}
                  </p>
                )}

                <div className="field">
                  <label htmlFor="cover_letter">Cover letter</label>
                  <textarea
                    id="cover_letter"
                    value={coverLetter}
                    maxLength={COVER_LETTER_MAX_LENGTH}
                    onChange={(event) => setCoverLetter(event.target.value)}
                    placeholder="Why are you a good fit for this role?"
                    required
                  />
                  <span className="field__hint">
                    {coverLetter.length} / {COVER_LETTER_MAX_LENGTH} characters
                  </span>
                </div>

                <button className="button" type="submit" disabled={isSubmitting}>
                  {isSubmitting ? 'Submitting…' : 'Submit application'}
                </button>
              </form>
            )}

            {!user && (
              <p className="card muted">
                <Link to="/login">Sign in</Link> as a candidate to apply for
                this role.
              </p>
            )}

            {user?.role === 'HR' && (
              <p className="card muted">
                You are signed in as HR. Applications are submitted by candidate
                accounts.
              </p>
            )}
          </>
        )}
      </AsyncBoundary>
    </section>
  )
}
