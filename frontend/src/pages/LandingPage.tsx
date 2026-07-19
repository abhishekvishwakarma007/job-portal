import { Link } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'
import { useApiResource } from '../hooks/useApiResource'
import { EMPLOYMENT_TYPE_LABELS, type Job, type Page } from '../types'

/**
 * Public landing page.
 *
 * Built with Tailwind utilities rather than the hand-written CSS the older
 * screens use — Tailwind runs with preflight disabled, so the two coexist and
 * this page can be styled independently without disturbing them.
 *
 * Shows real postings rather than placeholder marketing copy: the point of the
 * page is to get someone into the product, and live roles do that better than
 * a stock illustration.
 */
export default function LandingPage() {
  const { user } = useAuth()
  const { data } = useApiResource<Page<Job>>('/jobs', { limit: 3 })

  const featured = data?.items ?? []
  const total = data?.total ?? 0

  return (
    <div className="-mx-4 -mt-4">
      {/* Hero */}
      <section className="border-b border-[color:var(--border)] bg-gradient-to-b from-slate-50 to-white px-4 py-20">
        <div className="mx-auto max-w-3xl text-center">
          <span className="inline-block rounded-full border border-[color:var(--border)] bg-white px-3 py-1 text-xs font-semibold uppercase tracking-wide text-[color:var(--text-muted)]">
            Hiring, without the noise
          </span>

          <h1 className="mt-6 text-4xl font-bold leading-tight tracking-tight text-slate-900 sm:text-5xl">
            Find the role that
            <span className="text-[color:var(--accent)]"> actually fits</span>
          </h1>

          <p className="mx-auto mt-5 max-w-xl text-lg text-[color:var(--text-muted)]">
            {total > 0
              ? `${total} open ${total === 1 ? 'role' : 'roles'} from teams hiring right now.`
              : 'A job portal connecting hiring teams with candidates.'}{' '}
            Browse openings, apply in one step, and follow every application
            from submitted to offer.
          </p>

          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/jobs"
              className="rounded-lg bg-[color:var(--accent)] px-6 py-3 text-base font-semibold text-white no-underline transition hover:opacity-90"
            >
              Browse open roles
            </Link>

            {!user && (
              <Link
                to="/register"
                className="rounded-lg border border-[color:var(--border)] bg-white px-6 py-3 text-base font-semibold text-slate-900 no-underline transition hover:bg-slate-50"
              >
                Create an account
              </Link>
            )}
          </div>
        </div>
      </section>

      {/* Two audiences, stated plainly */}
      <section className="px-4 py-16">
        <div className="mx-auto grid max-w-4xl gap-6 sm:grid-cols-2">
          {[
            {
              title: 'For candidates',
              body: 'Search open roles, apply with a cover letter, and track every application as it moves through review.',
              points: ['One-click apply', 'Live status tracking', 'No duplicate applications'],
            },
            {
              title: 'For hiring teams',
              body: 'Post a role in under a minute, keep drafts private until ready, and review every applicant in one place.',
              points: ['Drafts stay private', 'Applicant pipeline', 'Full control of your postings'],
            },
          ].map((card) => (
            <div
              key={card.title}
              className="rounded-xl border border-[color:var(--border)] bg-white p-7 shadow-sm"
            >
              <h2 className="text-lg font-semibold text-slate-900">
                {card.title}
              </h2>
              <p className="mt-2 text-[color:var(--text-muted)]">{card.body}</p>
              <ul className="mt-4 space-y-2 pl-0">
                {card.points.map((point) => (
                  <li
                    key={point}
                    className="flex items-start gap-2 text-sm text-slate-700"
                  >
                    <span
                      aria-hidden="true"
                      className="mt-1 inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[color:var(--accent)]"
                    />
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* Live roles, only when there are some */}
      {featured.length > 0 && (
        <section className="border-t border-[color:var(--border)] bg-slate-50 px-4 py-16">
          <div className="mx-auto max-w-4xl">
            <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
              <h2 className="text-xl font-semibold text-slate-900">
                Latest openings
              </h2>
              <Link
                to="/jobs"
                className="text-sm font-medium text-[color:var(--accent)]"
              >
                View all {total} →
              </Link>
            </div>

            <ul className="grid gap-3 pl-0">
              {featured.map((job) => (
                <li key={job.id}>
                  <Link
                    to={`/jobs/${job.id}`}
                    className="block rounded-xl border border-[color:var(--border)] bg-white p-5 no-underline shadow-sm transition hover:border-[color:var(--accent)]"
                  >
                    <p className="font-semibold text-slate-900">{job.title}</p>
                    <p className="mt-1 text-sm text-[color:var(--text-muted)]">
                      {job.location} ·{' '}
                      {EMPLOYMENT_TYPE_LABELS[job.employment_type]} ·{' '}
                      {job.created_by.full_name}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}
    </div>
  )
}
