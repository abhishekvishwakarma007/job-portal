import { Link } from 'react-router-dom'

import AsyncBoundary from '../components/AsyncBoundary'
import { useApiResource } from '../hooks/useApiResource'
import { request } from '../lib/api'
import type { Job, NotificationPage } from '../types'

/**
 * The candidate's invites — messages from hiring teams about roles they
 * applied to.
 *
 * Presented as invitation cards rather than a plain message list: each one is
 * about a specific posting, so the card leads with the role and company and
 * puts the recruiter's message underneath. That is what someone scanning ten
 * of these actually needs — which role, from whom, and what to do next.
 *
 * These stand in for email. Nothing is dispatched; an HR user contacting an
 * applicant writes one of these, so a review environment never emits a real
 * message to a real inbox.
 */
export default function NotificationsPage() {
  const { data, isLoading, error, reload } =
    useApiResource<NotificationPage>('/notifications/mine')

  // The postings these invites reference, so a card can name the role and
  // company rather than only echoing a subject line.
  const { data: jobs } = useApiResource<{ items: Job[] }>('/jobs', {
    limit: 100,
  })

  const items = data?.items ?? []
  const jobsById = new Map((jobs?.items ?? []).map((job) => [job.id, job]))

  async function markRead(id: string) {
    await request(`/notifications/${id}/read`, { method: 'PATCH' })
    reload()
  }

  return (
    <section className="mx-auto max-w-3xl">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Invites
          </h1>
          <p className="mt-1 text-sm text-[color:var(--text-muted)]">
            Messages from hiring teams about roles you applied to.
          </p>
        </div>

        {data && !isLoading && data.unread > 0 && (
          <span className="rounded-full bg-[color:var(--accent)] px-3 py-1 text-xs font-semibold text-white">
            {data.unread} new
          </span>
        )}
      </div>

      <AsyncBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={items.length === 0}
        emptyMessage="No invites yet. When a hiring team responds to an application, it appears here."
      >
        <ul className="grid list-none gap-3 pl-0">
          {items.map((notification) => {
            const job = notification.job_id
              ? jobsById.get(notification.job_id)
              : undefined

            return (
              <li
                key={notification.id}
                className={`overflow-hidden rounded-xl border bg-white shadow-sm ${
                  notification.is_read
                    ? 'border-[color:var(--border)]'
                    : 'border-[color:var(--accent)]'
                }`}
              >
                {/* Card head: which role, from where, when. */}
                <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[color:var(--border)] bg-slate-50 px-5 py-3">
                  <div>
                    <p className="m-0 text-base font-semibold text-slate-900">
                      {job ? job.title : notification.subject}
                    </p>
                    {job && (
                      <p className="mt-0.5 text-sm font-medium text-[color:var(--accent)]">
                        {job.company} · {job.location}
                      </p>
                    )}
                  </div>

                  <div className="text-right">
                    {!notification.is_read && (
                      <span className="rounded-full bg-[color:var(--accent)] px-2 py-0.5 text-xs font-semibold text-white">
                        New
                      </span>
                    )}
                    <p className="mt-1 text-xs text-[color:var(--text-muted)]">
                      {new Date(notification.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                <div className="px-5 py-4">
                  <p className="m-0 text-xs font-semibold uppercase tracking-wide text-[color:var(--text-muted)]">
                    Message from the hiring team
                  </p>

                  {/* Text, never HTML — the body is composed from operator
                      input, and injecting it would be stored XSS. */}
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                    {notification.body}
                  </p>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {job && (
                      <Link
                        to={`/jobs/${job.id}`}
                        className="rounded-lg bg-[color:var(--accent)] px-4 py-2 text-sm font-semibold text-white no-underline transition hover:opacity-90"
                      >
                        View role
                      </Link>
                    )}
                    <Link
                      to="/applications"
                      className="rounded-lg border border-[color:var(--border)] bg-white px-4 py-2 text-sm font-semibold text-slate-700 no-underline transition hover:bg-slate-50"
                    >
                      My applications
                    </Link>
                    {!notification.is_read && (
                      <button
                        type="button"
                        onClick={() => void markRead(notification.id)}
                        className="rounded-lg border border-[color:var(--border)] bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                      >
                        Mark as read
                      </button>
                    )}
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      </AsyncBoundary>
    </section>
  )
}
