import { useState } from 'react'

import { ApiError, request } from '../lib/api'
import type { Job } from '../types'
import JobRowActions from './job-row/JobRowActions'
import JobRowShortlist from './job-row/JobRowShortlist'
import JobRowSummary from './job-row/JobRowSummary'
import { useJobInvites } from './job-row/useJobInvites'

interface ManagedJobRowProps {
  job: Job
  isOpen: boolean
  onToggle: () => void
  onChanged: () => void
}

/**
 * One posting in the HR list: a summary that expands to actions and a ranked,
 * selectable shortlist.
 *
 * This composes; the pieces render and useJobInvites decides. Invite state
 * lives in that hook rather than here because selection, delivery and failure
 * have to move together — a partial send leaves the failures selected.
 */
export default function ManagedJobRow({
  job,
  isOpen,
  onToggle,
  onChanged,
}: ManagedJobRowProps) {
  const invites = useJobInvites(job)
  const [isBusy, setIsBusy] = useState(false)
  const panelId = `managed-panel-${job.id}`

  /** Run a mutation, surfacing failure through the shared error slot. */
  async function mutate(action: () => Promise<unknown>, failure: string) {
    invites.setError(null)
    setIsBusy(true)
    try {
      await action()
      onChanged()
    } catch (cause) {
      invites.setError(cause instanceof ApiError ? cause.message : failure)
    } finally {
      setIsBusy(false)
    }
  }

  function handleToggle() {
    onToggle()
    // Ranked on first expand only. Fetching for every posting up front would
    // rank every application on the page to show names nobody opened.
    if (!isOpen) void invites.rank()
  }

  function handleDelete() {
    const confirmed = window.confirm(
      `Delete “${job.title}”? Any applications to it are removed too. This cannot be undone.`,
    )
    if (!confirmed) return

    void mutate(
      () => request(`/jobs/${job.id}`, { method: 'DELETE' }),
      'Could not delete the role.',
    )
  }

  return (
    <li className="overflow-hidden rounded-xl border border-[color:var(--border)] bg-white shadow-sm">
      <JobRowSummary
        job={job}
        isOpen={isOpen}
        panelId={panelId}
        onToggle={handleToggle}
      />

      {isOpen && (
        <div
          id={panelId}
          className="border-t border-[color:var(--border)] px-5 py-4"
        >
          {invites.error && (
            <p
              role="alert"
              className="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              {invites.error}
            </p>
          )}

          <JobRowActions
            job={job}
            isBusy={isBusy}
            onTogglePublished={() =>
              void mutate(
                () =>
                  request(`/jobs/${job.id}`, {
                    method: 'PATCH',
                    body: { is_published: !job.is_published },
                  }),
                'Could not update the role.',
              )
            }
            onDelete={handleDelete}
          />

          <JobRowShortlist
            jobId={job.id}
            items={invites.items}
            isRanking={invites.isRanking}
            selected={invites.selected}
            invited={invites.invited}
            message={invites.message}
            isComposing={invites.isComposing}
            isSending={invites.isSending}
            onToggleOne={invites.toggleOne}
            onToggleAll={invites.toggleAll}
            onCompose={invites.compose}
            onChangeMessage={invites.setMessage}
            onSend={invites.send}
            onCancel={invites.cancel}
          />
        </div>
      )}
    </li>
  )
}
