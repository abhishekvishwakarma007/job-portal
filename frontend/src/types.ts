/**
 * Shapes returned by the API.
 *
 * Mirrors the backend's Pydantic schemas. Kept hand-written rather than
 * generated so the frontend depends on the documented contract, not on
 * whatever the server happens to serialise today.
 */

export type UserRole = 'HR' | 'CANDIDATE'

export type EmploymentType =
  | 'FULL_TIME'
  | 'PART_TIME'
  | 'CONTRACT'
  | 'INTERNSHIP'

export type ApplicationStatus =
  | 'SUBMITTED'
  | 'UNDER_REVIEW'
  | 'ACCEPTED'
  | 'REJECTED'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface Job {
  id: string
  title: string
  company: string
  description: string
  location: string
  employment_type: EmploymentType
  is_published: boolean
  created_by: User
  created_at: string
  updated_at: string
}

export interface Application {
  id: string
  job: Job
  candidate: User
  cover_letter: string
  status: ApplicationStatus
  created_at: string
  updated_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface Token {
  access_token: string
  token_type: string
}

/** Human-readable labels, kept beside the unions they describe. */
export const EMPLOYMENT_TYPE_LABELS: Record<EmploymentType, string> = {
  FULL_TIME: 'Full time',
  PART_TIME: 'Part time',
  CONTRACT: 'Contract',
  INTERNSHIP: 'Internship',
}

export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  SUBMITTED: 'Submitted',
  UNDER_REVIEW: 'Under review',
  ACCEPTED: 'Accepted',
  REJECTED: 'Rejected',
}

export interface Notification {
  id: string
  subject: string
  body: string
  is_read: boolean
  job_id: string | null
  created_at: string
}

export interface NotificationPage {
  items: Notification[]
  total: number
  unread: number
  limit: number
  offset: number
}

export interface RecommendedApplicant {
  application: Application
  /** 0-1 share of the posting's vocabulary the cover letter covers. */
  score: number
  matched_terms: string[]
}

export interface RecommendationPage {
  items: RecommendedApplicant[]
  /** Named by the API so no view presents the score as more than it is. */
  method: string
}
