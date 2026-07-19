import { useState } from 'react'
import { Link } from 'react-router-dom'

import AsyncBoundary from '../components/AsyncBoundary'
import { useApiResource } from '../hooks/useApiResource'
import { ApiError, request } from '../lib/api'
import { EMPLOYMENT_TYPE_LABELS, type Job, type Page } from '../types'

/** An HR user's own postings, drafts included. */
export default function ManageJobsPage() {
  const { data, isLoading, error, reload } =
    useApiResource<Page<Job>>('/jobs/mine')
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const jobs = data?.items ?? []

  async function togglePublished(job: Job) {
    setActionError(null)
    setBusyId(job.id)

    try {
      await request<Job>(`/jobs/${job.id}`, {
        method: 'PATCH',
        body: { is_published: !job.is_published },
      })
      reload()
    } catch (cause) {
      setActionError(
        cause instanceof ApiError ? cause.message : 'Could not update the role.',
      )
    } finally {
      setBusyId(null)
    }
  }

  async function remove(job: Job) {
    // Deleting cascades to every application on the posting, so the warning
    // says so rather than asking a bare "are you sure?".
    const confirmed = window.confirm(
      `Delete “${job.title}”? Any applications to it are removed too. This cannot be undone.`,
    )
    if (!confirmed) return

    setActionError(null)
    setBusyId(job.id)

    try {
      await request<void>(`/jobs/${job.id}`, { method: 'DELETE' })
      reload()
    } catch (cause) {
      setActionError(
        cause instanceof ApiError ? cause.message : 'Could not delete the role.',
      )
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="stack">
      <div className="row row--between">
        <h1>My postings</h1>
        <Link to="/manage/new" className="button">
          Post a role
        </Link>
      </div>

      {actionError && (
        <p className="alert alert--error" role="alert">
          {actionError}
        </p>
      )}

      <AsyncBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={jobs.length === 0}
        emptyMessage="You have not posted any roles yet."
      >
        <ul className="job-list">
          {jobs.map((job) => (
            <li key={job.id} className="card">
              <div className="row row--between">
                <h2 className="job-card__title">
                  <Link to={`/jobs/${job.id}`}>{job.title}</Link>
                </h2>
                <span
                  className={`badge ${
                    job.is_published ? 'badge--success' : 'badge--neutral'
                  }`}
                >
                  {job.is_published ? 'Published' : 'Draft'}
                </span>
              </div>

              <p className="muted">
                {job.location} · {EMPLOYMENT_TYPE_LABELS[job.employment_type]}
              </p>

              <div className="row">
                <Link
                  to={`/manage/${job.id}/applicants`}
                  className="button button--secondary"
                >
                  View applicants
                </Link>
                <Link
                  to={`/manage/${job.id}/edit`}
                  className="button button--secondary"
                >
                  Edit
                </Link>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => void togglePublished(job)}
                  disabled={busyId === job.id}
                >
                  {job.is_published ? 'Unpublish' : 'Publish'}
                </button>
                <button
                  type="button"
                  className="button button--danger"
                  onClick={() => void remove(job)}
                  disabled={busyId === job.id}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      </AsyncBoundary>
    </section>
  )
}
