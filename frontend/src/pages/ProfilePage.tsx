import { useEffect, useState, type ReactNode } from 'react'

import AsyncBoundary from '../components/AsyncBoundary'
import { useApiResource } from '../hooks/useApiResource'
import { ApiError, request } from '../lib/api'
import { EMPLOYMENT_TYPE_LABELS, type CandidateProfile } from '../types'

type Draft = Omit<
  CandidateProfile,
  'id' | 'user_id' | 'created_at' | 'updated_at'
>

const EMPTY_DRAFT: Draft = {
  headline: '',
  location: '',
  phone: '',
  summary: '',
  preferred_role: '',
  preferred_location: '',
  preferred_employment_type: '',
  key_skills: '',
  employment: '',
  education: '',
}

const INPUT_CLASS =
  'mt-1 w-full rounded-lg border border-[color:var(--border)] px-3 py-2 text-sm'
const LABEL_CLASS =
  'block text-xs font-semibold uppercase tracking-wide text-[color:var(--text-muted)]'

const EMPLOYMENT_PLACEHOLDER =
  'Platform Engineer, Northwind Labs, 2022-present\nBackend Developer, Acme, 2019-2022'

/**
 * The candidate profile, in the sections a job site asks for.
 *
 * Each section saves on its own. One save button over ten fields means a
 * failure anywhere discards work everywhere, and someone correcting a single
 * skill should not have to re-confirm their whole history.
 *
 * Key skills matter beyond display: they feed the applicant ranking an HR user
 * sees, weighted above prose. The page says so, because effort with no visible
 * payoff does not get made.
 */
