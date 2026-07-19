import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from './AuthProvider'
import { useAuth } from './useAuth'

const CANDIDATE = {
  id: 'a1',
  email: 'user@test.com',
  full_name: 'Sam Okafor',
  role: 'CANDIDATE',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
}

/** Minimal consumer exposing auth state to assertions. */
function Probe() {
  const { user, isLoading, login, logout } = useAuth()

  if (isLoading) return <p>loading</p>

  return (
    <div>
      <p data-testid="user">{user ? user.email : 'signed out'}</p>
      <button onClick={() => void login('user@test.com', 'User@1234')}>
        sign in
      </button>
      <button onClick={logout}>sign out</button>
    </div>
  )
}

/** Route fetch by URL so one test can stub several endpoints. */
function stubApi(routes: Record<string, { status: number; body: unknown }>) {
  const spy = vi.fn(async (input: URL | string) => {
    const path = (input instanceof URL ? input.pathname : input).replace(
      '/api/v1',
      '',
    )
    const match = routes[path] ?? { status: 404, body: { detail: 'not found' } }

    return {
      ok: match.status >= 200 && match.status < 300,
      status: match.status,
      text: async () => JSON.stringify(match.body),
    } as Response
  })

  vi.stubGlobal('fetch', spy)
  return spy
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('AuthProvider', () => {
  it('starts signed out when no token is stored', async () => {
    stubApi({})

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    expect(await screen.findByTestId('user')).toHaveTextContent('signed out')
  })

  it('restores the session from a stored token', async () => {
    window.localStorage.setItem('jobportal.access_token', 'stored-token')
    stubApi({ '/auth/me': { status: 200, body: CANDIDATE } })

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    expect(await screen.findByTestId('user')).toHaveTextContent('user@test.com')
  })

  it('discards a token the server rejects', async () => {
    // The decisive case: a token that expired or belongs to a deactivated
    // account must resolve to signed-out, not a UI that renders as signed in
    // and then 401s on every action.
    window.localStorage.setItem('jobportal.access_token', 'stale-token')
    stubApi({ '/auth/me': { status: 401, body: { detail: 'Not authenticated' } } })

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    expect(await screen.findByTestId('user')).toHaveTextContent('signed out')
    expect(window.localStorage.getItem('jobportal.access_token')).toBeNull()
  })

  it('stores the token and loads the user on login', async () => {
    stubApi({
      '/auth/login': { status: 200, body: { access_token: 't', token_type: 'bearer' } },
      '/auth/me': { status: 200, body: CANDIDATE },
    })

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await screen.findByTestId('user')
    await userEvent.click(screen.getByRole('button', { name: 'sign in' }))

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent('user@test.com')
    })
    expect(window.localStorage.getItem('jobportal.access_token')).toBe('t')
  })

  it('reads the user from the server rather than the token', async () => {
    // The role in a token can be stale after an HR user is downgraded, so the
    // server is asked who the caller is instead of decoding the claims.
    const spy = stubApi({
      '/auth/login': { status: 200, body: { access_token: 't', token_type: 'bearer' } },
      '/auth/me': { status: 200, body: CANDIDATE },
    })

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await screen.findByTestId('user')
    await userEvent.click(screen.getByRole('button', { name: 'sign in' }))

    await waitFor(() => {
      const paths = spy.mock.calls.map(([input]) =>
        input instanceof URL ? input.pathname : String(input),
      )
      expect(paths.some((path) => path.endsWith('/auth/me'))).toBe(true)
    })
  })

  it('clears the stored token on sign out', async () => {
    window.localStorage.setItem('jobportal.access_token', 'stored-token')
    stubApi({ '/auth/me': { status: 200, body: CANDIDATE } })

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent('user@test.com')
    })

    await userEvent.click(screen.getByRole('button', { name: 'sign out' }))

    await waitFor(() => {
      expect(screen.getByTestId('user')).toHaveTextContent('signed out')
    })
    expect(window.localStorage.getItem('jobportal.access_token')).toBeNull()
  })
})
