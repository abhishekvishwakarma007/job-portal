import { useCallback, useState } from 'react'

import { SHORTLIST_SIZE } from '../../constants'
import { request } from '../../lib/api'
import type { Job, RecommendationPage, RecommendedApplicant } from '../../types'

/**
 * A default invite, so contacting someone is one click rather than a blank box.
 *
 * Written to be sendable as-is but obviously worth editing — a recruiter who
 * sends the default verbatim has still said something reasonable, and one who
 * personalises it has a starting point rather than a cursor blinking at them.
 */
export function defaultInvite(job: Job): string {
  return (
    `Thanks for applying to ${job.title} at ${job.company}. ` +
    `We have reviewed your application and would like to take it further.\n\n` +
    `Are you available for an introductory call this week? ` +
    `Reply with a couple of times that suit you and we will confirm.`
  )
}

/**
 * The shortlist for one posting, and the invites sent from it.
 *
 * Selection, delivery and failure all live together because a partial send has
 * to leave the failures selected — splitting that state across components is
 * what makes "sent 4 of 5" impossible to represent honestly.
 */
export function useJobInvites(job: Job) {
  const [items, setItems] = useState<RecommendedApplicant[] | null>(null)
  const [isRanking, setIsRanking] = useState(false)
  const [selected, setSelected] = useState<string[]>([])
  const [invited, setInvited] = useState<string[]>([])
  const [message, setMessage] = useState('')
  const [isComposing, setIsComposing] = useState(false)
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /** Fetch the shortlist once, on first expand. */
  const rank = useCallback(async () => {
    if (items !== null) return

    setIsRanking(true)
    try {
      const page = await request<RecommendationPage>(
        `/jobs/${job.id}/recommendations`,
        { params: { limit: SHORTLIST_SIZE } },
      )
      setItems(page.items)
    } catch {
      // A failed ranking must not take the row's actions down with it, so this
      // degrades to "none" rather than surfacing as a page error.
      setItems([])
    } finally {
      setIsRanking(false)
    }
  }, [items, job.id])

  const toggleOne = useCallback((applicationId: string) => {
    setSelected((current) =>
      current.includes(applicationId)
        ? current.filter((id) => id !== applicationId)
        : [...current, applicationId],
    )
  }, [])

  const toggleAll = useCallback(() => {
    const selectable = (items ?? [])
      .filter((item) => !invited.includes(item.application.id))
      .map((item) => item.application.id)

    setSelected((current) =>
      current.length === selectable.length ? [] : selectable,
    )
  }, [items, invited])

  const compose = useCallback(() => {
    setMessage(defaultInvite(job))
    setIsComposing(true)
    setError(null)
  }, [job])

  const cancel = useCallback(() => {
    setIsComposing(false)
    setMessage('')
  }, [])

  const send = useCallback(async () => {
    if (!message.trim()) {
      setError('Write a message before sending.')
      return
    }

    setError(null)
    setIsSending(true)

    // Sent one at a time and tracked individually: if the fourth of five
    // fails, the first three were genuinely delivered, and saying otherwise is
    // a lie the recruiter acts on by never following up.
    const delivered: string[] = []
    const failed: string[] = []

    for (const applicationId of selected) {
      try {
        await request(`/applications/${applicationId}/contact`, {
          method: 'POST',
          body: { message },
        })
        delivered.push(applicationId)
      } catch {
        failed.push(applicationId)
      }
    }

    setInvited((current) => [...current, ...delivered])
    setSelected(failed)
    setIsComposing(failed.length > 0)
    setIsSending(false)

    if (failed.length > 0) {
      setError(
        `Sent ${delivered.length}, but ${failed.length} failed. The failed ones are still selected.`,
      )
    }
  }, [message, selected])

  return {
    items: items ?? [],
    isRanking,
    selected,
    invited,
    message,
    isComposing,
    isSending,
    error,
    setError,
    setMessage,
    rank,
    toggleOne,
    toggleAll,
    compose,
    cancel,
    send,
  }
}
