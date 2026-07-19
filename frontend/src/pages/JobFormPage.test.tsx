import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { HR_USER, JOB, renderPage, stubApi } from '../test/harness'
import JobFormPage from './JobFormPage'

/** The parsed JSON body of the last write, with its method. */
function lastWrite(spy: ReturnType<typeof vi.fn>): {
  method: string
  body: Record<string, unknown>
} | null {
  const writes = spy.mock.calls.filter(([, init]) =>
    ['POST', 'PATCH'].includes((init as RequestInit | undefined)?.method ?? ''),
  )
  const last = writes[writes.length - 1]
  if (!last) return null

  const init = last[1] as RequestInit
  return {
    method: String(init.method),
    body: JSON.parse(String(init.body)) as Record<string, unknown>,
  }
}

async function fillRequired() {
  await userEvent.type(screen.getByLabelText('Title'), 'Staff Engineer')
  await userEvent.type(screen.getByLabelText('Company'), 'Northwind Labs')
  await userEvent.type(screen.getByLabelText('Location'), 'Remote')
  await userEvent.type(screen.getByLabelText('Description'), 'Own the pipeline.')
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('JobFormPage — creating', () => {
  it('POSTs the completed form', async () => {
    const spy = stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs': { status: 200, body: { items: [], total: 0 } },
      'POST /jobs': { status: 201, body: JOB },
    })

    renderPage(<JobFormPage />, { as: HR_USER, route: '/manage/new' })
    await fillRequired()
    await userEvent.click(screen.getByRole('button', { name: /post role/i }))

    await waitFor(() => {
      const write = lastWrite(spy)
      expect(write?.method).toBe('POST')
      expect(write?.body.title).toBe('Staff Engineer')
      expect(write?.body.company).toBe('Northwind Labs')
    })
  })

  it('sends is_published true when publish is left ticked', async () => {
    // The checkbox is the difference between a live posting and a draft, so
    // its mapping into the body is worth pinning rather than assuming.
    const spy = stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs': { status: 200, body: { items: [], total: 0 } },
      'POST /jobs': { status: 201, body: JOB },
    })

    renderPage(<JobFormPage />, { as: HR_USER, route: '/manage/new' })
    await fillRequired()
    await userEvent.click(screen.getByRole('button', { name: /post role/i }))

    await waitFor(() => {
      expect(lastWrite(spy)?.body.is_published).toBe(true)
    })
  })

  it('sends is_published false when publish is unticked', async () => {
    const spy = stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs': { status: 200, body: { items: [], total: 0 } },
      'POST /jobs': { status: 201, body: JOB },
    })

    renderPage(<JobFormPage />, { as: HR_USER, route: '/manage/new' })
    await fillRequired()
    await userEvent.click(screen.getByLabelText(/publish immediately/i))
    await userEvent.click(screen.getByRole('button', { name: /post role/i }))

    await waitFor(() => {
      expect(lastWrite(spy)?.body.is_published).toBe(false)
    })
  })

  it('blocks submission on a missing required field', async () => {
    // Client validation exists so the user is told before a round trip.
    const spy = stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs': { status: 200, body: { items: [], total: 0 } },
    })

    renderPage(<JobFormPage />, { as: HR_USER, route: '/manage/new' })
    await userEvent.type(screen.getByLabelText('Title'), 'Staff Engineer')
    await userEvent.click(screen.getByRole('button', { name: /post role/i }))

    expect(await screen.findByText('Company is required.')).toBeInTheDocument()
    expect(lastWrite(spy)).toBeNull()
  })

  it('shows the server field error when the client check passed', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs': { status: 200, body: { items: [], total: 0 } },
      'POST /jobs': {
        status: 422,
        body: {
          detail: [{ loc: ['body', 'title'], msg: 'Title is already in use' }],
        },
      },
    })

    renderPage(<JobFormPage />, { as: HR_USER, route: '/manage/new' })
    await fillRequired()
    await userEvent.click(screen.getByRole('button', { name: /post role/i }))

    expect(await screen.findByText(/already in use/i)).toBeInTheDocument()
  })

  it('keeps the form on screen when saving fails', async () => {
    // Navigating away on failure would discard everything just typed.
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs': { status: 200, body: { items: [], total: 0 } },
      'POST /jobs': { status: 500, body: { detail: 'Server error' } },
    })

    renderPage(<JobFormPage />, { as: HR_USER, route: '/manage/new' })
    await fillRequired()
    await userEvent.click(screen.getByRole('button', { name: /post role/i }))

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByLabelText('Title')).toHaveValue('Staff Engineer')
  })
})

describe('JobFormPage — editing', () => {
  it('prefills from the posting being edited', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/job-1': { status: 200, body: JOB },
    })

    renderPage(<JobFormPage />, {
      as: HR_USER,
      route: '/manage/job-1/edit',
      path: '/manage/:jobId/edit',
    })

    await waitFor(() => {
      expect(screen.getByLabelText('Title')).toHaveValue(
        'Senior Platform Engineer',
      )
    })
    expect(screen.getByLabelText('Company')).toHaveValue('Northwind Labs')
  })

  it('PATCHes rather than POSTs', async () => {
    // Same component serves both routes; sending the wrong verb would create a
    // duplicate posting instead of editing one.
    const spy = stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/job-1': { status: 200, body: JOB },
      'PATCH /jobs/job-1': { status: 200, body: JOB },
    })

    renderPage(<JobFormPage />, {
      as: HR_USER,
      route: '/manage/job-1/edit',
      path: '/manage/:jobId/edit',
    })
    await waitFor(() => {
      expect(screen.getByLabelText('Title')).toHaveValue(
        'Senior Platform Engineer',
      )
    })

    await userEvent.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => {
      expect(lastWrite(spy)?.method).toBe('PATCH')
    })
  })

  it('reports a failed load instead of an empty form', async () => {
    // A blank form here would look like a new posting, and saving it would
    // create one rather than edit the intended role.
    stubApi({
      'GET /auth/me': { status: 200, body: HR_USER },
      'GET /jobs/job-1': { status: 404, body: { detail: 'Job not found' } },
    })

    renderPage(<JobFormPage />, {
      as: HR_USER,
      route: '/manage/job-1/edit',
      path: '/manage/:jobId/edit',
    })

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByLabelText('Title')).not.toBeInTheDocument()
  })
})
