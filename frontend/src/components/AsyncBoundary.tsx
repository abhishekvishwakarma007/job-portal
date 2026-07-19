import type { ReactNode } from 'react'

interface AsyncBoundaryProps {
  isLoading: boolean
  error: string | null
  /** Shown when the request succeeded but returned nothing. */
  isEmpty?: boolean
  emptyMessage?: string
  children: ReactNode
}

/**
 * Render the loading and failure states around a fetched view.
 *
 * Centralised so no screen can quietly forget one of them: an unhandled error
 * state renders as an empty page, which looks like "there is nothing here"
 * rather than "this did not load".
 */
export default function AsyncBoundary({
  isLoading,
  error,
  isEmpty = false,
  emptyMessage = 'Nothing here yet.',
  children,
}: AsyncBoundaryProps) {
  if (isLoading) {
    return <p className="muted">Loading…</p>
  }

  if (error) {
    return (
      <p className="alert alert--error" role="alert">
        {error}
      </p>
    )
  }

  if (isEmpty) {
    return (
      <div className="card empty">
        <p>{emptyMessage}</p>
      </div>
    )
  }

  return <>{children}</>
}
