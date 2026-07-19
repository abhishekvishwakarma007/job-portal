/**
 * Client-side mirror of the server's password policy.
 *
 * This is a convenience, not a control: the API is reachable directly, so the
 * server enforces the same rules and is the authority. Duplicating them here
 * only means the user is told before submitting rather than after.
 *
 * These constants must track backend/app/schemas/auth.py. Drift shows up as a
 * form that accepts a password the server then rejects, which reads as a bug.
 */

export const MIN_PASSWORD_LENGTH = 8
export const MAX_PASSWORD_BYTES = 72
export const REQUIRED_CHARACTER_CLASSES = 3

export const PASSWORD_HINT =
  'At least 8 characters, using 3 of: lowercase, uppercase, digit, symbol.'

/** Count how many of the four character classes appear. */
function countCharacterClasses(password: string): number {
  const classes = [
    /[a-z]/.test(password),
    /[A-Z]/.test(password),
    /[0-9]/.test(password),
    /[^A-Za-z0-9]/.test(password),
  ]

  return classes.filter(Boolean).length
}

/** Return an error message, or null when the password is acceptable. */
export function validatePassword(password: string): string | null {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`
  }

  // Byte length, not character length: bcrypt's limit is on bytes, and one
  // emoji costs four of them.
  if (new TextEncoder().encode(password).length > MAX_PASSWORD_BYTES) {
    return `Password must be at most ${MAX_PASSWORD_BYTES} bytes.`
  }

  if (countCharacterClasses(password) < REQUIRED_CHARACTER_CLASSES) {
    return `Password must contain at least ${REQUIRED_CHARACTER_CLASSES} of: lowercase, uppercase, digit, symbol.`
  }

  return null
}

/** Return an error message, or null when the address looks usable. */
export function validateEmail(email: string): string | null {
  if (!email.trim()) return 'Email is required.'

  // Deliberately loose. The server does real validation; a strict regex here
  // would reject valid addresses and is a well-known way to lock people out.
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return 'Enter a valid email address.'
  }

  return null
}

/** Return an error message, or null when the name is usable. */
export function validateFullName(fullName: string): string | null {
  if (!fullName.trim()) return 'Full name is required.'
  if (fullName.length > 120) return 'Full name must be at most 120 characters.'

  return null
}
