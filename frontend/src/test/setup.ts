import '@testing-library/jest-dom/vitest'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// React Testing Library does not unmount between tests automatically under
// Vitest's globals, and a left-over tree makes the next test's queries match
// the previous render.
afterEach(() => {
  cleanup()
})
