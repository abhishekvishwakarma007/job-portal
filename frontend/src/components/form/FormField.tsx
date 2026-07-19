import type { ReactNode } from 'react'

export interface FieldProps {
  id: string
  label: string
  value: string
  error?: string | undefined
  hint?: string | undefined
  placeholder?: string | undefined
  maxLength?: number | undefined
  type?: string | undefined
  autoComplete?: string | undefined
  required?: boolean | undefined
  multiline?: boolean | undefined
  options?: { value: string; label: string }[] | undefined
  onChange: (value: string) => void
}

const CONTROL =
  'mt-1 w-full rounded-lg border border-[color:var(--border)] px-3 py-2 text-sm'

/**
 * A labelled control with its inline validation message.
 *
 * Every form in the app renders fields the same way, so doing it once here is
 * what stops a new form quietly omitting the label association or the
 * aria-invalid that assistive technology needs — both of which have already
 * been missed once in this codebase.
 */
export default function FormField({
  id,
  label,
  value,
  error,
  hint,
  placeholder,
  maxLength,
  type = 'text',
  autoComplete,
  required,
  multiline,
  options,
  onChange,
}: FieldProps) {
  const describedBy = hint ? `${id}-hint` : undefined
  const shared = {
    id,
    value,
    maxLength,
    required,
    className: multiline ? `${CONTROL} min-h-28` : CONTROL,
    'aria-invalid': Boolean(error),
    'aria-describedby': describedBy,
    onChange: (
      event: React.ChangeEvent<
        HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
      >,
    ) => onChange(event.target.value),
  }

  return (
    <div className="mb-4">
      <label
        className="block text-sm font-semibold text-slate-900"
        htmlFor={id}
      >
        {label}
      </label>

      {options ? (
        <select {...shared}>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : multiline ? (
        <textarea {...shared} placeholder={placeholder} />
      ) : (
        <input {...shared} type={type} autoComplete={autoComplete} placeholder={placeholder} />
      )}

      {hint && (
        <span
          id={describedBy}
          className="mt-1 block text-xs text-[color:var(--text-muted)]"
        >
          {hint}
        </span>
      )}
      {error && (
        <span className="mt-1 block text-sm text-[color:var(--danger)]">
          {error}
        </span>
      )}
    </div>
  )
}

/** A form's error banner, or nothing when there is no error. */
export function FormAlert({ message }: { message: string | null }): ReactNode {
  if (!message) return null

  return (
    <p
      role="alert"
      className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      {message}
    </p>
  )
}
