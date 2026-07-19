import { Link, Route, Routes, useNavigate } from 'react-router-dom'

import { AuthProvider } from './auth/AuthProvider'
import ProtectedRoute from './auth/ProtectedRoute'
import { useAuth } from './auth/useAuth'
import JobApplicantsPage from './pages/JobApplicantsPage'
import JobDetailPage from './pages/JobDetailPage'
import JobFormPage from './pages/JobFormPage'
import JobsPage from './pages/JobsPage'
import LoginPage from './pages/LoginPage'
import ManageJobsPage from './pages/ManageJobsPage'
import MyApplicationsPage from './pages/MyApplicationsPage'
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

export default function App() {
  return (
    <AuthProvider>
      <div className="app">
        <Navigation />

        <main className="main">
          <Routes>
            <Route path="/" element={<JobsPage />} />
            <Route path="/jobs/:jobId" element={<JobDetailPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            <Route
              path="/applications"
              element={
                <ProtectedRoute role="CANDIDATE">
                  <MyApplicationsPage />
                </ProtectedRoute>
              }
            />

            <Route
              path="/manage"
              element={
                <ProtectedRoute role="HR">
                  <ManageJobsPage />
                </ProtectedRoute>
              }
            />
            {/* Declared before /manage/:jobId/edit so the literal "new" wins
                the match rather than being read as a job id. */}
            <Route
              path="/manage/new"
              element={
                <ProtectedRoute role="HR">
                  <JobFormPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/manage/:jobId/edit"
              element={
                <ProtectedRoute role="HR">
                  <JobFormPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/manage/:jobId/applicants"
              element={
                <ProtectedRoute role="HR">
                  <JobApplicantsPage />
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
