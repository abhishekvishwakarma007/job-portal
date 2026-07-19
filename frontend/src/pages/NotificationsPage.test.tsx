import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CANDIDATE, JOB, page, renderPage, stubApi } from '../test/harness'
import NotificationsPage from './NotificationsPage'

const INVITE = {
  id: 'notification-1',
  subject: 'Update on your application for Senior Platform Engineer',
  body: 'We would like to invite you to a first interview.\n\n— Dana Reyes, Northwind Labs',
  is_read: false,
  job_id: JOB.id,
  created_at: '2026-01-01T00:00:00Z',
}

function inbox(items: unknown[], unread: number) {
  return { ...page(items), unread }
}

beforeEach(() => {
  window.localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  window.localStorage.clear()
})

describe('NotificationsPage', () => {
  it('names the role rather than echoing the subject line', async () => {
    // The notification stores only a job_id, so the page resolves it — the
    // card leads with what someone scanning ten of these actually needs.
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /notifications/mine': { status: 200, body: inbox([INVITE], 1) },
      'GET /jobs': { status: 200, body: page([JOB]) },
    })

    renderPage(<NotificationsPage />, { as: CANDIDATE })

    expect(await screen.findByText('Senior Platform Engineer')).toBeInTheDocument()
    // The header line specifically — the company also appears in the message
    // signature, so a loose matcher finds both.
    expect(screen.getByText('Northwind Labs · Remote')).toBeInTheDocument()
  })

  it('shows the recruiter message', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /notifications/mine': { status: 200, body: inbox([INVITE], 1) },
      'GET /jobs': { status: 200, body: page([JOB]) },
    })

    renderPage(<NotificationsPage />, { as: CANDIDATE })

    expect(
      await screen.findByText(/invite you to a first interview/i),
    ).toBeInTheDocument()
  })

  it('counts what is unread', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /notifications/mine': { status: 200, body: inbox([INVITE], 1) },
      'GET /jobs': { status: 200, body: page([JOB]) },
    })

    renderPage(<NotificationsPage />, { as: CANDIDATE })

    expect(await screen.findByText('1 new')).toBeInTheDocument()
  })

  it('offers mark-as-read only while unread', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /notifications/mine': {
        status: 200,
        body: inbox([{ ...INVITE, is_read: true }], 0),
      },
      'GET /jobs': { status: 200, body: page([JOB]) },
    })

    renderPage(<NotificationsPage />, { as: CANDIDATE })
    await screen.findByText('Senior Platform Engineer')

    expect(
      screen.queryByRole('button', { name: /mark as read/i }),
    ).not.toBeInTheDocument()
  })

  it('marks an invite read', async () => {
    const spy = stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /notifications/mine': { status: 200, body: inbox([INVITE], 1) },
      'GET /jobs': { status: 200, body: page([JOB]) },
      'PATCH /notifications/notification-1/read': {
        status: 200,
        body: { ...INVITE, is_read: true },
      },
    })

    renderPage(<NotificationsPage />, { as: CANDIDATE })
    await userEvent.click(
      await screen.findByRole('button', { name: /mark as read/i }),
    )

    await waitFor(() => {
      const marked = spy.mock.calls.some(([input, init]) => {
        const url = input instanceof URL ? input : new URL(String(input), 'http://x')
        return (
          url.pathname.endsWith('/read') &&
          (init as RequestInit | undefined)?.method === 'PATCH'
        )
      })
      expect(marked).toBe(true)
    })
  })

  it('links through to the role', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /notifications/mine': { status: 200, body: inbox([INVITE], 1) },
      'GET /jobs': { status: 200, body: page([JOB]) },
    })

    renderPage(<NotificationsPage />, { as: CANDIDATE })

    expect(await screen.findByRole('link', { name: /view role/i })).toHaveAttribute(
      'href',
      `/jobs/${JOB.id}`,
    )
  })

  it('still renders when the posting is gone', async () => {
    // Deleting a job nulls the notification job_id rather than cascading, so
    // an invite about a closed role has to survive without one.
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /notifications/mine': {
        status: 200,
        body: inbox([{ ...INVITE, job_id: null }], 1),
      },
      'GET /jobs': { status: 200, body: page([]) },
    })

    renderPage(<NotificationsPage />, { as: CANDIDATE })

    // Falls back to the subject, and offers no dead "View role" link.
    expect(await screen.findByText(INVITE.subject)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /view role/i })).not.toBeInTheDocument()
  })

  it('shows an empty state rather than a blank page', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /notifications/mine': { status: 200, body: inbox([], 0) },
      'GET /jobs': { status: 200, body: page([]) },
    })

    renderPage(<NotificationsPage />, { as: CANDIDATE })

    expect(await screen.findByText(/no invites yet/i)).toBeInTheDocument()
  })

  it('reports a failed load', async () => {
    stubApi({
      'GET /auth/me': { status: 200, body: CANDIDATE },
      'GET /notifications/mine': { status: 500, body: { detail: 'Server error' } },
      'GET /jobs': { status: 200, body: page([]) },
    })

    renderPage(<NotificationsPage />, { as: CANDIDATE })

    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
