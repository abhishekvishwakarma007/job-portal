import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CANDIDATE, HR_USER, renderPage, stubApi } from '../test/harness'
import LoginPage from './LoginPage'

const TOKENS = { access_token: 'access', refresh_token: 'refresh', token_type: 'bearer' }

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

async function submit(email: string, password: string) {
  await userEvent.type(screen.getByLabelText(/email/i), email)
  await userEvent.type(screen.getByLabelText(/password/i), password)
  await userEvent.click(screen.getByRole('button', { name: /sign in/i }))
}

describe('LoginPage', () => {
  it('stores the token on a successful sign-in', async () => {
    stubApi({
      'POST /auth/login': { status: 200, body: TOKENS },
      'GET /auth/me': { status: 200, body: CANDIDATE },
    })

    renderPage(<LoginPage />)
    await submit('user@test.com', 'User@1234')

    await vi.waitFor(() => {
      expect(window.localStorage.getItem('jobportal.access_token')).toBe('access')
    })
  })

  it('shows the server message on a rejected sign-in', async () => {
    stubApi({
      'POST /auth/login': {
        status: 401,
        body: { detail: 'Incorrect email or password' },
      },
    })

    renderPage(<LoginPage />)
    await submit('user@test.com', 'Wrong@1234')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /incorrect email or password/i,
    )
  })

  it('does not store a token when sign-in fails', async () => {
    // A stored credential that does not work is worse than none: it makes the
    // app render as signed in and then fail every request.
    stubApi({
      'POST /auth/login': { status: 401, body: { detail: 'Incorrect email or password' } },
    })

    renderPage(<LoginPage />)
    await submit('user@test.com', 'Wrong@1234')

    await screen.findByRole('alert')
    expect(window.localStorage.getItem('jobportal.access_token')).toBeNull()
  })

  it('reports an unreachable server distinctly from bad credentials', async () => {
    // "Incorrect password" when the API is down sends someone hunting for a
    // problem that is not theirs.
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('failed')))

    renderPage(<LoginPage />)
    await submit('user@test.com', 'User@1234')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /could not reach the server/i,
    )
  })

  it('re-enables the button after a failure so the form can be retried', async () => {
    stubApi({
      'POST /auth/login': { status: 401, body: { detail: 'Incorrect email or password' } },
    })

    renderPage(<LoginPage />)
    await submit('user@test.com', 'Wrong@1234')
    await screen.findByRole('alert')

    expect(screen.getByRole('button', { name: /sign in/i })).toBeEnabled()
  })

  it('uses the right autocomplete hints for a password manager', async () => {
    stubApi({})

    renderPage(<LoginPage />)

    expect(screen.getByLabelText(/email/i)).toHaveAttribute(
      'autocomplete',
      'username',
    )
    expect(screen.getByLabelText(/password/i)).toHaveAttribute(
      'autocomplete',
      'current-password',
    )
  })

  it('signs an HR user in as well', async () => {
    stubApi({
      'POST /auth/login': { status: 200, body: TOKENS },
      'GET /auth/me': { status: 200, body: HR_USER },
    })

    renderPage(<LoginPage />)
    await submit('admin@test.com', 'Admin@1234')

    await vi.waitFor(() => {
      expect(window.localStorage.getItem('jobportal.access_token')).toBe('access')
    })
  })
})
