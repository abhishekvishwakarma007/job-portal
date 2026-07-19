import { Link, Route, Routes, useNavigate } from 'react-router-dom'

import { AuthProvider } from './auth/AuthProvider'
import ProtectedRoute from './auth/ProtectedRoute'
import { useAuth } from './auth/useAuth'
import JobApplicantsPage from './pages/JobApplicantsPage'
import JobDetailPage from './pages/JobDetailPage'
import JobFormPage from './pages/JobFormPage'
import JobsPage from './pages/JobsPage'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import ManageJobsPage from './pages/ManageJobsPage'
import MyApplicationsPage from './pages/MyApplicationsPage'
import NotificationsPage from './pages/NotificationsPage'
import ProfilePage from './pages/ProfilePage'
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

  // Two initials from the display name, so the avatar means something rather
  // than being decoration.
  const initials = user
    ? user.full_name
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase() ?? '')
        .join('')
    : ''

  return (
    <header className="sticky top-0 z-10 border-b border-[color:var(--border)] bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-4 py-3">
        <Link
          to="/"
          className="text-lg font-bold tracking-tight text-slate-900 no-underline"
        >
          Job<span className="text-[color:var(--accent)]">Portal</span>
        </Link>

        <nav
          className="flex flex-wrap items-center gap-4"
          aria-label="Main"
        >
          <Link
            to="/jobs"
            className="text-sm font-medium text-[color:var(--text-muted)] no-underline hover:text-slate-900"
          >
            Browse jobs
          </Link>

          {!isLoading && user?.role === 'CANDIDATE' && (
            <>
              <Link
                to="/applications"
                className="text-sm font-medium text-[color:var(--text-muted)] no-underline hover:text-slate-900"
              >
                My applications
              </Link>
              <Link
                to="/profile"
                className="text-sm font-medium text-[color:var(--text-muted)] no-underline hover:text-slate-900"
              >
                Profile
              </Link>
              <Link
                to="/notifications"
                className="text-sm font-medium text-[color:var(--text-muted)] no-underline hover:text-slate-900"
              >
                Invites
              </Link>
            </>
          )}

          {!isLoading && user?.role === 'HR' && (
            <Link
              to="/manage"
              className="text-sm font-medium text-[color:var(--text-muted)] no-underline hover:text-slate-900"
            >
              My postings
            </Link>
          )}

          {!isLoading && user && (
            <div className="flex items-center gap-3 border-l border-[color:var(--border)] pl-4">
              <span
                aria-hidden="true"
                className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[color:var(--accent)] text-xs font-bold text-white"
              >
                {initials}
              </span>

              <span className="hidden leading-tight sm:block">
                <span className="block text-sm font-semibold text-slate-900">
                  {user.full_name}
                </span>
                <span className="block text-xs text-[color:var(--text-muted)]">
                  {user.role === 'HR' ? 'Hiring team' : 'Candidate'}
                </span>
              </span>

              <button
                type="button"
                onClick={handleLogout}
                className="rounded-lg border border-[color:var(--border)] bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              >
                Sign out
              </button>
            </div>
          )}

          {!isLoading && !user && (
            <>
              <Link
                to="/login"
                className="text-sm font-medium text-[color:var(--text-muted)] no-underline hover:text-slate-900"
              >
                Sign in
              </Link>
              <Link
                to="/register"
                className="rounded-lg bg-[color:var(--accent)] px-4 py-2 text-sm font-semibold text-white no-underline transition hover:opacity-90"
              >
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
            <Route path="/" element={<LandingPage />} />
            {/* Browsing moved off "/" so the landing page can introduce the
                product; the list itself is unchanged. */}
            <Route path="/jobs" element={<JobsPage />} />
            <Route path="/jobs/:jobId" element={<JobDetailPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            <Route
              path="/profile"
              element={
                <ProtectedRoute role="CANDIDATE">
                  <ProfilePage />
                </ProtectedRoute>
              }
            />

            <Route
              path="/notifications"
              element={
                <ProtectedRoute>
                  <NotificationsPage />
                </ProtectedRoute>
              }
            />

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
