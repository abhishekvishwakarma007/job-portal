import { Link, Route, Routes, useNavigate } from 'react-router-dom'

import { AuthProvider } from './auth/AuthProvider'
import ProtectedRoute from './auth/ProtectedRoute'
import { useAuth } from './auth/useAuth'
import JobsPage from './pages/JobsPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import RegisterPage from './pages/RegisterPage'

/**
 * Navigation, which changes with who is signed in.
 *
 * Hiding links a role cannot use is a usability measure. The API gates every
 * endpoint on its own, so this is about not showing people doors they cannot
 * open — not about keeping them out.
 */
function Navigation() {
  const { user, logout, isLoading } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/', { replace: true })
  }

  return (
    <header className="header">
      <div className="header__inner">
        <Link to="/" className="header__brand">
          JobPortal
        </Link>

        <nav className="header__nav" aria-label="Main">
          <Link to="/">Browse jobs</Link>

          {!isLoading && user?.role === 'CANDIDATE' && (
            <Link to="/applications">My applications</Link>
          )}

          {!isLoading && user?.role === 'HR' && (
            <Link to="/manage">My postings</Link>
          )}

          {!isLoading && user && (
            <>
              <span className="muted">
                {user.full_name} · {user.role === 'HR' ? 'HR' : 'Candidate'}
              </span>
              <button
                type="button"
                className="button button--secondary"
                onClick={handleLogout}
              >
                Sign out
              </button>
            </>
          )}

          {!isLoading && !user && (
            <>
              <Link to="/login">Sign in</Link>
              <Link to="/register" className="button">
                Register
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}

/** Placeholder until the jobs and applications UI slice lands. */
function ComingSoon({ title }: { title: string }) {
  return (
    <div className="card empty">
      <h1>{title}</h1>
      <p className="muted">This screen arrives in the next slice.</p>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <div className="app">
        <Navigation />

        <main className="main">
          <Routes>
            <Route path="/" element={<JobsPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            <Route
              path="/applications"
              element={
                <ProtectedRoute role="CANDIDATE">
                  <ComingSoon title="My applications" />
                </ProtectedRoute>
              }
            />

            <Route
              path="/manage"
              element={
                <ProtectedRoute role="HR">
                  <ComingSoon title="My postings" />
                </ProtectedRoute>
              }
            />

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>
      </div>
    </AuthProvider>
  )
}
