import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CANDIDATE, JOB, page, renderPage, stubApi } from '../test/harness'
import JobsPage from './JobsPage'

/** The query string the most recent /jobs call was made with. */
function lastJobsQuery(spy: ReturnType<typeof vi.fn>): URLSearchParams {
  const calls = spy.mock.calls.filter(([input]) => {
    const url = input instanceof URL ? input : new URL(String(input), 'http://x')
    return url.pathname.endsWith('/jobs')
  })
  const last = calls[calls.length - 1]?.[0] as URL

  return last.searchParams
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('JobsPage', () => {
  it('lists the roles it fetched', async () => {
    stubApi({ 'GET /jobs': { status: 200, body: page([JOB]) } })

    renderPage(<JobsPage />)

    expect(await screen.findByText('Senior Platform Engineer')).toBeInTheDocument()
    expect(screen.getByText(/Northwind Labs/)).toBeInTheDocument()
  })

  it('says so when nothing matches rather than rendering blank', async () => {
    stubApi({ 'GET /jobs': { status: 200, body: page([]) } })

    renderPage(<JobsPage />)

    expect(await screen.findByText(/no roles have been posted/i)).toBeInTheDocument()
  })

  it('reports a failed fetch instead of looking empty', async () => {
    // An unhandled error state renders as an empty page, which reads as
    // "there is nothing here" rather than "this did not load".
    stubApi({ 'GET /jobs': { status: 500, body: { detail: 'Server error' } } })

    renderPage(<JobsPage />)

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('sends the title filter to the server, not the browser', async () => {
    // Filtering client-side would leave the total and pagination describing a
    // different set than the one on screen.
    const spy = stubApi({ 'GET /jobs': { status: 200, body: page([JOB]) } })

    renderPage(<JobsPage />)
    await screen.findByText('Senior Platform Engineer')

    await userEvent.type(screen.getByLabelText(/title/i), 'engineer')

    await waitFor(() => {
      expect(lastJobsQuery(spy).get('search')).toBe('engineer')
    })
  })

  it('combines every filter in one request', async () => {
    const spy = stubApi({ 'GET /jobs': { status: 200, body: page([JOB]) } })

    renderPage(<JobsPage />)
    await screen.findByText('Senior Platform Engineer')

    await userEvent.type(screen.getByLabelText(/company/i), 'northwind')
    await userEvent.type(screen.getByLabelText(/location/i), 'remote')
    await userEvent.selectOptions(
      screen.getByLabelText(/employment type/i),
      'FULL_TIME',
    )

    await waitFor(() => {
      const query = lastJobsQuery(spy)
      expect(query.get('company')).toBe('northwind')
      expect(query.get('location')).toBe('remote')
      expect(query.get('employment_type')).toBe('FULL_TIME')
    })
  })

  it('debounces typing into one request rather than one per keystroke', async () => {
    const spy = stubApi({ 'GET /jobs': { status: 200, body: page([JOB]) } })

    renderPage(<JobsPage />)
    await screen.findByText('Senior Platform Engineer')

    const before = spy.mock.calls.length
    await userEvent.type(screen.getByLabelText(/title/i), 'engineer')

    await waitFor(() => {
      expect(lastJobsQuery(spy).get('search')).toBe('engineer')
    })

    // Eight characters typed. Debouncing should collapse them into a single
    // trailing request; allowing up to two tolerates a race between the
    // initial value settling and the debounce firing, without permitting the
    // seven-of-eight that a broken debounce would produce.
    expect(spy.mock.calls.length - before).toBeLessThanOrEqual(2)
  })

  it('offers to clear filters only once one is set', async () => {
    stubApi({ 'GET /jobs': { status: 200, body: page([JOB]) } })

    renderPage(<JobsPage />)
    await screen.findByText('Senior Platform Engineer')

    expect(
      screen.queryByRole('button', { name: /clear filters/i }),
    ).not.toBeInTheDocument()

    await userEvent.type(screen.getByLabelText(/title/i), 'engineer')

    expect(
      await screen.findByRole('button', { name: /clear filters/i }),
    ).toBeInTheDocument()
  })

  it('expands a row to reveal the description', async () => {
    stubApi({ 'GET /jobs': { status: 200, body: page([JOB]) } })

    renderPage(<JobsPage />)
    const trigger = await screen.findByRole('button', {
      name: /senior platform engineer/i,
    })

    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(trigger)

    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText(/own the deployment pipeline/i)).toBeInTheDocument()
  })

  it('keeps only one row open at a time', async () => {
    // Several open at once means the apply forms scroll past each other and it
    // stops being obvious which one is being submitted.
    const second = { ...JOB, id: 'job-2', title: 'Product Designer' }
    stubApi({ 'GET /jobs': { status: 200, body: page([JOB, second]) } })

    renderPage(<JobsPage />)
    const first = await screen.findByRole('button', {
      name: /senior platform engineer/i,
    })
    await userEvent.click(first)

    await userEvent.click(screen.getByRole('button', { name: /product designer/i }))

    expect(first).toHaveAttribute('aria-expanded', 'false')
  })

  it('shows an anonymous visitor a sign-in prompt, not an apply form', async () => {
    stubApi({ 'GET /jobs': { status: 200, body: page([JOB]) } })

    renderPage(<JobsPage />)
    await userEvent.click(
      await screen.findByRole('button', { name: /senior platform engineer/i }),
    )

    expect(screen.getByText(/sign in/i)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /apply for this role/i }),
    ).not.toBeInTheDocument()
  })

  it('lets a signed-in candidate apply from the list', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /jobs': { status: 200, body: page([JOB]) },
      'POST /applications': { status: 201, body: { id: 'application-1' } },
    })

    renderPage(<JobsPage />, { as: CANDIDATE })
    await userEvent.click(
      await screen.findByRole('button', { name: /senior platform engineer/i }),
    )

    await userEvent.type(
      await screen.findByLabelText(/cover letter/i),
      'Six years of pipeline work.',
    )
    await userEvent.click(
      screen.getByRole('button', { name: /apply for this role/i }),
    )

    expect(await screen.findByRole('status')).toHaveTextContent(
      /application submitted/i,
    )
  })

  it('treats a duplicate-apply 409 as submitted, not as an error', async () => {
    // The outcome the candidate wanted is already true, so a red failure would
    // be both confusing and wrong.
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /jobs': { status: 200, body: page([JOB]) },
      'POST /applications': {
        status: 409,
        body: { detail: 'You have already applied to this job' },
      },
    })

    renderPage(<JobsPage />, { as: CANDIDATE })
    await userEvent.click(
      await screen.findByRole('button', { name: /senior platform engineer/i }),
    )
    await userEvent.type(
      await screen.findByLabelText(/cover letter/i),
      'Applying twice by mistake.',
    )
    await userEvent.click(
      screen.getByRole('button', { name: /apply for this role/i }),
    )

    expect(await screen.findByRole('status')).toHaveTextContent(
      /application submitted/i,
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
