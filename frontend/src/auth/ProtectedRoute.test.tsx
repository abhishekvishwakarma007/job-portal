import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CANDIDATE, HR_USER, renderPage, stubApi } from '../test/harness'
import ProtectedRoute from './ProtectedRoute'

/**
 * The app's only frontend route gate.
 *
 * It is navigation, not security — the API gates every endpoint independently,
 * so removing this would make the app confusing rather than unsafe. These
 * tests pin the behaviour that makes it useful, and one case that is a fixed
 * bug rather than a preference.
 */
function Guarded({ role }: { role?: 'HR' | 'CANDIDATE' }) {
  return (
    <Routes>
      <Route
        path="/protected"
        element={
          <ProtectedRoute {...(role ? { role } : {})}>
            <p>Protected content</p>
          </ProtectedRoute>
        }
      />
      <Route path="/login" element={<p>Login page</p>} />
    </Routes>
  )
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('ProtectedRoute', () => {
  it('renders the page for a signed-in user', async () => {
    stubApi({ 'GET /auth/me': { status: 200, body: CANDIDATE } })

    renderPage(<Guarded />, { as: CANDIDATE, route: '/protected' })

    expect(await screen.findByText('Protected content')).toBeInTheDocument()
  })

  it('redirects an anonymous visitor to login', async () => {
    stubApi({})

    renderPage(<Guarded />, { route: '/protected' })

    expect(await screen.findByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
  })

  it('waits for the session check instead of redirecting mid-flight', async () => {
    // The bug this branch exists for. A stored token is exchanged for
    // /auth/me on boot, and redirecting during that exchange bounces a
    // perfectly signed-in user to the login screen on every page refresh.
    let resolveMe: (value: Response) => void = () => {}
    const pending = new Promise<Response>((resolve) => {
      resolveMe = resolve
    })
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(pending))
    window.localStorage.setItem('jobportal.access_token', 'stored-token')

    renderPage(<Guarded />, { route: '/protected' })

    // Mid-flight: neither the content nor a redirect.
    expect(screen.queryByText('Login page')).not.toBeInTheDocument()
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
    expect(screen.getByText(/loading/i)).toBeInTheDocument()

    resolveMe({
      ok: true,
      status: 200,
      text: async () => JSON.stringify(CANDIDATE),
    } as Response)

    expect(await screen.findByText('Protected content')).toBeInTheDocument()
  })

  it('admits a user holding the required role', async () => {
    stubApi({ 'GET /auth/me': { status: 200, body: HR_USER } })

    renderPage(<Guarded role="HR" />, { as: HR_USER, route: '/protected' })

    expect(await screen.findByText('Protected content')).toBeInTheDocument()
  })

  it('refuses a signed-in user holding the wrong role', async () => {
    // Not a redirect to login: they are signed in, so sending them to a login
    // form would be nonsense. They are told the page is not for their account.
    stubApi({ 'GET /auth/me': { status: 200, body: CANDIDATE } })

    renderPage(<Guarded role="HR" />, { as: CANDIDATE, route: '/protected' })

    expect(await screen.findByText(/not available for your account/i)).toBeInTheDocument()
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
    expect(screen.queryByText('Login page')).not.toBeInTheDocument()
  })

  it('names the role a page is for', async () => {
    stubApi({ 'GET /auth/me': { status: 200, body: HR_USER } })

    renderPage(<Guarded role="CANDIDATE" />, { as: HR_USER, route: '/protected' })

    expect(await screen.findByText(/for candidate accounts/i)).toBeInTheDocument()
  })

  it('treats a rejected token as signed out', async () => {
    // An expired or revoked token must resolve to the login screen, not to a
    // page that renders and then 401s on every action.
    window.localStorage.setItem('jobportal.access_token', 'stale-token')
    stubApi({ 'GET /auth/me': { status: 401, body: { detail: 'Not authenticated' } } })

    renderPage(<Guarded />, { route: '/protected' })

    expect(await screen.findByText('Login page')).toBeInTheDocument()
  })
})
