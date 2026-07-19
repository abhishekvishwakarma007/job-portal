/**
 * Where the access token lives between page loads.
 *
 * localStorage is a deliberate trade-off, not an oversight. It is readable by
 * any script on the origin, so a successful XSS can steal the token — which is
 * why the CSP forbids inline and third-party scripts. The alternative, an
 * httpOnly cookie, resists XSS but requires CSRF protection on every mutating
 * request and a same-site story for the API. For an assessment stack where
 * both halves are served from one origin, the simpler surface is the better
 * trade; a production deployment holding real candidate data should move to
 * httpOnly refresh cookies. This is called out in the README.
 */

const TOKEN_KEY = 'jobportal.access_token'

/** Read the stored token, or null when absent or storage is unavailable. */
export function readToken(): string | null {
  try {
    return window.localStorage.getItem(TOKEN_KEY)
  } catch {
    // Safari in private mode throws on access rather than returning null.
    // Failing to "not signed in" beats crashing the app on boot.
    return null
  }
}

export function writeToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token)
  } catch {
    // Storage full or blocked: the session still works for this page load,
    // it just will not survive a refresh. Not worth failing the login over.
  }
}

export function clearToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Nothing useful to do; the in-memory token is cleared regardless.
  }
}
