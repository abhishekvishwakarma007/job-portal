/**
 * Field limits, mirrored from the backend schemas.
 *
 * These were previously written inline at each `maxLength`, which meant the
 * same number appearing in several components with nothing tying them
 * together — and nothing at all tying them to the server, which is the
 * authority. Declaring them once does not make them shared with the backend,
 * but it does mean a change is one edit rather than a search.
 *
 * Each names its source, so the pair can be checked without guessing.
 */

/** backend/app/models/application.py — COVER_LETTER_MAX_LENGTH */
export const COVER_LETTER_MAX_LENGTH = 5_000

/** backend/app/schemas/notification.py — MESSAGE_MAX_LENGTH */
export const MESSAGE_MAX_LENGTH = 2_000

/** backend/app/models/job.py — TITLE_MAX_LENGTH */
export const JOB_TITLE_MAX_LENGTH = 200

/** backend/app/models/job.py — COMPANY_MAX_LENGTH */
export const COMPANY_MAX_LENGTH = 120

/** backend/app/models/job.py — LOCATION_MAX_LENGTH */
export const LOCATION_MAX_LENGTH = 120

/** backend/app/schemas/job.py — DESCRIPTION_MAX_LENGTH */
export const JOB_DESCRIPTION_MAX_LENGTH = 20_000

/** backend/app/models/user.py — FULL_NAME_MAX_LENGTH */
export const FULL_NAME_MAX_LENGTH = 120

/** backend/app/models/profile.py — HEADLINE_MAX_LENGTH */
export const HEADLINE_MAX_LENGTH = 200

/** backend/app/models/profile.py — SKILLS_MAX_LENGTH */
export const SKILLS_MAX_LENGTH = 1_000

/** backend/app/models/profile.py — TEXT_MAX_LENGTH */
export const PROFILE_TEXT_MAX_LENGTH = 5_000

/** How many ranked applicants the shortlist requests. */
export const SHORTLIST_SIZE = 5
