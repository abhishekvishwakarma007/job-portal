import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import AsyncBoundary from '../components/AsyncBoundary'
import { useApiResource } from '../hooks/useApiResource'
import { ApiError, request } from '../lib/api'
import { EMPLOYMENT_TYPE_LABELS, type EmploymentType, type Job } from '../types'

const TITLE_MAX_LENGTH = 200
const COMPANY_MAX_LENGTH = 120
const LOCATION_MAX_LENGTH = 120
const DESCRIPTION_MAX_LENGTH = 20_000

type FieldErrors = Partial<
  Record<'title' | 'company' | 'description' | 'location' | 'employment_type', string>
>

/**
 * Create or edit a posting.
 *
 * One component for both: the fields and rules are identical, and a separate
 * edit screen would be the same form with two lines changed — and one more
 * place to forget a validation rule.
 */
export default function JobFormPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const isEditing = Boolean(jobId)
  const navigate = useNavigate()

  const existing = useApiResource<Job>(isEditing ? `/jobs/${jobId}` : '/jobs')

  const [title, setTitle] = useState('')
  const [company, setCompany] = useState('')
  const [description, setDescription] = useState('')
  const [location, setLocation] = useState('')
  const [employmentType, setEmploymentType] =
    useState<EmploymentType>('FULL_TIME')
  const [isPublished, setIsPublished] = useState(true)

  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Populate once the existing posting arrives.
  useEffect(() => {
    if (!isEditing || !existing.data) return

    const job = existing.data
    setTitle(job.title)
    setCompany(job.company)
    setDescription(job.description)
    setLocation(job.location)
    setEmploymentType(job.employment_type)
    setIsPublished(job.is_published)
  }, [isEditing, existing.data])

  function validate(): FieldErrors {
    const errors: FieldErrors = {}

    if (!company.trim()) errors.company = 'Company is required.'
    else if (company.length > COMPANY_MAX_LENGTH)
      errors.company = `Company must be at most ${COMPANY_MAX_LENGTH} characters.`

    if (!title.trim()) errors.title = 'Title is required.'
    else if (title.length > TITLE_MAX_LENGTH)
      errors.title = `Title must be at most ${TITLE_MAX_LENGTH} characters.`

    if (!description.trim()) errors.description = 'Description is required.'

    if (!location.trim()) errors.location = 'Location is required.'
    else if (location.length > LOCATION_MAX_LENGTH)
      errors.location = `Location must be at most ${LOCATION_MAX_LENGTH} characters.`

    return errors
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    const errors = validate()
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return

    setIsSubmitting(true)

    const body = {
      title,
      company,
      description,
      location,
      employment_type: employmentType,
      is_published: isPublished,
    }

    try {
      if (isEditing) {
        await request<Job>(`/jobs/${jobId}`, { method: 'PATCH', body })
      } else {
        await request<Job>('/jobs', { method: 'POST', body })
      }
      navigate('/manage', { replace: true })
    } catch (cause) {
      if (cause instanceof ApiError) {
        setFieldErrors(cause.fieldErrors as FieldErrors)
        setError(
          Object.keys(cause.fieldErrors).length > 0 ? null : cause.message,
        )
      } else {
        setError('Could not save the role. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="stack">
      <p>
        <Link to="/manage">← Back to my postings</Link>
      </p>

      <AsyncBoundary
        isLoading={isEditing && existing.isLoading}
        error={isEditing ? existing.error : null}
      >
        <form className="card" onSubmit={handleSubmit} noValidate>
          <h1>{isEditing ? 'Edit role' : 'Post a role'}</h1>

          {error && (
            <p className="alert alert--error" role="alert">
              {error}
            </p>
          )}

          <div className="field">
            <label htmlFor="title">Title</label>
            <input
              id="title"
              value={title}
              maxLength={TITLE_MAX_LENGTH}
              onChange={(event) => setTitle(event.target.value)}
              aria-invalid={Boolean(fieldErrors.title)}
              required
            />
            {fieldErrors.title && (
              <span className="field__error">{fieldErrors.title}</span>
            )}
          </div>

          <div className="field">
            <label htmlFor="location">Location</label>
            <input
              id="location"
              value={location}
              maxLength={LOCATION_MAX_LENGTH}
              onChange={(event) => setLocation(event.target.value)}
              aria-invalid={Boolean(fieldErrors.location)}
              placeholder="Remote, Berlin, Bangalore…"
              required
            />
            {fieldErrors.location && (
              <span className="field__error">{fieldErrors.location}</span>
            )}
          </div>

          <div className="field">
            <label htmlFor="employment_type">Employment type</label>
            <select
              id="employment_type"
              value={employmentType}
              onChange={(event) =>
                setEmploymentType(event.target.value as EmploymentType)
              }
            >
              {Object.entries(EMPLOYMENT_TYPE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              value={description}
              maxLength={DESCRIPTION_MAX_LENGTH}
              onChange={(event) => setDescription(event.target.value)}
              aria-invalid={Boolean(fieldErrors.description)}
              placeholder="What the role involves, and what you are looking for."
              required
            />
            {fieldErrors.description && (
              <span className="field__error">{fieldErrors.description}</span>
            )}
          </div>

          <div className="field">
            <label className="row" style={{ fontWeight: 400 }}>
              <input
                type="checkbox"
                checked={isPublished}
                onChange={(event) => setIsPublished(event.target.checked)}
                style={{ width: 'auto' }}
              />
              Publish immediately
            </label>
            <span className="field__hint">
              Unpublished roles stay private to you and accept no applications.
            </span>
          </div>

          <button className="button" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Saving…' : isEditing ? 'Save changes' : 'Post role'}
          </button>
        </form>
      </AsyncBoundary>
    </section>
  )
}
