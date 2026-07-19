import { useCallback, useEffect, useState } from 'react'

import { ApiError, request } from '../lib/api'

export interface ApiResource<T> {
  data: T | null
  isLoading: boolean
  error: string | null
  /** Re-run the fetch, e.g. after a mutation changed the result. */
  reload: () => void
}

/**
 * Fetch a resource, tracking the three states every request really has.
 *
 * Written once here because every screen needs the same loading / failed /
 * loaded handling, and a page that renders only the success case shows a blank
 * screen when the API is down — which reads as a broken build rather than a
 * backend that is not up.
 *
 * `path` and `params` are the dependencies, so a screen that changes its
 * search term re-fetches without extra wiring.
 */
export function useApiResource<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
): ApiResource<T> {
  const [data, setData] = useState<T | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  // Serialised so a fresh object literal on every render does not retrigger
  // the effect forever.
  const serialisedParams = JSON.stringify(params ?? {})

  const reload = useCallback(() => setReloadToken((value) => value + 1), [])

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      setIsLoading(true)
      setError(null)

      try {
        const result = await request<T>(path, {
          params: JSON.parse(serialisedParams) as Record<string, string>,
          signal: controller.signal,
        })
        setData(result)
      } catch (cause) {
        // An abort is the caller's own doing, not a failure to report.
        if (cause instanceof DOMException && cause.name === 'AbortError') return
        setError(
          cause instanceof ApiError
            ? cause.message
            : 'Something went wrong. Please try again.',
        )
      } finally {
        if (!controller.signal.aborted) setIsLoading(false)
      }
    }

    void load()
    return () => controller.abort()
  }, [path, serialisedParams, reloadToken])

  return { data, isLoading, error, reload }
}
