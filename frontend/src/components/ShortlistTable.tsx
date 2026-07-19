import type { RecommendedApplicant } from '../types'

interface ShortlistTableProps {
  items: RecommendedApplicant[]
  selected: string[]
  invited: string[]
  onToggleOne: (applicationId: string) => void
  onToggleAll: () => void
}

/**
 * Ranked applicants, selectable for a bulk invite.
 *
 * A table rather than cards because the columns are being compared — two
 * scores side by side answer "who first?" at a glance, which stacked cards do
 * not.
 *
 * Presentational: it owns no selection state, so the parent can decide what
 * happens to a selection after an invite is sent.
 */
export default function ShortlistTable({
  items,
  selected,
  invited,
  onToggleOne,
  onToggleAll,
}: ShortlistTableProps) {
  const selectable = items.filter(
    (item) => !invited.includes(item.application.id),
  )
  // Only true when there is something to select — otherwise an all-invited
  // list would render a ticked box controlling nothing.
  const allSelected =
    selectable.length > 0 && selected.length === selectable.length

  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full min-w-[34rem] border-collapse text-sm">
        <thead>
          <tr className="border-b border-[color:var(--border)] text-left text-xs uppercase tracking-wide text-[color:var(--text-muted)]">
            <th scope="col" className="w-10 py-2">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={onToggleAll}
                disabled={selectable.length === 0}
                aria-label="Select all candidates"
                className="h-4 w-4"
              />
            </th>
            <th scope="col" className="py-2 pr-3">
              Candidate
            </th>
            <th scope="col" className="py-2 pr-3">
              Match
            </th>
            <th scope="col" className="py-2">
              Matched on
            </th>
          </tr>
        </thead>

        <tbody>
          {items.map(({ application, score, matched_terms }) => {
            const isInvited = invited.includes(application.id)

            return (
              <tr
                key={application.id}
                className="border-b border-[color:var(--border)] align-top last:border-0"
              >
                <td className="py-3">
                  <input
                    type="checkbox"
                    checked={selected.includes(application.id)}
                    onChange={() => onToggleOne(application.id)}
                    // Disabled once invited, so a second pass down the list
                    // cannot message the same person twice.
                    disabled={isInvited}
                    aria-label={`Select ${application.candidate.full_name}`}
                    className="h-4 w-4"
                  />
                </td>

                <td className="py-3 pr-3">
                  <span className="block font-semibold text-slate-900">
                    {application.candidate.full_name}
                  </span>
                  <span className="block text-xs text-[color:var(--text-muted)]">
                    {application.candidate.email}
                  </span>
                  {isInvited && (
                    <span className="mt-1 inline-block rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                      Invited
                    </span>
                  )}
                </td>

                <td className="py-3 pr-3">
                  <span className="font-semibold text-[color:var(--accent)]">
                    {Math.round(score * 100)}%
                  </span>
                </td>

                <td className="py-3">
                  <span className="flex flex-wrap gap-1">
                    {matched_terms.slice(0, 6).map((term) => (
                      <span
                        key={term}
                        className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600"
                      >
                        {term}
                      </span>
                    ))}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
