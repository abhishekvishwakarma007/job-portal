import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CANDIDATE, HR_USER, JOB, page, renderPage, stubApi } from '../test/harness'
import JobApplicantsPage from './JobApplicantsPage'

const APPLICATION = {
  id: 'application-1',
  job: JOB,
  candidate: CANDIDATE,
  cover_letter: 'Six years of deployment pipeline work.',
  status: 'SUBMITTED' as const,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function renderApplicants() {
  return renderPage(<JobApplicantsPage />, {
    as: HR_USER,
    route: '/manage/job-1/applicants',
    path: '/manage/:jobId/applicants',
  })
}

/** The parsed body of the last PATCH. */
function lastPatch(spy: ReturnType<typeof vi.fn>): Record<string, unknown> | null {
  const patches = spy.mock.calls.filter(
    ([, init]) => (init as RequestInit | undefined)?.method === 'PATCH',
  )
  const last = patches[patches.length - 1]

  return last ? (JSON.parse(String((last[1] as RequestInit).body)) as Record<string, unknown>) : null
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('JobApplicantsPage', () => {
  it('lists the applicants with their cover letters', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/job-1': { status: 200, body: JOB },
      'GET /jobs/job-1/applications': { status: 200, body: page([APPLICATION]) },
    })

    renderApplicants()

    expect(await screen.findByText('Sam Okafor')).toBeInTheDocument()
    expect(screen.getByText(/six years of deployment/i)).toBeInTheDocument()
    // The address shares a line with the applied-on date, so match within.
    expect(screen.getByText(/user@test\.com/)).toBeInTheDocument()
  })

  it('names the posting being reviewed', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/job-1': { status: 200, body: JOB },
      'GET /jobs/job-1/applications': { status: 200, body: page([APPLICATION]) },
    })

    renderApplicants()

    expect(
      await screen.findByText(/Senior Platform Engineer/),
    ).toBeInTheDocument()
  })

  it('PATCHes the chosen status to the right application', async () => {
    // The dropdown is the only way an application moves through the pipeline,
    // so both the target id and the value are worth pinning.
    const spy = stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/job-1': { status: 200, body: JOB },
      'GET /jobs/job-1/applications': { status: 200, body: page([APPLICATION]) },
      'PATCH /applications/application-1': {
        status: 200,
        body: { ...APPLICATION, status: 'ACCEPTED' },
      },
    })

    renderApplicants()
    await userEvent.selectOptions(
      await screen.findByLabelText(/move to/i),
      'ACCEPTED',
    )

    await waitFor(() => {
      expect(lastPatch(spy)).toEqual({ status: 'ACCEPTED' })
    })
    const patched = spy.mock.calls.find(
      ([, init]) => (init as RequestInit | undefined)?.method === 'PATCH',
    )?.[0] as URL
    expect(patched.pathname).toContain('application-1')
  })

  it('reflects the new status after the server confirms', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/job-1': { status: 200, body: JOB },
      'GET /jobs/job-1/applications': {
        status: 200,
        body: page([{ ...APPLICATION, status: 'ACCEPTED' }]),
      },
      'PATCH /applications/application-1': {
        status: 200,
        body: { ...APPLICATION, status: 'ACCEPTED' },
      },
    })

    renderApplicants()

    // Asserted on the select's value, not the word "Accepted" — that also
    // appears as a dropdown option, so matching the text alone would pass
    // against a row whose status never changed.
    await waitFor(() => {
      expect(screen.getByLabelText(/move to/i)).toHaveValue('ACCEPTED')
    })
  })

  it('surfaces a failed status change', async () => {
    // Silently failing would leave the recruiter believing they had rejected
    // someone who is still sitting in the pipeline.
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/job-1': { status: 200, body: JOB },
      'GET /jobs/job-1/applications': { status: 200, body: page([APPLICATION]) },
      'PATCH /applications/application-1': {
        status: 500,
        body: { detail: 'Server error' },
      },
    })

    renderApplicants()
    await userEvent.selectOptions(
      await screen.findByLabelText(/move to/i),
      'REJECTED',
    )

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('reports a refused pipeline rather than an empty table', async () => {
    // Another HR user's posting answers 404. Rendering that as "no applicants"
    // would read as a role nobody applied to.
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/job-1': { status: 200, body: JOB },
      'GET /jobs/job-1/applications': {
        status: 404,
        body: { detail: 'Job not found' },
      },
    })

    renderApplicants()

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText('Sam Okafor')).not.toBeInTheDocument()
  })

  it('shows an empty state when nobody has applied', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/job-1': { status: 200, body: JOB },
      'GET /jobs/job-1/applications': { status: 200, body: page([]) },
    })

    renderApplicants()

    expect(await screen.findByText(/no one has applied/i)).toBeInTheDocument()
  })

  it('offers every pipeline state', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/job-1': { status: 200, body: JOB },
      'GET /jobs/job-1/applications': { status: 200, body: page([APPLICATION]) },
    })

    renderApplicants()
    const select = await screen.findByLabelText(/move to/i)

    for (const label of ['Submitted', 'Under review', 'Accepted', 'Rejected']) {
      expect(
        screen.getByRole('option', { name: label }),
      ).toBeInTheDocument()
    }
    expect(select).toHaveValue('SUBMITTED')
  })
})
