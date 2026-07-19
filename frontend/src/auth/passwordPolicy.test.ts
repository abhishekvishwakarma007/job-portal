import { describe, expect, it } from 'vitest'

import { validateEmail, validateFullName, validatePassword } from './passwordPolicy'

/**
 * These cases mirror backend/tests/test_auth_api.py. If the two drift, the form
 * accepts something the server rejects, which surfaces to the user as a
 * mysterious failure after submitting a form that looked fine.
 */
describe('validatePassword', () => {
  it.each([
    ['Admin@1234', 'the HR credential the brief publishes'],
    ['User@1234', 'the candidate credential the brief publishes'],
    ['Passw0rd', 'exactly at the floor with three classes'],
    ['correct-horse-battery-staple-7', 'a long passphrase with no capital'],
  ])('accepts %s (%s)', (password) => {
    expect(validatePassword(password)).toBeNull()
  })

  it.each([
    ['short', /at least 8/i],
    ['alllowercaseletters', /3 of/i],
    ['1234567890123456', /3 of/i],
    ['password1', /3 of/i],
  ])('rejects %s', (password, expected) => {
    expect(validatePassword(password)).toMatch(expected)
  })

  it('measures the bcrypt limit in bytes, not characters', () => {
    // 20 four-byte emoji is 80 bytes but only 20 characters. Counting
    // characters would let this through to a server that refuses it.
    const password = 'Aa1' + '😀'.repeat(20)

    expect(validatePassword(password)).toMatch(/72 bytes/)
  })
})

describe('validateEmail', () => {
  it.each(['candidate@test.com', 'first.last+tag@sub.example.org'])(
    'accepts %s',
    (email) => {
      expect(validateEmail(email)).toBeNull()
    },
  )

  it.each(['', 'not-an-email', '@test.com', 'spaces in@test.com'])(
    'rejects %s',
    (email) => {
      expect(validateEmail(email)).not.toBeNull()
    },
  )
})

describe('validateFullName', () => {
  it('accepts a normal name', () => {
    expect(validateFullName('Dana Reyes')).toBeNull()
  })

  it('rejects an empty or whitespace-only name', () => {
    expect(validateFullName('   ')).toMatch(/required/i)
  })

  it('rejects a name beyond the column length', () => {
    expect(validateFullName('x'.repeat(121))).toMatch(/120/)
  })
})
