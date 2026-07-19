import type { RecommendedApplicant } from '../../types'
import InviteComposer from '../InviteComposer'
import ShortlistTable from '../ShortlistTable'

interface JobRowShortlistProps {
  jobId: string
  items: RecommendedApplicant[]
  isRanking: boolean
  selected: string[]
  invited: string[]
  message: string
  isComposing: boolean
  isSending: boolean
  onToggleOne: (applicationId: string) => void
  onToggleAll: () => void
  onCompose: () => void
  onChangeMessage: (message: string) => void
  onSend: () => void
  onCancel: () => void
}

/**
 * Ranked applicants and the invite sent to them.
 *
 * The score is described as a shortlist aid rather than an assessment, matching
 * the API labelling its own method — a keyword count must not be quietly
 * upgraded into a judgement about whether someone can do the job.
 */
export default function JobRowShortlist(props: JobRowShortlistProps) {
  const { items, isRanking, selected, isComposing } = props

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h4 className="m-0 text-sm font-semibold uppercase tracking-wide text-[color:var(--text-muted)]">
            Top matches
          </h4>
          <p className="mt-1 text-xs text-[color:var(--text-muted)]">
            Ranked by keyword overlap between each candidate and this posting —
            a shortlist aid, not an assessment.
          </p>
        </div>

        {selected.length > 0 && !isComposing && (
          <button
            type="button"
            onClick={props.onCompose}
            className="rounded-lg bg-[color:var(--accent)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90"
          >
            Invite {selected.length} selected
          </button>
        )}
      </div>

      {isRanking && (
        <p className="mt-3 text-sm text-[color:var(--text-muted)]">
          Ranking applicants…
        </p>
      )}

      {!isRanking && items.length === 0 && (
        <p className="mt-3 text-sm text-[color:var(--text-muted)]">
          No applications to rank yet.
        </p>
      )}

      {items.length > 0 && (
        <ShortlistTable
          items={items}
          selected={selected}
          invited={props.invited}
          onToggleOne={props.onToggleOne}
          onToggleAll={props.onToggleAll}
        />
      )}

      {isComposing && (
        <InviteComposer
          id={props.jobId}
          recipientCount={selected.length}
          message={props.message}
          isSending={props.isSending}
          onChange={props.onChangeMessage}
          onSend={props.onSend}
          onCancel={props.onCancel}
        />
      )}
    </>
  )
}
