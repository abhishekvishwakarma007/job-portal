import { screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CANDIDATE, JOB, page, renderPage, stubApi } from '../test/harness'
import MyApplicationsPage from './MyApplicationsPage'

const APPLICATION = {
  id: 'application-1',
  job: JOB,
  candidate: CANDIDATE,
  cover_letter: 'Six years of pipeline work.',
  status: 'UNDER_REVIEW' as const,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

beforeEach(() => window.localStorage.clear())
afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('MyApplicationsPage', () => {
  it('lists the roles applied to with their status', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /applications/mine': { status: 200, body: page([APPLICATION]) },
    })

    renderPage(<MyApplicationsPage />, { as: CANDIDATE })

    expect(await screen.findByText('Senior Platform Engineer')).toBeInTheDocument()
    expect(screen.getByText('Under review')).toBeInTheDocument()
  })

  it('links each application to its posting', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /applications/mine': { status: 200, body: page([APPLICATION]) },
    })

    renderPage(<MyApplicationsPage />, { as: CANDIDATE })

    expect(
      await screen.findByRole('link', { name: /senior platform engineer/i }),
    ).toHaveAttribute('href', `/jobs/${JOB.id}`)
  })

  it('shows an empty state before applying to anything', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /applications/mine': { status: 200, body: page([]) },
    })

    renderPage(<MyApplicationsPage />, { as: CANDIDATE })

    expect(
      await screen.findByText(/not applied to any roles/i),
    ).toBeInTheDocument()
  })

  it('reports a failed load rather than looking like no applications', async () => {
    // An unhandled error here reads as "you have applied to nothing", which is
    // a materially different and alarming message.
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /applications/mine': { status: 500, body: { detail: 'Server error' } },
    })

    renderPage(<MyApplicationsPage />, { as: CANDIDATE })

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
