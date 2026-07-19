import {
  HEADLINE_MAX_LENGTH,
  LOCATION_MAX_LENGTH,
  PROFILE_TEXT_MAX_LENGTH,
  SKILLS_MAX_LENGTH,
} from '../constants'
import { EMPLOYMENT_TYPE_LABELS, type CandidateProfile } from '../types'

export type ProfileField = Exclude<
  keyof CandidateProfile,
  'id' | 'user_id' | 'created_at' | 'updated_at'
>

export type Draft = Record<ProfileField, string>

export const EMPTY_DRAFT: Draft = {
  headline: '',
  location: '',
  phone: '',
  summary: '',
  preferred_role: '',
  preferred_location: '',
  preferred_employment_type: '',
  key_skills: '',
  employment: '',
  education: '',
}

interface FieldSpec {
  name: ProfileField
  label: string
  /** Rendered as a textarea when true, a single-line input otherwise. */
  multiline?: boolean
  /** Renders a select over these options instead of a free-text field. */
  options?: { value: string; label: string }[]
  placeholder?: string
  maxLength: number
  /** Hides the label visually while keeping it for assistive technology. */
  labelHidden?: boolean
  /** Lays the field across both columns of a two-column section. */
  wide?: boolean
}

export interface SectionSpec {
  id: string
  title: string
  hint?: string
  /** Column count at the small breakpoint. */
  columns?: 2 | 3
  fields: FieldSpec[]
}

/**
 * The profile, described as data rather than as six near-identical blocks of
 * JSX.
 *
 * The sections differ only in their labels, limits, and input type, so writing
 * them out longhand produced one 287-line component where a field added to a
 * section meant copying a div. Describing them here means the page renders a
 * map and a new field is one entry.
 *
 * Every maxLength cites the backend column it mirrors via ../constants, so a
 * limit cannot drift from the schema unnoticed.
 */
export const PROFILE_SECTIONS: SectionSpec[] = [
  {
    id: 'basic',
    title: 'Basic details',
    columns: 2,
    fields: [
      {
        name: 'headline',
        label: 'Headline',
        placeholder: 'Senior Platform Engineer',
        maxLength: HEADLINE_MAX_LENGTH,
        wide: true,
      },
      {
        name: 'location',
        label: 'Current location',
        placeholder: 'Bangalore',
        maxLength: LOCATION_MAX_LENGTH,
      },
      {
        name: 'phone',
        label: 'Phone',
        placeholder: '+91 98765 43210',
        maxLength: 40,
      },
    ],
  },
  {
    id: 'summary',
    title: 'Profile summary',
    hint: 'Two or three sentences. Read when a hiring team ranks you.',
    fields: [
      {
        name: 'summary',
        label: 'Profile summary',
        labelHidden: true,
        multiline: true,
        placeholder:
          'What you do, what you are good at, and what you are looking for.',
        maxLength: PROFILE_TEXT_MAX_LENGTH,
      },
    ],
  },
  {
    id: 'skills',
    title: 'Key skills',
    hint: 'Comma separated. Weighted above prose when applicants are ranked.',
    fields: [
      {
        name: 'key_skills',
        label: 'Key skills',
        labelHidden: true,
        placeholder: 'Python, FastAPI, Postgres, Docker',
        maxLength: SKILLS_MAX_LENGTH,
      },
    ],
  },
  {
    id: 'preferences',
    title: 'Career preferences',
    columns: 3,
    fields: [
      {
        name: 'preferred_role',
        label: 'Preferred role',
        placeholder: 'Backend Engineer',
        maxLength: HEADLINE_MAX_LENGTH,
      },
      {
        name: 'preferred_location',
        label: 'Preferred location',
        placeholder: 'Remote',
        maxLength: LOCATION_MAX_LENGTH,
      },
      {
        name: 'preferred_employment_type',
        label: 'Employment type',
        maxLength: 40,
        options: [
          { value: '', label: 'No preference' },
          ...Object.entries(EMPLOYMENT_TYPE_LABELS).map(([value, label]) => ({
            value,
            label,
          })),
        ],
      },
    ],
  },
  {
    id: 'employment',
    title: 'Employment',
    hint: 'One role per line: title, company, dates.',
    fields: [
      {
        name: 'employment',
        label: 'Employment history',
        labelHidden: true,
        multiline: true,
        placeholder:
          'Platform Engineer, Northwind Labs, 2022-present\nBackend Developer, Acme, 2019-2022',
        maxLength: PROFILE_TEXT_MAX_LENGTH,
      },
    ],
  },
  {
    id: 'education',
    title: 'Education',
    hint: 'One qualification per line.',
    fields: [
      {
        name: 'education',
        label: 'Education',
        labelHidden: true,
        multiline: true,
        placeholder: 'B.Tech Computer Science, IIT Delhi, 2019',
        maxLength: PROFILE_TEXT_MAX_LENGTH,
      },
    ],
  },
]

export type { FieldSpec }
