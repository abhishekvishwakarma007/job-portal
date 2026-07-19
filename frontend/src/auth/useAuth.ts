import { useContext } from 'react'

import { AuthContext, type AuthState } from './context'

/** Access the auth state. Throws outside an <AuthProvider>. */
export function useAuth(): AuthState {
  const context = useContext(AuthContext)

  if (!context) {
    // Naming the cause beats "cannot read properties of null" from whichever
    // component happened to call it.
    throw new Error('useAuth must be used inside an <AuthProvider>')
  }

  return context
}
