import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CANDIDATE, renderPage, stubApi } from '../test/harness'
import ProfilePage from './ProfilePage'

const EMPTY_PROFILE = {
  id: 'profile-1',
  user_id: CANDIDATE.id,
  headline: '',
  location: '',
  phone: '',
  summary: '',
  preferred_role: '',
  preferred_location: '',
  preferred_employment_type: '',
  key_skills: '',
  employment: '',
  education: '',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

/** The JSON body of the most recent PATCH. */
function lastPatchBody(spy: ReturnType<typeof vi.fn>): Record<string, unknown> {
  const patches = spy.mock.calls.filter(
    ([, init]) => (init as RequestInit | undefined)?.method === 'PATCH',
  )
  const body = (patches[patches.length - 1]?.[1] as RequestInit).body

  return JSON.parse(String(body)) as Record<string, unknown>
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('ProfilePage', () => {
  it('renders the saved profile into its fields', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /profile/me': {
        status: 200,
        body: { ...EMPTY_PROFILE, headline: 'Platform engineer' },
      },
    })

    renderPage(<ProfilePage />, { as: CANDIDATE })

    await waitFor(() => {
      expect(screen.getByLabelText(/headline/i)).toHaveValue('Platform engineer')
    })
  })

  it('does not lose focus while typing', async () => {
    // Regression test. Section was declared inside the component, so every
    // keystroke produced a new component identity, React remounted the
    // subtree, and the focused input was destroyed — meaning one character per
    // click. The page the README sends a reviewer to was unusable.
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /profile/me': { status: 200, body: EMPTY_PROFILE },
    })

    renderPage(<ProfilePage />, { as: CANDIDATE })
    const headline = await screen.findByLabelText(/headline/i)

    headline.focus()
    await userEvent.keyboard('Platform engineer')

    // Both assertions matter: focus survived, and every character landed in
    // the same field rather than the first one landing and the rest going
    // nowhere.
    expect(headline).toHaveFocus()
    expect(headline).toHaveValue('Platform engineer')
  })

  it('sends only the edited section', async () => {
    // The decisive property. Sending everything would let a stale field in
    // local state overwrite a section the user was not editing.
    const spy = stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /profile/me': { status: 200, body: EMPTY_PROFILE },
      'PATCH /profile/me': { status: 200, body: EMPTY_PROFILE },
    })

    renderPage(<ProfilePage />, { as: CANDIDATE })
    await userEvent.type(
      await screen.findByLabelText(/headline/i),
      'Platform engineer',
    )

    const saveButtons = screen.getAllByRole('button', { name: /^save$/i })
    await userEvent.click(saveButtons[0]!)

    await waitFor(() => {
      const body = lastPatchBody(spy)
      expect(Object.keys(body).sort()).toEqual(['headline', 'location', 'phone'])
      expect(body.headline).toBe('Platform engineer')
    })
  })

  it('confirms a save', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /profile/me': { status: 200, body: EMPTY_PROFILE },
      'PATCH /profile/me': { status: 200, body: EMPTY_PROFILE },
    })

    renderPage(<ProfilePage />, { as: CANDIDATE })
    await screen.findByLabelText(/headline/i)

    await userEvent.click(screen.getAllByRole('button', { name: /^save$/i })[0]!)

    expect(await screen.findByText(/^saved$/i)).toBeInTheDocument()
  })

  it('surfaces a failed save rather than silently discarding it', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /profile/me': { status: 200, body: EMPTY_PROFILE },
      'PATCH /profile/me': { status: 422, body: { detail: 'Too long' } },
    })

    renderPage(<ProfilePage />, { as: CANDIDATE })
    await screen.findByLabelText(/headline/i)

    await userEvent.click(screen.getAllByRole('button', { name: /^save$/i })[0]!)

    expect(await screen.findByRole('alert')).toHaveTextContent(/too long/i)
  })

  it('previews the skill list as it is typed', async () => {
    // The comma-separated field is what the ranking splits on, so showing the
    // parse is how someone notices a stray comma before it becomes a skill.
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /profile/me': { status: 200, body: EMPTY_PROFILE },
    })

    renderPage(<ProfilePage />, { as: CANDIDATE })
    await userEvent.type(
      await screen.findByLabelText(/key skills/i),
      'Python, Docker',
    )

    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('Docker')).toBeInTheDocument()
  })

  it('says why the profile is worth filling in', async () => {
    // Effort with no visible payoff does not get made, so the page states that
    // skills feed the HR shortlist.
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /profile/me': { status: 200, body: EMPTY_PROFILE },
    })

    renderPage(<ProfilePage />, { as: CANDIDATE })

    expect(
      await screen.findByText(/hiring teams see your skills/i),
    ).toBeInTheDocument()
  })

  it('reports a failed load instead of showing empty fields', async () => {
    // Blank inputs would look like an empty profile, and saving over them
    // would then wipe a profile that had loaded fine a moment earlier.
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /profile/me': { status: 500, body: { detail: 'Server error' } },
    })

    renderPage(<ProfilePage />, { as: CANDIDATE })

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByLabelText(/headline/i)).not.toBeInTheDocument()
  })
})
