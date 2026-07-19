import { useEffect, useState } from 'react'

import { ApiError, request } from '../lib/api'
import { EMPLOYMENT_TYPE_LABELS, type Job, type Page } from '../types'

/**
 * Public job browse.
 *
 * Every fetch has three renderable outcomes — loading, failed, empty — and all
 * three are handled explicitly. A page that only renders the success case shows
 * a blank screen when the API is down, which reads as a broken build rather
 * than a backend that is not up yet.
 */
export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Aborted on unmount so a slow response cannot call setState afterwards.
    const controller = new AbortController()

    async function load() {
      setIsLoading(true)
      setError(null)

      try {
        const page = await request<Page<Job>>('/jobs', {
          signal: controller.signal,
        })
        setJobs(page.items)
        setTotal(page.total)
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setError(
          cause instanceof ApiError
            ? cause.message
            : 'Could not load jobs. Please try again.',
        )
      } finally {
        if (!controller.signal.aborted) setIsLoading(false)
      }
    }

    void load()
    return () => controller.abort()
  }, [])

  return (
    <section className="stack">
      <div className="row row--between">
        <h1>Open roles</h1>
        {!isLoading && !error && (
          <p className="muted">
            {total} {total === 1 ? 'role' : 'roles'}
          </p>
        )}
      </div>

      {isLoading && <p className="muted">Loading roles…</p>}

      {error && (
        <p className="alert alert--error" role="alert">
          {error}
        </p>
      )}

      {!isLoading && !error && jobs.length === 0 && (
        <div className="card empty">
          <p>No roles have been posted yet.</p>
        </div>
      )}

      {jobs.length > 0 && (
        <ul className="job-list">
          {jobs.map((job) => (
            <li key={job.id} className="card">
              <h2 className="job-card__title">{job.title}</h2>
              <p className="muted">
                {job.location} · {EMPLOYMENT_TYPE_LABELS[job.employment_type]}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
