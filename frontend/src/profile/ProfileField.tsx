import type { Draft, FieldSpec } from './sections'

const INPUT_CLASS =
  'mt-1 w-full rounded-lg border border-[color:var(--border)] px-3 py-2 text-sm'
const LABEL_CLASS =
  'block text-xs font-semibold uppercase tracking-wide text-[color:var(--text-muted)]'

interface ProfileFieldProps {
  spec: FieldSpec
  value: string
  onChange: (field: keyof Draft, value: string) => void
}

/**
 * One profile field, rendered from its description.
 *
 * `labelHidden` renders the label sr-only rather than omitting it. The section
 * heading conveys these fields visually, but a heading is not a label — a
 * screen reader would otherwise announce an unlabelled input, which is what it
 * did before these were described as data.
 */
export default function ProfileField({
  spec,
  value,
  onChange,
}: ProfileFieldProps) {
  const { name, label, multiline, options, placeholder, maxLength } = spec
  const shared = {
    id: name,
    value,
    maxLength,
    className: multiline ? `${INPUT_CLASS} min-h-24` : INPUT_CLASS,
  }

  return (
    <div className={spec.wide ? 'sm:col-span-2' : undefined}>
      <label
        className={spec.labelHidden ? 'sr-only' : LABEL_CLASS}
        htmlFor={name}
      >
        {label}
      </label>

      {options ? (
        <select
          {...shared}
          onChange={(event) => onChange(name, event.target.value)}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : multiline ? (
        <textarea
          {...shared}
          placeholder={placeholder}
          onChange={(event) => onChange(name, event.target.value)}
        />
      ) : (
        <input
          {...shared}
          placeholder={placeholder}
          onChange={(event) => onChange(name, event.target.value)}
        />
      )}
    </div>
  )
}
