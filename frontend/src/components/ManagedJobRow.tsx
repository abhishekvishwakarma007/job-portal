import { useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, request } from '../lib/api'
import {
  EMPLOYMENT_TYPE_LABELS,
  type Job,
  type RecommendationPage,
  type RecommendedApplicant,
} from '../types'

interface ManagedJobRowProps {
  job: Job
  isOpen: boolean
  onToggle: () => void
  onChanged: () => void
}

/**
 * One posting in the HR list: summary, and on expand the actions plus the
 * best-matching applicants.
 *
 * Recommendations load only when the row is opened. Fetching them for every
 * posting up front would run a ranking pass over every application on the page
 * to show three names the user may never look at.
 */
export default function ManagedJobRow({
  job,
  isOpen,
  onToggle,
  onChanged,
}: ManagedJobRowProps) {
  const [recommendations, setRecommendations] = useState<
    RecommendedApplicant[] | null
  >(null)
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // Which applicant's message box is open, and what has been sent this session.
  const [messagingId, setMessagingId] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [sentTo, setSentTo] = useState<string[]>([])

  const panelId = `managed-panel-${job.id}`

  async function handleToggle() {
    onToggle()

    if (isOpen || recommendations !== null) return

    setIsLoadingRecommendations(true)
    try {
      const page = await request<RecommendationPage>(
        `/jobs/${job.id}/recommendations`,
        { params: { limit: 3 } },
      )
      setRecommendations(page.items)
    } catch {
      // A failed ranking should not take the row's actions down with it, so
      // this degrades to "none" rather than surfacing as a page error.
      setRecommendations([])
    } finally {
      setIsLoadingRecommendations(false)
    }
  }

  async function togglePublished() {
    setError(null)
    setBusy(true)
    try {
      await request(`/jobs/${job.id}`, {
        method: 'PATCH',
        body: { is_published: !job.is_published },
      })
      onChanged()
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : 'Could not update the role.',
      )
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    const confirmed = window.confirm(
      `Delete “${job.title}”? Any applications to it are removed too. This cannot be undone.`,
    )
    if (!confirmed) return

    setError(null)
    setBusy(true)
    try {
      await request(`/jobs/${job.id}`, { method: 'DELETE' })
      onChanged()
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : 'Could not delete the role.',
      )
    } finally {
      setBusy(false)
    }
  }

  async function sendMessage(applicationId: string) {
    if (!message.trim()) {
      setError('Write a message before sending.')
      return
    }

    setError(null)
    setBusy(true)
    try {
      await request(`/applications/${applicationId}/contact`, {
        method: 'POST',
        body: { message },
      })
      setSentTo((current) => [...current, applicationId])
      setMessagingId(null)
      setMessage('')
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : 'Could not send the message.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className="overflow-hidden rounded-xl border border-[color:var(--border)] bg-white shadow-sm">
      <h3 className="m-0">
        <button
          type="button"
          onClick={() => void handleToggle()}
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
              {job.location} · {EMPLOYMENT_TYPE_LABELS[job.employment_type]}
            </span>
          </span>

          <span className="flex shrink-0 items-center gap-3">
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                job.is_published
                  ? 'bg-emerald-50 text-emerald-700'
                  : 'bg-slate-100 text-slate-600'
              }`}
            >
              {job.is_published ? 'Published' : 'Draft'}
            </span>
            <span
              aria-hidden="true"
              className={`text-[color:var(--text-muted)] transition-transform ${
                isOpen ? 'rotate-180' : ''
              }`}
            >
              ▾
            </span>
          </span>
        </button>
      </h3>

      {isOpen && (
        <div
          id={panelId}
          className="border-t border-[color:var(--border)] px-5 py-4"
        >
          {error && (
            <p
              role="alert"
              className="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              {error}
            </p>
          )}

          <div className="mb-5 flex flex-wrap gap-2">
            <Link
              to={`/manage/${job.id}/applicants`}
              className="rounded-lg border border-[color:var(--border)] bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 no-underline transition hover:bg-slate-50"
            >
              All applicants
            </Link>
            <Link
              to={`/manage/${job.id}/edit`}
              className="rounded-lg border border-[color:var(--border)] bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 no-underline transition hover:bg-slate-50"
            >
              Edit
            </Link>
            <button
              type="button"
              onClick={() => void togglePublished()}
              disabled={busy}
              className="rounded-lg border border-[color:var(--border)] bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
            >
              {job.is_published ? 'Unpublish' : 'Publish'}
            </button>
            <button
              type="button"
              onClick={() => void remove()}
              disabled={busy}
              className="rounded-lg bg-[color:var(--danger)] px-3 py-1.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
            >
              Delete
            </button>
          </div>

          <div>
            <h4 className="m-0 text-sm font-semibold uppercase tracking-wide text-[color:var(--text-muted)]">
              Top matches
            </h4>
            <p className="mt-1 text-xs text-[color:var(--text-muted)]">
              Ranked by keyword overlap between the cover letter and this
              posting — a shortlist aid, not an assessment.
            </p>

            {isLoadingRecommendations && (
              <p className="mt-3 text-sm text-[color:var(--text-muted)]">
                Ranking applicants…
              </p>
            )}

            {!isLoadingRecommendations && recommendations?.length === 0 && (
              <p className="mt-3 text-sm text-[color:var(--text-muted)]">
                No applications to rank yet.
              </p>
            )}

            <ul className="mt-3 grid list-none gap-3 pl-0">
              {(recommendations ?? []).map(
                ({ application, score, matched_terms }) => (
                  <li
                    key={application.id}
                    className="rounded-lg border border-[color:var(--border)] bg-slate-50 p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-slate-900">
                        {application.candidate.full_name}
                      </span>
                      <span className="rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-[color:var(--accent)]">
                        {Math.round(score * 100)}% match
                      </span>
                    </div>

                    <p className="mt-1 text-xs text-[color:var(--text-muted)]">
                      {application.candidate.email}
                    </p>

                    {matched_terms.length > 0 && (
                      <p className="mt-2 flex flex-wrap gap-1">
                        {matched_terms.slice(0, 8).map((term) => (
                          <span
                            key={term}
                            className="rounded bg-white px-1.5 py-0.5 text-xs text-slate-600"
                          >
                            {term}
                          </span>
                        ))}
                      </p>
                    )}

                    {sentTo.includes(application.id) ? (
                      <p className="mt-3 text-sm font-medium text-emerald-700">
                        Message sent — it appears in their notifications.
                      </p>
                    ) : messagingId === application.id ? (
                      <div className="mt-3">
                        <label
                          htmlFor={`msg-${application.id}`}
                          className="block text-xs font-semibold text-slate-700"
                        >
                          Message to {application.candidate.full_name}
                        </label>
                        <textarea
                          id={`msg-${application.id}`}
                          value={message}
                          maxLength={2000}
                          onChange={(event) => setMessage(event.target.value)}
                          placeholder="We'd like to invite you to a first interview…"
                          className="mt-1 min-h-20 w-full rounded-lg border border-[color:var(--border)] px-3 py-2 text-sm"
                        />
                        <div className="mt-2 flex gap-2">
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => void sendMessage(application.id)}
                            className="rounded-lg bg-[color:var(--accent)] px-3 py-1.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
                          >
                            {busy ? 'Sending…' : 'Send'}
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setMessagingId(null)
                              setMessage('')
                            }}
                            className="rounded-lg border border-[color:var(--border)] bg-white px-3 py-1.5 text-sm font-semibold text-slate-700"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          setMessagingId(application.id)
                          setMessage('')
                        }}
                        className="mt-3 rounded-lg border border-[color:var(--border)] bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                      >
                        Contact applicant
                      </button>
                    )}
                  </li>
                ),
              )}
            </ul>
          </div>
        </div>
      )}
    </li>
  )
}
