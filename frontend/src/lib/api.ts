/**
 * Typed client for the JobPortal API.
 *
 * Every call goes through `request`, so authentication, error shaping, and JSON
 * handling exist in exactly one place. A component that needs a new endpoint
 * adds a function here rather than reaching for fetch directly and re-inventing
 * the error handling.
 */

// Relative by default so the browser talks to whatever origin served the page —
// nginx proxies /api to the backend in production, and Vite's dev server does
// the same locally. Overridable at build time via VITE_API_BASE_URL for a
// deployment that puts the API on its own host.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export class ApiError extends Error {
  readonly status: number
  /** Field-level messages, keyed by field name, when the server sent them. */
  readonly fieldErrors: Record<string, string>

  constructor(
    status: number,
    message: string,
    fieldErrors: Record<string, string> = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

/** FastAPI's 422 body: a list of per-field validation failures. */
interface ValidationDetail {
  loc: (string | number)[]
  msg: string
}

function isValidationDetail(value: unknown): value is ValidationDetail {
  return (
    typeof value === 'object' &&
    value !== null &&
    Array.isArray((value as ValidationDetail).loc) &&
    typeof (value as ValidationDetail).msg === 'string'
  )
}

/**
 * Turn an error body into a message plus per-field messages.
 *
 * FastAPI reports validation failures as a list under `detail` and everything
 * else as a plain string there, so both shapes have to be handled or a 422
 * surfaces to the user as "[object Object]".
 */
function parseError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown })?.detail

  if (typeof detail === 'string') {
    return new ApiError(status, detail)
  }

  if (Array.isArray(detail)) {
    const fieldErrors: Record<string, string> = {}

    for (const item of detail) {
      if (!isValidationDetail(item)) continue
      // loc is ["body", "field"] — the last segment is the field name.
      const field = item.loc[item.loc.length - 1]
      if (typeof field === 'string' && !(field in fieldErrors)) {
        fieldErrors[field] = item.msg.replace(/^Value error, /, '')
      }
    }

    const first = Object.values(fieldErrors)[0]
    return new ApiError(status, first ?? 'Please check the form and try again.', fieldErrors)
  }

  return new ApiError(status, 'Something went wrong. Please try again.')
}

let authToken: string | null = null

/** Set or clear the bearer token used by subsequent requests. */
export function setAuthToken(token: string | null): void {
  authToken = token
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  /** Query parameters; undefined and empty values are omitted. */
  params?: Record<string, string | number | undefined>
  signal?: AbortSignal
}

export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = 'GET', body, params, signal } = options

  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin)
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== '') {
      url.searchParams.set(key, String(value))
    }
  }

  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (authToken) headers.Authorization = `Bearer ${authToken}`

  // Built key by key rather than as a literal: under exactOptionalPropertyTypes
  // an explicit `body: undefined` is not the same as an absent body, and
  // RequestInit does not accept the former.
  const init: RequestInit = { method, headers }
  if (body !== undefined) init.body = JSON.stringify(body)
  if (signal) init.signal = signal

  let response: Response
  try {
    response = await fetch(url, init)
  } catch (cause) {
    // A network failure is not an HTTP status, but the UI still needs one
    // message shape to render. 0 marks "never reached the server".
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new ApiError(0, 'Could not reach the server. Is it running?')
  }

  if (response.status === 204) return undefined as T

  const text = await response.text()
  const payload: unknown = text ? JSON.parse(text) : null

  if (!response.ok) {
    throw parseError(response.status, payload)
  }

  return payload as T
}
