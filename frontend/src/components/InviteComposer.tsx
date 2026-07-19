import { MESSAGE_MAX_LENGTH } from '../constants'

interface InviteComposerProps {
  id: string
  recipientCount: number
  message: string
  isSending: boolean
  onChange: (message: string) => void
  onSend: () => void
  onCancel: () => void
}

/**
 * The message sent to everyone currently selected.
 *
 * Opens prefilled by its parent rather than empty: a blank box is a small tax
 * charged on every single invite, and a default that is sendable as-is still
 * says something reasonable if nobody edits it.
 */
export default function InviteComposer({
  id,
  recipientCount,
  message,
  isSending,
  onChange,
  onSend,
  onCancel,
}: InviteComposerProps) {
  const noun = recipientCount === 1 ? 'candidate' : 'candidates'

  return (
    <div className="mt-4 rounded-lg border border-[color:var(--border)] bg-slate-50 p-4">
      <label
        htmlFor={`invite-${id}`}
        className="block text-sm font-semibold text-slate-900"
      >
        Invite {recipientCount} {noun}
      </label>
      <p className="mt-0.5 text-xs text-[color:var(--text-muted)]">
        Everyone selected receives the same message. Nothing is emailed — it
        appears in their invites.
      </p>

      <textarea
        id={`invite-${id}`}
        value={message}
        maxLength={MESSAGE_MAX_LENGTH}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 min-h-32 w-full rounded-lg border border-[color:var(--border)] px-3 py-2 text-sm"
      />

      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={isSending || recipientCount === 0}
          onClick={onSend}
          className="rounded-lg bg-[color:var(--accent)] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
        >
          {isSending
            ? 'Sending…'
            : `Send ${recipientCount} ${
                recipientCount === 1 ? 'invite' : 'invites'
              }`}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-[color:var(--border)] bg-white px-4 py-2 text-sm font-semibold text-slate-700"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
