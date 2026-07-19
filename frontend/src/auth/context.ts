import { createContext } from 'react'

import type { User, UserRole } from '../types'

export interface RegisterInput {
  email: string
  password: string
  full_name: string
  role: UserRole
}

export interface AuthState {
  user: User | null
  /** True until the stored token has been checked against the server. */
  isLoading: boolean
  login: (email: string, password: string) => Promise<User>
  register: (input: RegisterInput) => Promise<User>
  logout: () => void
}

/**
 * The context object itself, kept apart from both the provider component and
 * the hook. A module that exports a component alongside anything else breaks
 * react-refresh, which then reloads the whole page on every edit instead of
 * preserving state.
 */
export const AuthContext = createContext<AuthState | null>(null)
