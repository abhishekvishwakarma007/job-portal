import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, request, setAuthToken } from './api'

/** Build a fetch stub returning the given status and JSON body. */
function mockFetch(status: number, body: unknown) {
  const response = {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (body === null ? '' : JSON.stringify(body)),
  } as Response

  const spy = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', spy)
  return spy
}

/**
 * Await a request expected to fail and return its ApiError.
 *
 * Narrowing here rather than casting at each call site means a rejection with
 * some other error type fails the test loudly instead of being asserted
 * against as if it were an ApiError.
 */
async function captureApiError(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (cause) {
    if (cause instanceof ApiError) return cause
    throw cause
  }

  throw new Error('Expected the request to reject, but it resolved')
}

afterEach(() => {
  vi.unstubAllGlobals()
  setAuthToken(null)
})

describe('request', () => {
  it('returns the parsed body on success', async () => {
    mockFetch(200, { items: [], total: 0 })

    await expect(request('/jobs')).resolves.toEqual({ items: [], total: 0 })
  })

  it('returns undefined for 204 without parsing a body', async () => {
    mockFetch(204, null)

    await expect(request('/jobs/x')).resolves.toBeUndefined()
  })

  it('attaches the bearer token once set', async () => {
    const spy = mockFetch(200, {})
    setAuthToken('a-token')

    await request('/auth/me')

    const headers = spy.mock.calls[0]?.[1]?.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer a-token')
  })

  it('sends no Authorization header once the token is cleared', async () => {
    const spy = mockFetch(200, {})
    setAuthToken('a-token')
    setAuthToken(null)

    await request('/jobs')

    const headers = spy.mock.calls[0]?.[1]?.headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
  })

  it('omits empty query parameters', async () => {
    const spy = mockFetch(200, {})

    await request('/jobs', { params: { search: '', limit: 20 } })

    const url = spy.mock.calls[0]?.[0] as URL
    expect(url.searchParams.get('search')).toBeNull()
    expect(url.searchParams.get('limit')).toBe('20')
  })

  it('surfaces a string detail as the error message', async () => {
    mockFetch(401, { detail: 'Incorrect email or password' })

    await expect(request('/auth/login')).rejects.toThrow(
      'Incorrect email or password',
    )
  })

  it('maps a 422 validation body to per-field messages', async () => {
    // FastAPI's shape. Rendering `detail` directly here would put
    // "[object Object]" in front of the user.
    mockFetch(422, {
      detail: [
        {
          loc: ['body', 'password'],
          msg: 'Value error, Password must be at least 8 characters.',
        },
        { loc: ['body', 'email'], msg: 'value is not a valid email address' },
      ],
    })

    const error = await captureApiError(request('/auth/register'))

    expect(error.fieldErrors.password).toBe(
      'Password must be at least 8 characters.',
    )
    expect(error.fieldErrors.email).toBe('value is not a valid email address')
    // The first field message doubles as the summary so the form always has
    // something to show even without per-field rendering.
    expect(error.message).toBe('Password must be at least 8 characters.')
  })

  it('reports a network failure as a reachability problem', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed')))

    const error = await captureApiError(request('/jobs'))

    expect(error.status).toBe(0)
    expect(error.message).toMatch(/could not reach the server/i)
  })

  it('propagates an abort rather than dressing it as a server error', async () => {
    const abort = new DOMException('aborted', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))

    await expect(request('/jobs')).rejects.toBe(abort)
  })
})
