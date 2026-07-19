import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import AsyncBoundary from '../components/AsyncBoundary'
import FormField, { FormAlert } from '../components/form/FormField'
import {
  COMPANY_MAX_LENGTH,
  JOB_DESCRIPTION_MAX_LENGTH,
  JOB_TITLE_MAX_LENGTH,
  LOCATION_MAX_LENGTH,
} from '../constants'
import { useApiResource } from '../hooks/useApiResource'
import { ApiError, request } from '../lib/api'
import { EMPLOYMENT_TYPE_LABELS, type EmploymentType, type Job } from '../types'

type Draft = {
  title: string
  company: string
  location: string
  employment_type: EmploymentType
  description: string
  is_published: boolean
}

const EMPTY: Draft = {
  title: '',
  company: '',
  location: '',
  employment_type: 'FULL_TIME',
  description: '',
  is_published: true,
}

type Errors = Partial<Record<keyof Draft, string>>

/** Required text fields, with the limit each must respect. */
const REQUIRED: { name: keyof Draft; label: string; max: number }[] = [
  { name: 'title', label: 'Title', max: JOB_TITLE_MAX_LENGTH },
  { name: 'company', label: 'Company', max: COMPANY_MAX_LENGTH },
  { name: 'location', label: 'Location', max: LOCATION_MAX_LENGTH },
  { name: 'description', label: 'Description', max: JOB_DESCRIPTION_MAX_LENGTH },
]

/** Validate client-side so the user is told before a round trip, not after. */
function validate(draft: Draft): Errors {
  const errors: Errors = {}

  for (const { name, label, max } of REQUIRED) {
    const value = String(draft[name])
    if (!value.trim()) errors[name] = `${label} is required.`
    else if (value.length > max)
      errors[name] = `${label} must be at most ${max} characters.`
  }

  return errors
}

/**
 * Create or edit a posting.
 *
 * One component for both: the fields and rules are identical, so a separate
 * edit screen would be the same form with two lines changed, plus one more
 * place to forget a validation rule.
 */
export default function JobFormPage() {
  const { jobId } = useParams<{ jobId: string }>()
  const isEditing = Boolean(jobId)
  const navigate = useNavigate()

  const existing = useApiResource<Job>(isEditing ? `/jobs/${jobId}` : '/jobs')
  const [draft, setDraft] = useState<Draft>(EMPTY)
  const [errors, setErrors] = useState<Errors>({})
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    if (!isEditing || !existing.data) return

    const { title, company, location, employment_type, description, is_published } =
      existing.data
    setDraft({ title, company, location, employment_type, description, is_published })
  }, [isEditing, existing.data])

  function set<K extends keyof Draft>(field: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [field]: value }))
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    const found = validate(draft)
    setErrors(found)
    if (Object.keys(found).length > 0) return

    setIsSubmitting(true)
    try {
      await request<Job>(isEditing ? `/jobs/${jobId}` : '/jobs', {
        method: isEditing ? 'PATCH' : 'POST',
        body: draft,
      })
      navigate('/manage', { replace: true })
    } catch (cause) {
      // The server validated the same input with the authoritative rules, so
      // its per-field messages win over the client's.
      if (cause instanceof ApiError) {
        setErrors(cause.fieldErrors as Errors)
        setError(Object.keys(cause.fieldErrors).length > 0 ? null : cause.message)
      } else {
        setError('Could not save the role. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="mx-auto max-w-2xl">
      <p>
        <Link to="/manage">← Back to my postings</Link>
      </p>

      <AsyncBoundary
        isLoading={isEditing && existing.isLoading}
        error={isEditing ? existing.error : null}
      >
        <form
          className="rounded-xl border border-[color:var(--border)] bg-white p-5 shadow-sm"
          onSubmit={handleSubmit}
          noValidate
        >
          <h1 className="text-xl font-bold text-slate-900">
            {isEditing ? 'Edit role' : 'Post a role'}
          </h1>

          <FormAlert message={error} />

          <FormField
            id="title"
            label="Title"
            value={draft.title}
            error={errors.title}
            maxLength={JOB_TITLE_MAX_LENGTH}
            onChange={(value) => set('title', value)}
            required
          />
          <FormField
            id="company"
            label="Company"
            value={draft.company}
            error={errors.company}
            maxLength={COMPANY_MAX_LENGTH}
            placeholder="Who is hiring for this role?"
            onChange={(value) => set('company', value)}
            required
          />
          <FormField
            id="location"
            label="Location"
            value={draft.location}
            error={errors.location}
            maxLength={LOCATION_MAX_LENGTH}
            placeholder="Remote, Berlin, Bangalore…"
            onChange={(value) => set('location', value)}
            required
          />
          <FormField
            id="employment_type"
            label="Employment type"
            value={draft.employment_type}
            options={Object.entries(EMPLOYMENT_TYPE_LABELS).map(
              ([value, label]) => ({ value, label }),
            )}
            onChange={(value) => set('employment_type', value as EmploymentType)}
          />
          <FormField
            id="description"
            label="Description"
            value={draft.description}
            error={errors.description}
            maxLength={JOB_DESCRIPTION_MAX_LENGTH}
            multiline
            placeholder="What the role involves, and what you are looking for."
            onChange={(value) => set('description', value)}
            required
          />

          <label className="mb-4 flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={draft.is_published}
              onChange={(event) => set('is_published', event.target.checked)}
            />
            Publish immediately
          </label>
          <p className="mb-4 -mt-3 text-xs text-[color:var(--text-muted)]">
            Unpublished roles stay private to you and accept no applications.
          </p>

          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-lg bg-[color:var(--accent)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
          >
            {isSubmitting ? 'Saving…' : isEditing ? 'Save changes' : 'Post role'}
          </button>
        </form>
      </AsyncBoundary>
    </section>
  )
}
