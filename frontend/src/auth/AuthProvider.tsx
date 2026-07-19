import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { request, setAuthToken } from '../lib/api'
import type { Token, User } from '../types'
import { AuthContext, type AuthState, type RegisterInput } from './context'
import { clearToken, readToken, writeToken } from './storage'

/**
 * Holds the signed-in user for the whole app.
 *
 * The stored token is never trusted on its own: on boot it is exchanged for
 * /auth/me, so a token that expired, was revoked, or belongs to a deactivated
 * account resolves to signed-out rather than a UI that renders as if signed in
 * and then 401s on every action.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const token = readToken()

    if (!token) {
      setIsLoading(false)
      return
    }

    setAuthToken(token)
    let cancelled = false

    async function restore() {
      try {
        const me = await request<User>('/auth/me')
        if (!cancelled) setUser(me)
      } catch {
        // Any failure here means the token is unusable. Drop it rather than
        // leaving a dead credential to fail every subsequent request.
        if (!cancelled) {
          clearToken()
          setAuthToken(null)
          setUser(null)
        }
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void restore()
    return () => {
      cancelled = true
    }
  }, [])

  /** Store the token and resolve the account it belongs to. */
  const establishSession = useCallback(async (accessToken: string) => {
    writeToken(accessToken)
    setAuthToken(accessToken)

    // Read the user from the server rather than decoding the token: the role
    // in a token can be stale, and the server is the authority on it.
    const me = await request<User>('/auth/me')
    setUser(me)
    return me
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const token = await request<Token>('/auth/login', {
        method: 'POST',
        body: { email, password },
      })
      return establishSession(token.access_token)
    },
    [establishSession],
  )

  const register = useCallback(
    async (input: RegisterInput) => {
      await request<User>('/auth/register', { method: 'POST', body: input })
      // Registration does not return a token, so sign in with the same
      // credentials — the user should not have to log in immediately after.
      return login(input.email, input.password)
    },
    [login],
  )

  const logout = useCallback(() => {
    clearToken()
    setAuthToken(null)
    setUser(null)
  }, [])

  const value = useMemo<AuthState>(
    () => ({ user, isLoading, login, register, logout }),
    [user, isLoading, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