export default function ProfilePage() {
  const { data, isLoading, error, reload } =
    useApiResource<CandidateProfile>('/profile/me')

  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT)
  const [savingSection, setSavingSection] = useState<string | null>(null)
  const [savedSection, setSavedSection] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (!data) return

    setDraft({
      headline: data.headline,
      location: data.location,
      phone: data.phone,
      summary: data.summary,
      preferred_role: data.preferred_role,
      preferred_location: data.preferred_location,
      preferred_employment_type: data.preferred_employment_type,
      key_skills: data.key_skills,
      employment: data.employment,
      education: data.education,
    })
  }, [data])

  function set<K extends keyof Draft>(field: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [field]: value }))
    setSavedSection(null)
  }

  async function saveSection(section: string, fields: (keyof Draft)[]) {
    setSaveError(null)
    setSavingSection(section)

    // Only this section's fields are sent, so a save can never overwrite a
    // section the user was not editing with whatever local state held.
    const body = Object.fromEntries(fields.map((field) => [field, draft[field]]))

    try {
      await request<CandidateProfile>('/profile/me', { method: 'PATCH', body })
      setSavedSection(section)
      reload()
    } catch (cause) {
      setSaveError(
        cause instanceof ApiError ? cause.message : 'Could not save. Try again.',
      )
    } finally {
      setSavingSection(null)
    }
  }

  function Section({
    id,
    title,
    hint,
    fields,
    children,
  }: {
    id: string
    title: string
    hint?: string
    fields: (keyof Draft)[]
    children: ReactNode
  }) {
    return (
      <section className="rounded-xl border border-[color:var(--border)] bg-white p-5 shadow-sm">
        <div className="mb-3">
          <h2 className="m-0 text-base font-semibold text-slate-900">{title}</h2>
          {hint && (
            <p className="mt-1 text-xs text-[color:var(--text-muted)]">{hint}</p>
          )}
        </div>

        {children}

        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={() => void saveSection(id, fields)}
            disabled={savingSection === id}
            className="rounded-lg bg-[color:var(--accent)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
          >
            {savingSection === id ? 'Saving...' : 'Save'}
          </button>
          {savedSection === id && (
            <span className="text-sm font-medium text-emerald-700">Saved</span>
          )}
        </div>
      </section>
    )
  }

  const skills = draft.key_skills
    .split(',')
    .map((skill) => skill.trim())
    .filter(Boolean)

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">
        My profile
      </h1>
      <p className="mt-1 text-sm text-[color:var(--text-muted)]">
        Hiring teams see your skills and summary when ranking applicants, so a
        fuller profile puts you higher on their shortlist.
      </p>

      {saveError && (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {saveError}
        </p>
      )}

      <AsyncBoundary isLoading={isLoading} error={error}>
        <div className="mt-5 grid gap-4">
          <Section
            id="basic"
            title="Basic details"
            fields={['headline', 'location', 'phone']}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className={LABEL_CLASS} htmlFor="headline">
                  Headline
                </label>
                <input
                  id="headline"
                  className={INPUT_CLASS}
                  value={draft.headline}
                  onChange={(event) => set('headline', event.target.value)}
                  placeholder="Senior Platform Engineer"
                />
              </div>
              <div>
                <label className={LABEL_CLASS} htmlFor="location">
                  Current location
                </label>
                <input
                  id="location"
                  className={INPUT_CLASS}
                  value={draft.location}
                  onChange={(event) => set('location', event.target.value)}
                  placeholder="Bangalore"
                />
              </div>
              <div>
                <label className={LABEL_CLASS} htmlFor="phone">
                  Phone
                </label>
                <input
                  id="phone"
                  className={INPUT_CLASS}
                  value={draft.phone}
                  onChange={(event) => set('phone', event.target.value)}
                  placeholder="+91 98765 43210"
                />
              </div>
            </div>
          </Section>

          <Section
            id="summary"
            title="Profile summary"
            hint="Two or three sentences. Read when a hiring team ranks you."
            fields={['summary']}
          >
            <textarea
              className={`${INPUT_CLASS} min-h-24`}
              value={draft.summary}
              onChange={(event) => set('summary', event.target.value)}
              placeholder="What you do, what you are good at, and what you are looking for."
            />
          </Section>

          <Section
            id="skills"
            title="Key skills"
            hint="Comma separated. Weighted above prose when applicants are ranked."
            fields={['key_skills']}
          >
            <input
              className={INPUT_CLASS}
              value={draft.key_skills}
              onChange={(event) => set('key_skills', event.target.value)}
              placeholder="Python, FastAPI, Postgres, Docker"
            />
            {skills.length > 0 && (
              <p className="mt-2 flex flex-wrap gap-1">
                {skills.map((skill) => (
                  <span
                    key={skill}
                    className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700"
                  >
                    {skill}
                  </span>
                ))}
              </p>
            )}
          </Section>

          <Section
            id="preferences"
            title="Career preferences"
            fields={[
              'preferred_role',
              'preferred_location',
              'preferred_employment_type',
            ]}
          >
            <div className="grid gap-3 sm:grid-cols-3">
              <div>
                <label className={LABEL_CLASS} htmlFor="preferred_role">
                  Preferred role
                </label>
                <input
                  id="preferred_role"
                  className={INPUT_CLASS}
                  value={draft.preferred_role}
                  onChange={(event) => set('preferred_role', event.target.value)}
                  placeholder="Backend Engineer"
                />
              </div>
              <div>
                <label className={LABEL_CLASS} htmlFor="preferred_location">
                  Preferred location
                </label>
                <input
                  id="preferred_location"
                  className={INPUT_CLASS}
                  value={draft.preferred_location}
                  onChange={(event) =>
                    set('preferred_location', event.target.value)
                  }
                  placeholder="Remote"
                />
              </div>
              <div>
                <label
                  className={LABEL_CLASS}
                  htmlFor="preferred_employment_type"
                >
                  Employment type
                </label>
                <select
                  id="preferred_employment_type"
                  className={INPUT_CLASS}
                  value={draft.preferred_employment_type}
                  onChange={(event) =>
                    set('preferred_employment_type', event.target.value)
                  }
                >
                  <option value="">No preference</option>
                  {Object.entries(EMPLOYMENT_TYPE_LABELS).map(([value, l]) => (
                    <option key={value} value={value}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </Section>

          <Section
            id="employment"
            title="Employment"
            hint="One role per line: title, company, dates."
            fields={['employment']}
          >
            <textarea
              className={`${INPUT_CLASS} min-h-24`}
              value={draft.employment}
              onChange={(event) => set('employment', event.target.value)}
              placeholder={EMPLOYMENT_PLACEHOLDER}
            />
          </Section>

          <Section
            id="education"
            title="Education"
            hint="One qualification per line."
            fields={['education']}
          >
            <textarea
              className={`${INPUT_CLASS} min-h-20`}
              value={draft.education}
              onChange={(event) => set('education', event.target.value)}
              placeholder="B.Tech Computer Science, IIT Delhi, 2019"
            />
          </Section>
        </div>
      </AsyncBoundary>
    </div>
  )
}
