import { useEffect, useState } from 'react'

import AsyncBoundary from '../components/AsyncBoundary'
import JobAccordionItem from '../components/JobAccordionItem'
import { useApiResource } from '../hooks/useApiResource'
import {
  EMPLOYMENT_TYPE_LABELS,
  type EmploymentType,
  type Job,
  type Page,
} from '../types'

/**
 * Public job browse: filter, then expand a row to read the full posting and
 * apply without leaving the list.
 *
 * Filtering happens server-side rather than over an already-fetched page —
 * otherwise the count and the pagination would describe a different set than
 * the one on screen.
 */
export default function JobsPage() {
  const [titleInput, setTitleInput] = useState('')
  const [locationInput, setLocationInput] = useState('')
  const [employmentType, setEmploymentType] = useState<EmploymentType | ''>('')

  const [title, setTitle] = useState('')
  const [location, setLocation] = useState('')

  const [openJobId, setOpenJobId] = useState<string | null>(null)

  // Debounced so typing does not fire a request per keystroke. The select is
  // not debounced — it changes once per interaction.
  useEffect(() => {
    const timer = setTimeout(() => {
      setTitle(titleInput.trim())
      setLocation(locationInput.trim())
    }, 300)
    return () => clearTimeout(timer)
  }, [titleInput, locationInput])

  const { data, isLoading, error } = useApiResource<Page<Job>>('/jobs', {
    search: title || undefined,
    location: location || undefined,
    employment_type: employmentType || undefined,
  })

  const jobs = data?.items ?? []
  const hasFilters = Boolean(title || location || employmentType)

  function clearFilters() {
    setTitleInput('')
    setLocationInput('')
    setEmploymentType('')
  }

  return (
    <section className="mx-auto max-w-4xl">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Open roles
          </h1>
          {data && !isLoading && (
            <p className="mt-1 text-sm text-[color:var(--text-muted)]">
              {data.total} {data.total === 1 ? 'role' : 'roles'}
              {hasFilters ? ' matching your filters' : ''}
            </p>
          )}
        </div>

        {hasFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="rounded-lg border border-[color:var(--border)] bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="mb-5 grid gap-3 rounded-xl border border-[color:var(--border)] bg-white p-4 shadow-sm sm:grid-cols-3">
        <div>
          <label
            htmlFor="filter-title"
            className="block text-xs font-semibold uppercase tracking-wide text-[color:var(--text-muted)]"
          >
            Title
          </label>
          <input
            id="filter-title"
            type="search"
            value={titleInput}
            onChange={(event) => setTitleInput(event.target.value)}
            placeholder="Engineer, designer…"
            className="mt-1 w-full rounded-lg border border-[color:var(--border)] px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label
            htmlFor="filter-location"
            className="block text-xs font-semibold uppercase tracking-wide text-[color:var(--text-muted)]"
          >
            Location
          </label>
          <input
            id="filter-location"
            type="search"
            value={locationInput}
            onChange={(event) => setLocationInput(event.target.value)}
            placeholder="Remote, Berlin…"
            className="mt-1 w-full rounded-lg border border-[color:var(--border)] px-3 py-2 text-sm"
          />
        </div>

        <div>
          <label
            htmlFor="filter-type"
            className="block text-xs font-semibold uppercase tracking-wide text-[color:var(--text-muted)]"
          >
            Employment type
          </label>
          <select
            id="filter-type"
            value={employmentType}
            onChange={(event) =>
              setEmploymentType(event.target.value as EmploymentType | '')
            }
            className="mt-1 w-full rounded-lg border border-[color:var(--border)] px-3 py-2 text-sm"
          >
            <option value="">Any</option>
            {Object.entries(EMPLOYMENT_TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <AsyncBoundary
        isLoading={isLoading}
        error={error}
        isEmpty={jobs.length === 0}
        emptyMessage={
          hasFilters
            ? 'No roles match these filters. Try widening them.'
            : 'No roles have been posted yet.'
        }
      >
        <ul className="grid list-none gap-3 pl-0">
          {jobs.map((job) => (
            <JobAccordionItem
              key={job.id}
              job={job}
              isOpen={openJobId === job.id}
              // One panel at a time: with several open the apply forms scroll
              // past each other and it stops being obvious which one is being
              // submitted.
              onToggle={() =>
                setOpenJobId((current) => (current === job.id ? null : job.id))
              }
            />
          ))}
        </ul>
      </AsyncBoundary>
    </section>
  )
}
