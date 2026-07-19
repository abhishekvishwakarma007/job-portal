import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../auth/AuthProvider'
import JobDetailPage from './JobDetailPage'

const CANDIDATE = {
  id: 'c1',
  email: 'user@test.com',
  full_name: 'Sam Okafor',
  role: 'CANDIDATE',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
}

const JOB = {
  id: 'j1',
  title: 'Senior Platform Engineer',
  description: 'Own the deployment pipeline.',
  location: 'Remote',
  employment_type: 'FULL_TIME',
  is_published: true,
  created_by: { ...CANDIDATE, id: 'h1', role: 'HR', full_name: 'Dana Reyes' },
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

/** Stub fetch, routing by path and method. */
function stubApi(
  routes: Record<string, { status: number; body: unknown }>,
): ReturnType<typeof vi.fn> {
  const spy = vi.fn(async (input: URL | string, init?: RequestInit) => {
    const path = (input instanceof URL ? input.pathname : input).replace(
      '/api/v1',
      '',
    )
    const key = `${init?.method ?? 'GET'} ${path}`
    const match = routes[key] ?? { status: 404, body: { detail: 'not found' } }

    return {
      ok: match.status >= 200 && match.status < 300,
      status: match.status,
      text: async () => JSON.stringify(match.body),
    } as Response
  })

  vi.stubGlobal('fetch', spy)
  return spy
}

function renderPage() {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={['/jobs/j1']}>
        <Routes>
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  )
}

beforeEach(() => {
  window.localStorage.setItem('jobportal.access_token', 'token')
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('JobDetailPage', () => {
  it('shows the apply form to a signed-in candidate', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /jobs/j1': { status: 200, body: JOB },
    })

    renderPage()

    expect(
      await screen.findByRole('button', { name: /submit application/i }),
    ).toBeInTheDocument()
  })

  it('confirms submission on success', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /jobs/j1': { status: 200, body: JOB },
      'POST /applications': { status: 201, body: { id: 'a1' } },
    })

    renderPage()

    await userEvent.type(
      await screen.findByLabelText(/cover letter/i),
      'Six years of pipeline work.',
    )
    await userEvent.click(
      screen.getByRole('button', { name: /submit application/i }),
    )

    expect(await screen.findByRole('status')).toHaveTextContent(
      /application has been submitted/i,
    )
  })

  it('treats a duplicate-apply 409 as already applied, not as an error', async () => {
    // The candidate's goal is already true, so showing a red failure would be
    // both confusing and wrong — they are in the pipeline either way.
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /jobs/j1': { status: 200, body: JOB },
      'POST /applications': {
        status: 409,
        body: { detail: 'You have already applied to this job' },
      },
    })

    renderPage()

    await userEvent.type(
      await screen.findByLabelText(/cover letter/i),
      'Applying again by accident.',
    )
    await userEvent.click(
      screen.getByRole('button', { name: /submit application/i }),
    )

    expect(await screen.findByRole('status')).toHaveTextContent(
      /application has been submitted/i,
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('surfaces a real failure as an error', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /jobs/j1': { status: 200, body: JOB },
      'POST /applications': {
        status: 404,
        body: { detail: 'Job not found' },
      },
    })

    renderPage()

    await userEvent.type(
      await screen.findByLabelText(/cover letter/i),
      'Applying to a role that vanished.',
    )
    await userEvent.click(
      screen.getByRole('button', { name: /submit application/i }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(/job not found/i)
  })

  it('requires a cover letter before calling the API', async () => {
    const spy = stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /jobs/j1': { status: 200, body: JOB },
    })

    renderPage()

    await userEvent.click(
      await screen.findByRole('button', { name: /submit application/i }),
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(/required/i)
    await waitFor(() => {
      const posted = spy.mock.calls.some(
        ([, init]) => (init as RequestInit | undefined)?.method === 'POST',
      )
      expect(posted).toBe(false)
    })
  })

  it('prompts an anonymous visitor to sign in instead of showing the form', async () => {
    window.localStorage.clear()
    stubApi({ 'GET /jobs/j1': { status: 200, body: JOB } })

    renderPage()

    expect(await screen.findByText(/sign in/i)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /submit application/i }),
    ).not.toBeInTheDocument()
  })
})
