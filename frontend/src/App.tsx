import { Link, Route, Routes } from 'react-router-dom'

import JobsPage from './pages/JobsPage'
import NotFoundPage from './pages/NotFoundPage'

/**
 * Application shell and routing.
 *
 * Auth-aware navigation and protected routes arrive with the auth slice; for
 * now this mounts the public job browse so the container has something real to
 * serve and the API wiring can be verified end to end.
 */
export default function App() {
  return (
    <div className="app">
      <header className="header">
        <div className="header__inner">
          <Link to="/" className="header__brand">
            JobPortal
          </Link>
          <nav className="header__nav" aria-label="Main">
            <Link to="/">Browse jobs</Link>
          </nav>
        </div>
      </header>

      <main className="main">
        <Routes>
          <Route path="/" element={<JobsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  )
}
