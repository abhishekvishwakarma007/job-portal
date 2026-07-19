import { screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CANDIDATE, JOB, page, renderPage, stubApi } from '../test/harness'
import LandingPage from './LandingPage'

beforeEach(() => window.localStorage.clear())
afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('LandingPage', () => {
  it('shows the live count rather than placeholder copy', async () => {
    stubApi({ 'GET /jobs': { status: 200, body: page([JOB], { total: 4 }) } })

    renderPage(<LandingPage />)

    expect(await screen.findByText(/4 open roles/i)).toBeInTheDocument()
  })

  it('leads to the job list', async () => {
    stubApi({ 'GET /jobs': { status: 200, body: page([JOB]) } })

    renderPage(<LandingPage />)

    expect(
      screen.getByRole('link', { name: /browse open roles/i }),
    ).toHaveAttribute('href', '/jobs')
  })

  it('invites an anonymous visitor to register', async () => {
    stubApi({ 'GET /jobs': { status: 200, body: page([JOB]) } })

    renderPage(<LandingPage />)

    expect(
      screen.getByRole('link', { name: /create an account/i }),
    ).toHaveAttribute('href', '/register')
  })

  it('does not ask a signed-in user to register again', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /jobs': { status: 200, body: page([JOB]) },
    })

    renderPage(<LandingPage />, { as: CANDIDATE })

    await screen.findByRole('link', { name: /browse open roles/i })
    expect(
      screen.queryByRole('link', { name: /create an account/i }),
    ).not.toBeInTheDocument()
  })

  it('features real postings', async () => {
    stubApi({ 'GET /jobs': { status: 200, body: page([JOB]) } })

    renderPage(<LandingPage />)

    expect(await screen.findByText('Senior Platform Engineer')).toBeInTheDocument()
    expect(screen.getByText(/Northwind Labs/)).toBeInTheDocument()
  })

  it('omits the openings section when there are none', async () => {
    // An empty install should not advertise its emptiness.
    stubApi({ 'GET /jobs': { status: 200, body: page([]) } })

    renderPage(<LandingPage />)

    await screen.findByRole('link', { name: /browse open roles/i })
    expect(screen.queryByText(/latest openings/i)).not.toBeInTheDocument()
  })
})
