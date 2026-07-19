import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CANDIDATE, renderPage, stubApi } from '../test/harness'
import RegisterPage from './RegisterPage'

const TOKENS = { access_token: 'access', refresh_token: 'refresh', token_type: 'bearer' }

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

async function fill({
  name = 'Sam Okafor',
  email = 'user@test.com',
  password = 'User@1234',
} = {}) {
  await userEvent.type(screen.getByLabelText(/full name/i), name)
  await userEvent.type(screen.getByLabelText(/email/i), email)
  await userEvent.type(screen.getByLabelText(/password/i), password)
}

describe('RegisterPage', () => {
  it('creates the account and signs straight in', async () => {
    // Registering and then being asked to log in is a pointless second step.
    const spy = stubApi({
      'POST /auth/register': { status: 201, body: CANDIDATE },
      'POST /auth/login': { status: 200, body: TOKENS },
      'GET /auth/me': { status: 200, body: CANDIDATE },
    })

    renderPage(<RegisterPage />)
    await fill()
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    await vi.waitFor(() => {
      expect(window.localStorage.getItem('jobportal.access_token')).toBe('access')
    })

    const paths = spy.mock.calls.map(([input]) =>
      input instanceof URL ? input.pathname : String(input),
    )
    expect(paths.some((path) => path.endsWith('/auth/register'))).toBe(true)
    expect(paths.some((path) => path.endsWith('/auth/login'))).toBe(true)
  })

  it('rejects a weak password before calling the API', async () => {
    // The client mirror exists so the user is told before submitting, not
    // after a round trip.
    const spy = stubApi({})

    renderPage(<RegisterPage />)
    await fill({ password: 'weak' })
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    expect(
      await screen.findByText('Password must be at least 8 characters.'),
    ).toBeInTheDocument()
    expect(spy).not.toHaveBeenCalled()
  })

  it('rejects a single-class password', async () => {
    stubApi({})

    renderPage(<RegisterPage />)
    await fill({ password: 'alllowercaseletters' })
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    expect(
      await screen.findByText(
        'Password must contain at least 3 of: lowercase, uppercase, digit, symbol.',
      ),
    ).toBeInTheDocument()
  })

  it('rejects a malformed email without calling the API', async () => {
    const spy = stubApi({})

    renderPage(<RegisterPage />)
    await fill({ email: 'not-an-email' })
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByText(/valid email/i)).toBeInTheDocument()
    expect(spy).not.toHaveBeenCalled()
  })

  it('shows the server field error when the client check passed', async () => {
    // The server validated the same input with the authoritative rules, so
    // its per-field message wins on conflict.
    stubApi({
      'POST /auth/register': {
        status: 422,
        body: {
          detail: [
            {
              loc: ['body', 'email'],
              msg: 'value is not a valid email address',
            },
          ],
        },
      },
    })

    renderPage(<RegisterPage />)
    await fill({ email: 'sam@reserved.test' })
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    expect(
      await screen.findByText(/not a valid email address/i),
    ).toBeInTheDocument()
  })

  it('reports a taken address', async () => {
    stubApi({
      'POST /auth/register': {
        status: 409,
        body: { detail: 'An account with this email already exists' },
      },
    })

    renderPage(<RegisterPage />)
    await fill()
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/already exists/i)
  })

  it('defaults to candidate and offers HR', async () => {
    stubApi({})

    renderPage(<RegisterPage />)

    expect(screen.getByRole('radio', { name: /candidate/i })).toBeChecked()
    expect(screen.getByRole('radio', { name: /hr/i })).not.toBeChecked()
  })

  it('states the password policy up front', async () => {
    // Telling someone the rule after they broke it is the worse order, so the
    // hint is rendered before anything is submitted.
    stubApi({})

    renderPage(<RegisterPage />)

    const password = screen.getByLabelText(/password/i)
    const hintId = password.getAttribute('aria-describedby')

    expect(hintId).toBeTruthy()
    expect(document.getElementById(hintId!)).toHaveTextContent(
      /at least 8 characters/i,
    )
  })
})
