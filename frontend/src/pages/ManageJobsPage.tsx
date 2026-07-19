import { useState } from 'react'
import { Link } from 'react-router-dom'

import AsyncBoundary from '../components/AsyncBoundary'
import ManagedJobRow from '../components/ManagedJobRow'
import { useApiResource } from '../hooks/useApiResource'
import type { Job, Page } from '../types'

/** An HR user's own postings, drafts included, as an expandable list. */
export default function ManageJobsPage() {
  const { data, isLoading, error, reload } =
    useApiResource<Page<Job>>('/jobs/mine')
  const [openId, setOpenId] = useState<string | null>(null)

  const jobs = data?.items ?? []

  return (
    <section className="mx-auto max-w-4xl">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            My postings
          </h1>
          {data && !isLoading && (
            <p className="mt-1 text-sm text-[color:var(--text-muted)]">
              {data.total} {data.total === 1 ? 'posting' : 'postings'}
            </p>
          )}
        </div>

        <Link
          to="/manage/new"
          className="rounded-lg bg-[color:var(--accent)] px-4 py-2 text-sm font-semibold text-white no-underline transition hover:opacity-90"
        >
          Post a role
        </Link>
      </div>

      <AsyncBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={jobs.length === 0}
        emptyMessage="You have not posted any roles yet."
      >
        <ul className="grid list-none gap-3 pl-0">
          {jobs.map((job) => (
            <ManagedJobRow
              key={job.id}
              job={job}
              isOpen={openId === job.id}
              onToggle={() =>
                setOpenId((current) => (current === job.id ? null : job.id))
              }
              onChanged={reload}
            />
          ))}
        </ul>
      </AsyncBoundary>
    </section>
  )
}
