import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import AsyncBoundary from '../components/AsyncBoundary'
import StatusBadge from '../components/StatusBadge'
import { useApiResource } from '../hooks/useApiResource'
import { ApiError, request } from '../lib/api'
import {
  APPLICATION_STATUS_LABELS,
  type Application,
  type ApplicationStatus,
  type Job,
  type Page,
} from '../types'

const STATUSES = Object.keys(APPLICATION_STATUS_LABELS) as ApplicationStatus[]

/** The pipeline for one posting: who applied, and moving them through it. */
export default function JobApplicantsPage() {
  const { jobId } = useParams<{ jobId: string }>()

  const job = useApiResource<Job>(`/jobs/${jobId}`)
  const applications = useApiResource<Page<Application>>(
    `/jobs/${jobId}/applications`,
  )

  const [actionError, setActionError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const items = applications.data?.items ?? []

  async function setStatus(application: Application, status: ApplicationStatus) {
    setActionError(null)
    setBusyId(application.id)

    try {
      await request<Application>(`/applications/${application.id}`, {
        method: 'PATCH',
        body: { status },
      })
      applications.reload()
    } catch (cause) {
      setActionError(
        cause instanceof ApiError
          ? cause.message
          : 'Could not update the application.',
      )
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="stack">
      <p>
        <Link to="/manage">← Back to my postings</Link>
      </p>

      <div className="row row--between">
        <h1>Applicants{job.data ? ` · ${job.data.title}` : ''}</h1>
        {applications.data && !applications.isLoading && (
          <p className="muted">
            {applications.data.total}{' '}
            {applications.data.total === 1 ? 'applicant' : 'applicants'}
          </p>
        )}
      </div>

      {actionError && (
        <p className="alert alert--error" role="alert">
          {actionError}
        </p>
      )}

      <AsyncBoundary
        isLoading={applications.isLoading}
        error={applications.error}
        isEmpty={items.length === 0}
        emptyMessage="No one has applied to this role yet."
      >
        <ul className="job-list">
          {items.map((application) => (
            <li key={application.id} className="card">
              <div className="row row--between">
                <h2 className="job-card__title">
                  {application.candidate.full_name}
                </h2>
                <StatusBadge status={application.status} />
              </div>

              <p className="muted">
                {application.candidate.email} · applied{' '}
                {new Date(application.created_at).toLocaleDateString()}
              </p>

              {/* Text, never HTML — the cover letter is candidate-supplied. */}
              <p style={{ whiteSpace: 'pre-wrap' }}>
                {application.cover_letter}
              </p>

              <div className="field" style={{ maxWidth: '16rem' }}>
                <label htmlFor={`status-${application.id}`}>
                  Move to
                </label>
                <select
                  id={`status-${application.id}`}
                  value={application.status}
                  disabled={busyId === application.id}
                  onChange={(event) =>
                    void setStatus(
                      application,
                      event.target.value as ApplicationStatus,
                    )
                  }
                >
                  {STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {APPLICATION_STATUS_LABELS[status]}
                    </option>
                  ))}
                </select>
              </div>
            </li>
          ))}
        </ul>
      </AsyncBoundary>
    </section>
  )
}
