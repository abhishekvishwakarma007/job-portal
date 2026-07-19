import { Link } from 'react-router-dom'

import AsyncBoundary from '../components/AsyncBoundary'
import StatusBadge from '../components/StatusBadge'
import { useApiResource } from '../hooks/useApiResource'
import type { Application, Page } from '../types'

/** A candidate's own applications and where each one stands. */
export default function MyApplicationsPage() {
  const { data, isLoading, error } = useApiResource<Page<Application>>(
    '/applications/mine',
  )

  const applications = data?.items ?? []

  return (
    <section className="stack">
      <div className="row row--between">
        <h1>My applications</h1>
        {data && !isLoading && (
          <p className="muted">
            {data.total} {data.total === 1 ? 'application' : 'applications'}
          </p>
        )}
      </div>

      <AsyncBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={applications.length === 0}
        emptyMessage="You have not applied to any roles yet."
      >
        <ul className="job-list">
          {applications.map((application) => (
            <li key={application.id} className="card">
              <div className="row row--between">
                <h2 className="job-card__title">
                  <Link to={`/jobs/${application.job.id}`}>
                    {application.job.title}
                  </Link>
                </h2>
                <StatusBadge status={application.status} />
              </div>
              <p className="muted">
                {application.job.location} · applied{' '}
                {new Date(application.created_at).toLocaleDateString()}
              </p>
            </li>
          ))}
        </ul>
      </AsyncBoundary>
    </section>
  )
}
