import ProfileField from './ProfileField'
import type { Draft, ProfileField as FieldName, SectionSpec } from './sections'

interface ProfileSectionProps {
  spec: SectionSpec
  draft: Draft
  isSaving: boolean
  isSaved: boolean
  onChange: (field: keyof Draft, value: string) => void
  onSave: (section: string, fields: FieldName[]) => void
}

const COLUMN_CLASS: Record<number, string> = {
  2: 'grid gap-3 sm:grid-cols-2',
  3: 'grid gap-3 sm:grid-cols-3',
}

/**
 * One savable block of the profile.
 *
 * Declared at module scope, which is load-bearing rather than stylistic.
 * Nested inside the page it was redefined on every render, so React saw a new
 * component type each time, unmounted the subtree, and destroyed the focused
 * input — one character per click, on the page the README sends a reviewer to.
 */
export default function ProfileSection({
  spec,
  draft,
  isSaving,
  isSaved,
  onChange,
  onSave,
}: ProfileSectionProps) {
  const fields = spec.fields.map((field) => field.name)

  return (
    <section className="rounded-xl border border-[color:var(--border)] bg-white p-5 shadow-sm">
      <div className="mb-3">
        <h2 className="m-0 text-base font-semibold text-slate-900">
          {spec.title}
        </h2>
        {spec.hint && (
          <p className="mt-1 text-xs text-[color:var(--text-muted)]">
            {spec.hint}
          </p>
        )}
      </div>

      <div className={spec.columns ? COLUMN_CLASS[spec.columns] : undefined}>
        {spec.fields.map((field) => (
          <ProfileField
            key={field.name}
            spec={field}
            value={draft[field.name]}
            onChange={onChange}
          />
        ))}
      </div>

      {spec.id === 'skills' && <SkillPreview value={draft.key_skills} />}

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={() => onSave(spec.id, fields)}
          disabled={isSaving}
          className="rounded-lg bg-[color:var(--accent)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
        >
          {isSaving ? 'Saving...' : 'Save'}
        </button>
        {isSaved && (
          <span className="text-sm font-medium text-emerald-700">Saved</span>
        )}
      </div>
    </section>
  )
}

/**
 * The parsed skill list.
 *
 * Shown because the ranking splits this field on commas — seeing the parse is
 * how someone notices a stray comma before it becomes a skill.
 */
function SkillPreview({ value }: { value: string }) {
  const skills = value
    .split(',')
    .map((skill) => skill.trim())
    .filter(Boolean)

  if (skills.length === 0) return null

  return (
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
  )
}
