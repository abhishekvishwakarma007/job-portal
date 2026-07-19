import { Navigate, useLocation } from 'react-router-dom'

import type { UserRole } from '../types'
import { useAuth } from './useAuth'

interface ProtectedRouteProps {
  children: React.ReactNode
  /** When given, the signed-in user must hold this role. */
  role?: UserRole
}

/**
 * Gate a route on being signed in, and optionally on holding a role.
 *
 * This is navigation, not security. Hiding a route stops a candidate wandering
 * into an HR screen; it does not stop them calling the API, which is why the
 * backend gates every endpoint independently. Removing this component would
 * make the app confusing, not insecure.
 */
export default function ProtectedRoute({ children, role }: ProtectedRouteProps) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  // The token is still being exchanged for a user. Rendering the redirect now
  // would bounce a signed-in user to the login screen on every refresh.
  if (isLoading) {
    return <p className="muted">Loading…</p>
  }

  if (!user) {
    // `state` carries where they were headed so login can return them there
    // instead of dumping everyone on the home page.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (role && user.role !== role) {
    return (
      <div className="card empty">
        <h1>Not available for your account</h1>
        <p className="muted">
          This page is for {role === 'HR' ? 'HR' : 'candidate'} accounts.
        </p>
      </div>
    )
  }

  return <>{children}</>
}
