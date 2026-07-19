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

/** How many matches to rank. Enough to choose from, few enough to scan. */
const SHORTLIST_SIZE = 5

/**
 * A default invite, so contacting someone is one click rather than a blank box.
 *
 * Written to be sendable as-is but obviously worth editing — a recruiter who
 * sends the default verbatim has still said something reasonable, and one who
 * personalises it has a starting point rather than a cursor blinking at them.
 */
function defaultInvite(job: Job): string {
  return (
    `Thanks for applying to ${job.title} at ${job.company}. ` +
    `We have reviewed your application and would like to take it further.\n\n` +
    `Are you available for an introductory call this week? ` +
    `Reply with a couple of times that suit you and we will confirm.`
  )
}

/**
 * One posting in the HR list: summary, and on expand the actions plus a
 * ranked, selectable table of the best-matching applicants.
 *
 * Recommendations load only when the row is opened. Fetching them for every
 * posting up front would run a ranking pass over every application on the page
 * to show names the user may never look at.
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

  const [selected, setSelected] = useState<string[]>([])
  const [isComposing, setIsComposing] = useState(false)
  const [message, setMessage] = useState('')
  const [invited, setInvited] = useState<string[]>([])

  const panelId = `managed-panel-${job.id}`

  async function handleToggle() {
    onToggle()

    if (isOpen || recommendations !== null) return

    setIsLoadingRecommendations(true)
    try {
      const page = await request<RecommendationPage>(
        `/jobs/${job.id}/recommendations`,
        { params: { limit: SHORTLIST_SIZE } },
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

  const selectable = (recommendations ?? []).filter(
    (item) => !invited.includes(item.application.id),
  )
  const allSelected =
    selectable.length > 0 && selected.length === selectable.length

  function toggleAll() {
    setSelected(allSelected ? [] : selectable.map((item) => item.application.id))
  }

  function toggleOne(applicationId: string) {
    setSelected((current) =>
      current.includes(applicationId)
        ? current.filter((id) => id !== applicationId)
        : [...current, applicationId],
    )
  }

  function startComposing() {
    setMessage(defaultInvite(job))
    setIsComposing(true)
    setError(null)
  }

  async function sendInvites() {
    if (!message.trim()) {
      setError('Write a message before sending.')
      return
    }

    setError(null)
    setBusy(true)

    // Sent one at a time and tracked individually: if the fourth of five
    // fails, the first three were genuinely delivered and saying otherwise
    // would be a lie the recruiter acts on.
    const delivered: string[] = []
    const failed: string[] = []

    for (const applicationId of selected) {
      try {
        await request(`/applications/${applicationId}/contact`, {
          method: 'POST',
          body: { message },
        })
        delivered.push(applicationId)
      } catch {
        failed.push(applicationId)
      }
    }

    setInvited((current) => [...current, ...delivered])
    setSelected(failed)
    setIsComposing(failed.length > 0)

    if (failed.length > 0) {
      setError(
        `Sent ${delivered.length}, but ${failed.length} failed. The failed ones are still selected.`,
      )
    }

    setBusy(false)
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
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h4 className="m-0 text-sm font-semibold uppercase tracking-wide text-[color:var(--text-muted)]">
                  Top matches
                </h4>
                <p className="mt-1 text-xs text-[color:var(--text-muted)]">
                  Ranked by keyword overlap between each candidate and this
                  posting — a shortlist aid, not an assessment.
                </p>
              </div>

              {selected.length > 0 && !isComposing && (
                <button
                  type="button"
                  onClick={startComposing}
                  className="rounded-lg bg-[color:var(--accent)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
                >
                  Invite {selected.length} selected
                </button>
              )}
            </div>

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

            {(recommendations ?? []).length > 0 && (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[34rem] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-[color:var(--border)] text-left text-xs uppercase tracking-wide text-[color:var(--text-muted)]">
                      <th scope="col" className="w-10 py-2">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={toggleAll}
                          disabled={selectable.length === 0}
                          aria-label="Select all candidates"
                          className="h-4 w-4"
                        />
                      </th>
                      <th scope="col" className="py-2 pr-3">
                        Candidate
                      </th>
                      <th scope="col" className="py-2 pr-3">
                        Match
                      </th>
                      <th scope="col" className="py-2">
                        Matched on
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {(recommendations ?? []).map(
                      ({ application, score, matched_terms }) => {
                        const isInvited = invited.includes(application.id)

                        return (
                          <tr
                            key={application.id}
                            className="border-b border-[color:var(--border)] align-top last:border-0"
                          >
                            <td className="py-3">
                              <input
                                type="checkbox"
                                checked={selected.includes(application.id)}
                                onChange={() => toggleOne(application.id)}
                                disabled={isInvited}
                                aria-label={`Select ${application.candidate.full_name}`}
                                className="h-4 w-4"
                              />
                            </td>

                            <td className="py-3 pr-3">
                              <span className="block font-semibold text-slate-900">
                                {application.candidate.full_name}
                              </span>
                              <span className="block text-xs text-[color:var(--text-muted)]">
                                {application.candidate.email}
                              </span>
                              {isInvited && (
                                <span className="mt-1 inline-block rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                                  Invited
                                </span>
                              )}
                            </td>

                            <td className="py-3 pr-3">
                              <span className="font-semibold text-[color:var(--accent)]">
                                {Math.round(score * 100)}%
                              </span>
                            </td>

                            <td className="py-3">
                              <span className="flex flex-wrap gap-1">
                                {matched_terms.slice(0, 6).map((term) => (
                                  <span
                                    key={term}
                                    className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600"
                                  >
                                    {term}
                                  </span>
                                ))}
                              </span>
                            </td>
                          </tr>
                        )
                      },
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {isComposing && (
              <div className="mt-4 rounded-lg border border-[color:var(--border)] bg-slate-50 p-4">
                <label
                  htmlFor={`invite-${job.id}`}
                  className="block text-sm font-semibold text-slate-900"
                >
                  Invite {selected.length}{' '}
                  {selected.length === 1 ? 'candidate' : 'candidates'}
                </label>
                <p className="mt-0.5 text-xs text-[color:var(--text-muted)]">
                  Everyone selected receives the same message. Nothing is
                  emailed — it appears in their invites.
                </p>

                <textarea
                  id={`invite-${job.id}`}
                  value={message}
                  maxLength={2000}
                  onChange={(event) => setMessage(event.target.value)}
                  className="mt-2 min-h-32 w-full rounded-lg border border-[color:var(--border)] px-3 py-2 text-sm"
                />

                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busy || selected.length === 0}
                    onClick={() => void sendInvites()}
                    className="rounded-lg bg-[color:var(--accent)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
                  >
                    {busy
                      ? 'Sending…'
                      : `Send ${selected.length} ${
                          selected.length === 1 ? 'invite' : 'invites'
                        }`}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIsComposing(false)
                      setMessage('')
                    }}
                    className="rounded-lg border border-[color:var(--border)] bg-white px-4 py-2 text-sm font-semibold text-slate-700"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </li>
  )
}
