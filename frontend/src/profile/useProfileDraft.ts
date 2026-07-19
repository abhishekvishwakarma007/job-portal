import { useCallback, useEffect, useState } from 'react'

import { useApiResource } from '../hooks/useApiResource'
import { ApiError, request } from '../lib/api'
import type { CandidateProfile } from '../types'
import { EMPTY_DRAFT, type Draft, type ProfileField } from './sections'

/**
 * Holds the editable profile and saves one section at a time.
 *
 * Separated from the page so the page renders and this decides. The
 * section-at-a-time save is the part worth isolating: sending the whole draft
 * would let a stale field overwrite a section the user was not editing, and
 * one save button over ten fields means a failure anywhere discards work
 * everywhere.
 */
export function useProfileDraft() {
  const { data, isLoading, error, reload } =
    useApiResource<CandidateProfile>('/profile/me')

  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT)
  const [savingSection, setSavingSection] = useState<string | null>(null)
  const [savedSection, setSavedSection] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (!data) return

    setDraft(
      Object.fromEntries(
        Object.keys(EMPTY_DRAFT).map((field) => [
          field,
          data[field as ProfileField],
        ]),
      ) as Draft,
    )
  }, [data])

  const setField = useCallback((field: keyof Draft, value: string) => {
    setDraft((current) => ({ ...current, [field]: value }))
    setSavedSection(null)
  }, [])

  const saveSection = useCallback(
    async (section: string, fields: ProfileField[]) => {
      setSaveError(null)
      setSavingSection(section)

      // Only this section's fields are sent, so a save cannot carry a stale
      // value from a section the user never touched.
      const body = Object.fromEntries(
        fields.map((field) => [field, draft[field]]),
      )

      try {
        await request<CandidateProfile>('/profile/me', { method: 'PATCH', body })
        setSavedSection(section)
        reload()
      } catch (cause) {
        setSaveError(
          cause instanceof ApiError
            ? cause.message
            : 'Could not save. Try again.',
        )
      } finally {
        setSavingSection(null)
      }
    },
    [draft, reload],
  )

  return {
    draft,
    isLoading,
    error,
    saveError,
    savingSection,
    savedSection,
    setField,
    saveSection,
  }
}
