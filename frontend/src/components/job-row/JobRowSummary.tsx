import { EMPLOYMENT_TYPE_LABELS, type Job } from '../../types'

interface JobRowSummaryProps {
  job: Job
  isOpen: boolean
  panelId: string
  onToggle: () => void
}

/** The always-visible row: what the posting is, and its publish state. */
export default function JobRowSummary({
  job,
  isOpen,
  panelId,
  onToggle,
}: JobRowSummaryProps) {
  return (
    <h3 className="m-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        aria-controls={panelId}
        className="flex w-full cursor-pointer items-start justify-between gap-4 border-0 bg-transparent px-5 py-4 text-left"
      >
        <span>
          <span className="block text-base font-semibold text-slate-900">
            {job.title}
          </span>
          <span className="mt-0.5 block text-sm font-medium text-[color:var(--accent)]">
            {job.company}
          </span>
          <span className="mt-1 block text-sm text-[color:var(--text-muted)]">
            {job.location} · {EMPLOYMENT_TYPE_LABELS[job.employment_type]}
          </span>
        </span>

        <span className="flex shrink-0 items-center gap-3">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
              job.is_published
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-slate-100 text-slate-600'
            }`}
          >
            {job.is_published ? 'Published' : 'Draft'}
          </span>
          <span
            aria-hidden="true"
            className={`text-[color:var(--text-muted)] transition-transform ${
              isOpen ? 'rotate-180' : ''
            }`}
          >
            ▾
          </span>
        </span>
      </button>
    </h3>
  )
}
