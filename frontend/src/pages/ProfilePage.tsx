import AsyncBoundary from '../components/AsyncBoundary'
import ProfileSection from '../profile/ProfileSection'
import { PROFILE_SECTIONS } from '../profile/sections'
import { useProfileDraft } from '../profile/useProfileDraft'

/**
 * The candidate profile, in the sections a job site asks for.
 *
 * The page renders; useProfileDraft decides. Sections are described as data in
 * ../profile/sections, so adding a field is one entry there rather than
 * another block of near-identical JSX here — which is how this reached 287
 * lines the first time.
 *
 * Key skills matter beyond display: they feed the applicant ranking an HR user
 * sees, weighted above prose. The page says so, because effort with no visible
 * payoff does not get made.
 */
export default function ProfilePage() {
  const profile = useProfileDraft()

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">
        My profile
      </h1>
      <p className="mt-1 text-sm text-[color:var(--text-muted)]">
        Hiring teams see your skills and summary when ranking applicants, so a
        fuller profile puts you higher on their shortlist.
      </p>

      {profile.saveError && (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {profile.saveError}
        </p>
      )}

      <AsyncBoundary isLoading={profile.isLoading} error={profile.error}>
        <div className="mt-5 grid gap-4">
          {PROFILE_SECTIONS.map((spec) => (
            <ProfileSection
              key={spec.id}
              spec={spec}
              draft={profile.draft}
              isSaving={profile.savingSection === spec.id}
              isSaved={profile.savedSection === spec.id}
              onChange={profile.setField}
              onSave={profile.saveSection}
            />
          ))}
        </div>
      </AsyncBoundary>
    </div>
  )
}
