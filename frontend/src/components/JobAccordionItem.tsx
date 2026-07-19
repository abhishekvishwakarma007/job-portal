import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'
import { COVER_LETTER_MAX_LENGTH } from '../constants'
import { ApiError, request } from '../lib/api'
import { EMPLOYMENT_TYPE_LABELS, type Job } from '../types'

interface JobAccordionItemProps {
  job: Job
  isOpen: boolean
  onToggle: () => void
}

/**
 * One row of the job list: a summary that expands to the full description and,
 * for a signed-in candidate, the apply form.
 *
 * Applying inline rather than on a separate page means the candidate never
 * loses their place in a filtered list — which is exactly when they are most
 * likely to apply to more than one role.
 */
export default function JobAccordionItem({
  job,
  isOpen,
  onToggle,
}: JobAccordionItemProps) {
  const { user } = useAuth()

  const [coverLetter, setCoverLetter] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [hasApplied, setHasApplied] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const panelId = `job-panel-${job.id}`
  const headerId = `job-header-${job.id}`

  async function handleApply(event: FormEvent) {
    event.preventDefault()
    setError(null)

    if (!coverLetter.trim()) {
      setError('A cover letter is required.')
      return
    }

    setIsSubmitting(true)

    try {
      await request('/applications', {
        method: 'POST',
        body: { job_id: job.id, cover_letter: coverLetter },
      })
      setHasApplied(true)
    } catch (cause) {
      // 409 means they already applied. That is the outcome they wanted, so
      // showing a red failure would be both confusing and wrong.
      if (cause instanceof ApiError && cause.status === 409) {
        setHasApplied(true)
        return
      }

      setError(
        cause instanceof ApiError
          ? cause.message
          : 'Could not submit the application. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <li className="overflow-hidden rounded-xl border border-[color:var(--border)] bg-white shadow-sm">
      <h3 className="m-0">
        <button
          type="button"
          id={headerId}
          onClick={onToggle}
          aria-expanded={isOpen}
          aria-controls={panelId}
          className="flex w-full cursor-pointer items-start justify-between gap-4 border-0 bg-transparent px-5 py-4 text-left"
        >
          <span>
            <span className="block text-base font-semibold text-slate-900">
              {job.title}
            </span>
            <span className="mt-0.5 block text-sm font-medium text-[color:var(--accent)]">
              {job.company}
            </span>
            <span className="mt-1 block text-sm text-[color:var(--text-muted)]">
              {job.location} · {EMPLOYMENT_TYPE_LABELS[job.employment_type]} ·
              posted by {job.created_by.full_name}
            </span>
          </span>

          <span
            aria-hidden="true"
            className={`mt-1 shrink-0 text-[color:var(--text-muted)] transition-transform ${
              isOpen ? 'rotate-180' : ''
            }`}
          >
            ▾
          </span>
        </button>
      </h3>

      {isOpen && (
        <div
          id={panelId}
          role="region"
          aria-labelledby={headerId}
          className="border-t border-[color:var(--border)] px-5 py-4"
        >
          {/* Text, never dangerouslySetInnerHTML — the description is
              user-supplied, and injecting it as HTML would be stored XSS. */}
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
            {job.description}
          </p>

          {hasApplied && (
            <p
              role="status"
              className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
            >
              Application submitted. Track it under{' '}
              <Link to="/applications" className="font-semibold underline">
                My applications
              </Link>
              .
            </p>
          )}

          {!hasApplied && user?.role === 'CANDIDATE' && (
            <form onSubmit={handleApply} noValidate className="mt-4">
              {error && (
                <p
                  role="alert"
                  className="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
                >
                  {error}
                </p>
              )}

              <label
                htmlFor={`cover-${job.id}`}
                className="block text-sm font-semibold text-slate-900"
              >
                Cover letter
              </label>
              <textarea
                id={`cover-${job.id}`}
                value={coverLetter}
                maxLength={COVER_LETTER_MAX_LENGTH}
                onChange={(event) => setCoverLetter(event.target.value)}
                placeholder="Why are you a good fit for this role?"
                className="mt-1 min-h-28 w-full rounded-lg border border-[color:var(--border)] px-3 py-2 text-sm"
                required
              />
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="rounded-lg bg-[color:var(--accent)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
                >
                  {isSubmitting ? 'Submitting…' : 'Apply for this role'}
                </button>
                <span className="text-xs text-[color:var(--text-muted)]">
                  {coverLetter.length} / {COVER_LETTER_MAX_LENGTH}
                </span>
              </div>
            </form>
          )}

          {!user && (
            <p className="mt-4 text-sm text-[color:var(--text-muted)]">
              <Link to="/login" className="font-semibold">
                Sign in
              </Link>{' '}
              as a candidate to apply for this role.
            </p>
          )}

          {user?.role === 'HR' && (
            <p className="mt-4 text-sm text-[color:var(--text-muted)]">
              You are signed in as HR. Applications come from candidate
              accounts.
            </p>
          )}

          <p className="mt-4 text-sm">
            <Link to={`/jobs/${job.id}`} className="font-medium">
              Open full page →
            </Link>
          </p>
        </div>
      )}
    </li>
  )
}
