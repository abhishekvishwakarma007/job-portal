import { render, type RenderResult } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

import { AuthProvider } from '../auth/AuthProvider'

/**
 * Shared test setup.
 *
 * Every page test needs the same three things: a router, an auth provider, and
 * a fetch stub routed by method and path. Written once here so a page test is
 * about the page rather than about wiring.
 */

export const CANDIDATE = {
  id: 'candidate-1',
  email: 'user@test.com',
  full_name: 'Sam Okafor',
  role: 'CANDIDATE' as const,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
}

export const HR_USER = {
  id: 'hr-1',
  email: 'admin@test.com',
  full_name: 'Dana Reyes',
  role: 'HR' as const,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
}

export const JOB = {
  id: 'job-1',
  title: 'Senior Platform Engineer',
  company: 'Northwind Labs',
  description: 'Own the deployment pipeline.',
  location: 'Remote',
  employment_type: 'FULL_TIME' as const,
  is_published: true,
  created_by: HR_USER,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

export interface StubbedRoute {
  status: number
  body: unknown
}

/**
 * Stub fetch, keyed by "METHOD /path".
 *
 * Query strings are stripped from the key but kept on the recorded call, so a
 * test can assert which filters were sent without every route key having to
 * spell them out.
 */
export function stubApi(
  routes: Record<string, StubbedRoute>,
): ReturnType<typeof vi.fn> {
  const spy = vi.fn(async (input: URL | string, init?: RequestInit) => {
    const url = input instanceof URL ? input : new URL(input, 'http://localhost')
    const path = url.pathname.replace('/api/v1', '')
    const key = `${init?.method ?? 'GET'} ${path}`
    const match = routes[key] ?? { status: 404, body: { detail: 'not found' } }

    return {
      ok: match.status >= 200 && match.status < 300,
      status: match.status,
      text: async () => (match.body === null ? '' : JSON.stringify(match.body)),
    } as Response
  })

  vi.stubGlobal('fetch', spy)
  return spy
}

/** A page of results, in the shape the API returns. */
export function page<T>(items: T[], extra: Record<string, unknown> = {}) {
  return { items, total: items.length, limit: 20, offset: 0, ...extra }
}

interface RenderOptions {
  /** Sign in as this user, or stay anonymous when omitted. */
  as?: typeof CANDIDATE | typeof HR_USER
  /** Initial router entry, for pages that read route params. */
  route?: string
  /** Route pattern, when the component expects params. */
  path?: string
}

/**
 * Render a page inside a router and an auth provider.
 *
 * `as` seeds the stored token, which AuthProvider exchanges for /auth/me — so
 * the caller must stub that route too. That indirection is deliberate: it is
 * the real sign-in path, and stubbing around it would let a test pass against
 * a provider that never verified anything.
 */
export function renderPage(
  element: ReactElement,
  { as, route = '/', path }: RenderOptions = {},
): RenderResult {
  if (as) {
    window.localStorage.setItem('jobportal.access_token', 'test-token')
  }

  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[route]}>
        {path ? (
          <Routes>
            <Route path={path} element={element} />
          </Routes>
        ) : (
          element
        )}
      </MemoryRouter>
    </AuthProvider>,
  )
}
