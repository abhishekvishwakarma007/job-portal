import { Link } from 'react-router-dom'

import type { Job } from '../../types'

interface JobRowActionsProps {
  job: Job
  isBusy: boolean
  onTogglePublished: () => void
  onDelete: () => void
}

const SECONDARY =
  'rounded-lg border border-[color:var(--border)] bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 no-underline transition hover:bg-slate-50 disabled:opacity-60'

/** What an owner can do with a posting. */
export default function JobRowActions({
  job,
  isBusy,
  onTogglePublished,
  onDelete,
}: JobRowActionsProps) {
  return (
    <div className="mb-5 flex flex-wrap gap-2">
      <Link to={`/manage/${job.id}/applicants`} className={SECONDARY}>
        All applicants
      </Link>
      <Link to={`/manage/${job.id}/edit`} className={SECONDARY}>
        Edit
      </Link>
      <button
        type="button"
        onClick={onTogglePublished}
        disabled={isBusy}
        className={SECONDARY}
      >
        {job.is_published ? 'Unpublish' : 'Publish'}
      </button>
      <button
        type="button"
        onClick={onDelete}
        disabled={isBusy}
        className="rounded-lg bg-[color:var(--danger)] px-3 py-1.5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
      >
        Delete
      </button>
    </div>
  )
}
