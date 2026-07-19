import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import AsyncBoundary from '../components/AsyncBoundary'
import { useApiResource } from '../hooks/useApiResource'
import { EMPLOYMENT_TYPE_LABELS, type Job, type Page } from '../types'

/** Public job browse with title search. */
export default function JobsPage() {
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')

  // Debounced so typing does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput.trim()), 300)
    return () => clearTimeout(timer)
  }, [searchInput])

  const { data, isLoading, error } = useApiResource<Page<Job>>('/jobs', {
    search: search || undefined,
  })

  const jobs = data?.items ?? []

  return (
    <section className="stack">
      <div className="row row--between">
        <h1>Open roles</h1>
        {data && !isLoading && (
          <p className="muted">
            {data.total} {data.total === 1 ? 'role' : 'roles'}
          </p>
        )}
      </div>

      <div className="card">
        <label htmlFor="search" className="sr-only">
          Search roles by title
        </label>
        <input
          id="search"
          type="search"
          placeholder="Search by title…"
          value={searchInput}
          onChange={(event) => setSearchInput(event.target.value)}
        />
      </div>

      <AsyncBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={jobs.length === 0}
        emptyMessage={
          search
            ? `No roles match “${search}”.`
            : 'No roles have been posted yet.'
        }
      >
        <ul className="job-list">
          {jobs.map((job) => (
            <li key={job.id} className="card">
              <h2 className="job-card__title">
                <Link to={`/jobs/${job.id}`}>{job.title}</Link>
              </h2>
              <p className="muted">
                {job.location} · {EMPLOYMENT_TYPE_LABELS[job.employment_type]} ·
                posted by {job.created_by.full_name}
              </p>
            </li>
          ))}
        </ul>
      </AsyncBoundary>
    </section>
  )
}
