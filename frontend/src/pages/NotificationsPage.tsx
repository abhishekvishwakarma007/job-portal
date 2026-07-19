import AsyncBoundary from '../components/AsyncBoundary'
import { useApiResource } from '../hooks/useApiResource'
import { request } from '../lib/api'
import type { NotificationPage } from '../types'

/**
 * The candidate's inbox.
 *
 * These stand in for email: an HR user contacting an applicant writes one of
 * these rather than sending mail, so a review environment never emits a real
 * message to a real inbox.
 */
export default function NotificationsPage() {
  const { data, isLoading, error, reload } =
    useApiResource<NotificationPage>('/notifications/mine')

  const items = data?.items ?? []

  async function markRead(id: string) {
    await request(`/notifications/${id}/read`, { method: 'PATCH' })
    reload()
  }

  return (
    <section className="mx-auto max-w-3xl">
      <div className="mb-5">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Notifications
        </h1>
        {data && !isLoading && (
          <p className="mt-1 text-sm text-[color:var(--text-muted)]">
            {data.unread} unread of {data.total}
          </p>
        )}
      </div>

      <AsyncBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={items.length === 0}
        emptyMessage="Nothing yet. Messages from hiring teams appear here."
      >
        <ul className="grid list-none gap-3 pl-0">
          {items.map((notification) => (
            <li
              key={notification.id}
              className={`rounded-xl border bg-white p-5 shadow-sm ${
                notification.is_read
                  ? 'border-[color:var(--border)]'
                  : 'border-[color:var(--accent)]'
              }`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <h2 className="m-0 text-base font-semibold text-slate-900">
                  {notification.subject}
                </h2>
                {!notification.is_read && (
                  <span className="rounded-full bg-[color:var(--accent)] px-2 py-0.5 text-xs font-semibold text-white">
                    New
                  </span>
                )}
              </div>

              <p className="mt-1 text-xs text-[color:var(--text-muted)]">
                {new Date(notification.created_at).toLocaleString()}
              </p>

              {/* Text, never HTML — the body is composed from operator input. */}
              <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                {notification.body}
              </p>

              {!notification.is_read && (
                <button
                  type="button"
                  onClick={() => void markRead(notification.id)}
                  className="mt-3 rounded-lg border border-[color:var(--border)] bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                >
                  Mark as read
                </button>
              )}
            </li>
          ))}
        </ul>
      </AsyncBoundary>
    </section>
  )
}
