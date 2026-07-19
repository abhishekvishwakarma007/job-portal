import { useState } from 'react'
import { Link } from 'react-router-dom'

import { SHORTLIST_SIZE } from '../constants'
import { ApiError, request } from '../lib/api'
import {
  EMPLOYMENT_TYPE_LABELS,
  type Job,
  type RecommendationPage,
  type RecommendedApplicant,
} from '../types'
import InviteComposer from './InviteComposer'
import ShortlistTable from './ShortlistTable'

interface ManagedJobRowProps {
  job: Job
  isOpen: boolean
  onToggle: () => void
  onChanged: () => void
}

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
 * One posting in the HR list: summary, and on expand its actions plus a
 * ranked, selectable shortlist.
 *
 * The table and the message box are separate components — this one owns the
 * state they share (what is selected, what has been invited, whether a request
 * is in flight) and they render it. Keeping that state here is what lets a
 * partial send leave the failures selected.
 *
 * Recommendations load on expand rather than with the page: fetching them for
 * every posting up front would run a ranking pass over every application to
 * show names the user may never look at.
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
  const items = recommendations ?? []

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

  function toggleAll() {
    const selectable = items
      .filter((item) => !invited.includes(item.application.id))
      .map((item) => item.application.id)

    setSelected(selected.length === selectable.length ? [] : selectable)
  }

  function toggleOne(applicationId: string) {
    setSelected((current) =>
      current.includes(applicationId)
        ? current.filter((id) => id !== applicationId)
        : [...current, applicationId],
    )
  }

  async function sendInvites() {
    if (!message.trim()) {
      setError('Write a message before sending.')
      return
    }

    setError(null)
    setBusy(true)

    // Sent one at a time and tracked individually: if the fourth of five
    // fails, the first three were genuinely delivered, and saying otherwise
    // would be a lie the recruiter then acts on.
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
                onClick={() => {
                  setMessage(defaultInvite(job))
                  setIsComposing(true)
                  setError(null)
                }}
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

          {!isLoadingRecommendations && items.length === 0 && (
            <p className="mt-3 text-sm text-[color:var(--text-muted)]">
              No applications to rank yet.
            </p>
          )}

          {items.length > 0 && (
            <ShortlistTable
              items={items}
              selected={selected}
              invited={invited}
              onToggleOne={toggleOne}
              onToggleAll={toggleAll}
            />
          )}

          {isComposing && (
            <InviteComposer
              id={job.id}
              recipientCount={selected.length}
              message={message}
              isSending={busy}
              onChange={setMessage}
              onSend={() => void sendInvites()}
              onCancel={() => {
                setIsComposing(false)
                setMessage('')
              }}
            />
          )}
        </div>
      )}
    </li>
  )
}
