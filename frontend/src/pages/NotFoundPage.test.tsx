import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { renderPage } from '../test/harness'
import NotFoundPage from './NotFoundPage'

describe('NotFoundPage', () => {
  it('says the page does not exist', () => {
    renderPage(<NotFoundPage />)

    expect(screen.getByText(/page not found/i)).toBeInTheDocument()
  })

  it('offers a way back to the job list', () => {
    // A dead end with no exit is the worst version of this page.
    renderPage(<NotFoundPage />)

    expect(screen.getByRole('link', { name: /browse jobs/i })).toHaveAttribute(
      'href',
      '/jobs',
    )
  })
})
