import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CANDIDATE, HR_USER, JOB, page, renderPage, stubApi } from '../test/harness'
import ManageJobsPage from './ManageJobsPage'

const DRAFT = { ...JOB, id: 'job-2', title: 'Engineering Manager', is_published: false }

const APPLICANT = {
  id: 'application-1',
  job: JOB,
  candidate: CANDIDATE,
  cover_letter: 'Six years of pipeline work.',
  status: 'SUBMITTED' as const,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const SHORTLIST = {
  items: [
    { application: APPLICANT, score: 0.62, matched_terms: ['docker', 'pipeline'] },
  ],
  method: 'keyword-overlap',
}

/** Count POSTs to the contact endpoint. */
function contactCalls(spy: ReturnType<typeof vi.fn>): number {
  return spy.mock.calls.filter(([input, init]) => {
    const url = input instanceof URL ? input : new URL(String(input), 'http://x')
    return (
      url.pathname.endsWith('/contact') &&
      (init as RequestInit | undefined)?.method === 'POST'
    )
  }).length
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('ManageJobsPage', () => {
  it('lists the postings the HR user owns', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/mine': { status: 200, body: page([JOB, DRAFT]) },
    })

    renderPage(<ManageJobsPage />, { as: HR_USER })

    expect(await screen.findByText('Senior Platform Engineer')).toBeInTheDocument()
    expect(screen.getByText('Engineering Manager')).toBeInTheDocument()
  })

  it('marks a draft as such', async () => {
    // The draft/published distinction is the whole reason this view differs
    // from the public list.
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/mine': { status: 200, body: page([DRAFT]) },
    })

    renderPage(<ManageJobsPage />, { as: HR_USER })

    expect(await screen.findByText('Draft')).toBeInTheDocument()
  })

  it('loads the shortlist only once a row is expanded', async () => {
    // Fetching for every posting up front would rank every application on the
    // page to show names the user may never look at.
    const spy = stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/mine': { status: 200, body: page([JOB]) },
      'GET /jobs/job-1/recommendations': { status: 200, body: SHORTLIST },
    })

    renderPage(<ManageJobsPage />, { as: HR_USER })
    const trigger = await screen.findByRole('button', {
      name: /senior platform engineer/i,
    })

    const before = spy.mock.calls.filter(([input]) =>
      String(input).includes('recommendations'),
    ).length
    expect(before).toBe(0)

    await userEvent.click(trigger)

    expect(await screen.findByText('Sam Okafor')).toBeInTheDocument()
  })

  it('shows the match score and the terms behind it', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/mine': { status: 200, body: page([JOB]) },
      'GET /jobs/job-1/recommendations': { status: 200, body: SHORTLIST },
    })

    renderPage(<ManageJobsPage />, { as: HR_USER })
    await userEvent.click(
      await screen.findByRole('button', { name: /senior platform engineer/i }),
    )

    expect(await screen.findByText('62%')).toBeInTheDocument()
    expect(screen.getByText('docker')).toBeInTheDocument()
  })

  it('describes the score as a shortlist aid rather than an assessment', async () => {
    // The API labels its method for the same reason; the UI must not quietly
    // upgrade a keyword count into a judgement of competence.
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/mine': { status: 200, body: page([JOB]) },
      'GET /jobs/job-1/recommendations': { status: 200, body: SHORTLIST },
    })

    renderPage(<ManageJobsPage />, { as: HR_USER })
    await userEvent.click(
      await screen.findByRole('button', { name: /senior platform engineer/i }),
    )

    expect(
      await screen.findByText(/not an assessment/i),
    ).toBeInTheDocument()
  })

  it('prefills the invite rather than opening a blank box', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/mine': { status: 200, body: page([JOB]) },
      'GET /jobs/job-1/recommendations': { status: 200, body: SHORTLIST },
    })

    renderPage(<ManageJobsPage />, { as: HR_USER })
    await userEvent.click(
      await screen.findByRole('button', { name: /senior platform engineer/i }),
    )
    await userEvent.click(await screen.findByLabelText(/select sam okafor/i))
    await userEvent.click(screen.getByRole('button', { name: /invite 1 selected/i }))

    const box = await screen.findByLabelText(/invite 1 candidate/i)

    // Sendable as-is: it names the role and the company, so a recruiter who
    // sends it verbatim has still said something reasonable.
    expect((box as HTMLTextAreaElement).value).toContain('Senior Platform Engineer')
    expect((box as HTMLTextAreaElement).value).toContain('Northwind Labs')
  })

  it('sends one invite per selected candidate', async () => {
    const second = {
      application: { ...APPLICANT, id: 'application-2', candidate: { ...CANDIDATE, id: 'c2', full_name: 'Ravi Menon' } },
      score: 0.4,
      matched_terms: ['postgres'],
    }
    const spy = stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/mine': { status: 200, body: page([JOB]) },
      'GET /jobs/job-1/recommendations': {
        status: 200,
        body: { ...SHORTLIST, items: [SHORTLIST.items[0]!, second] },
      },
      'POST /applications/application-1/contact': { status: 201, body: {} },
      'POST /applications/application-2/contact': { status: 201, body: {} },
    })

    renderPage(<ManageJobsPage />, { as: HR_USER })
    await userEvent.click(
      await screen.findByRole('button', { name: /senior platform engineer/i }),
    )
    await userEvent.click(await screen.findByLabelText(/select all candidates/i))
    await userEvent.click(screen.getByRole('button', { name: /invite 2 selected/i }))
    await userEvent.click(screen.getByRole('button', { name: /send 2 invites/i }))

    await waitFor(() => {
      expect(contactCalls(spy)).toBe(2)
    })
  })

  it('marks the invited and keeps the failures selected', async () => {
    // The decisive property. Reporting a partial send as complete would be a
    // lie the recruiter then acts on — they would never follow up with the
    // people who did not receive it.
    const second = {
      application: { ...APPLICANT, id: 'application-2', candidate: { ...CANDIDATE, id: 'c2', full_name: 'Ravi Menon' } },
      score: 0.4,
      matched_terms: ['postgres'],
    }
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/mine': { status: 200, body: page([JOB]) },
      'GET /jobs/job-1/recommendations': {
        status: 200,
        body: { ...SHORTLIST, items: [SHORTLIST.items[0]!, second] },
      },
      'POST /applications/application-1/contact': { status: 201, body: {} },
      'POST /applications/application-2/contact': {
        status: 500,
        body: { detail: 'Server error' },
      },
    })

    renderPage(<ManageJobsPage />, { as: HR_USER })
    await userEvent.click(
      await screen.findByRole('button', { name: /senior platform engineer/i }),
    )
    await userEvent.click(await screen.findByLabelText(/select all candidates/i))
    await userEvent.click(screen.getByRole('button', { name: /invite 2 selected/i }))
    await userEvent.click(screen.getByRole('button', { name: /send 2 invites/i }))

    // One delivered, one not, and the message says which.
    expect(await screen.findByRole('alert')).toHaveTextContent(/sent 1.*1 failed/i)
    expect(await screen.findByText('Invited')).toBeInTheDocument()
  })

  it('cannot invite the same person twice', async () => {
    // Once invited the checkbox is disabled, so a second pass down the list
    // does not message them again.
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/mine': { status: 200, body: page([JOB]) },
      'GET /jobs/job-1/recommendations': { status: 200, body: SHORTLIST },
      'POST /applications/application-1/contact': { status: 201, body: {} },
    })

    renderPage(<ManageJobsPage />, { as: HR_USER })
    await userEvent.click(
      await screen.findByRole('button', { name: /senior platform engineer/i }),
    )
    await userEvent.click(await screen.findByLabelText(/select sam okafor/i))
    await userEvent.click(screen.getByRole('button', { name: /invite 1 selected/i }))
    await userEvent.click(screen.getByRole('button', { name: /send 1 invite/i }))

    await screen.findByText('Invited')
    expect(screen.getByLabelText(/select sam okafor/i)).toBeDisabled()
  })

  it('says so when there is nothing to rank', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/mine': { status: 200, body: page([JOB]) },
      'GET /jobs/job-1/recommendations': {
        status: 200,
        body: { items: [], method: 'keyword-overlap' },
      },
    })

    renderPage(<ManageJobsPage />, { as: HR_USER })
    await userEvent.click(
      await screen.findByRole('button', { name: /senior platform engineer/i }),
    )

    expect(await screen.findByText(/no applications to rank/i)).toBeInTheDocument()
  })

  it('keeps the row usable when the ranking fails', async () => {
    // A failed shortlist must not take the row's actions down with it.
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/mine': { status: 200, body: page([JOB]) },
      'GET /jobs/job-1/recommendations': {
        status: 500,
        body: { detail: 'Server error' },
      },
    })

    renderPage(<ManageJobsPage />, { as: HR_USER })
    await userEvent.click(
      await screen.findByRole('button', { name: /senior platform engineer/i }),
    )

    expect(await screen.findByRole('link', { name: /edit/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /unpublish/i })).toBeInTheDocument()
  })

  it('shows an empty state before any postings exist', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/mine': { status: 200, body: page([]) },
    })

    renderPage(<ManageJobsPage />, { as: HR_USER })

    expect(
      await screen.findByText(/not posted any roles yet/i),
    ).toBeInTheDocument()
  })
})
