import { APPLICATION_STATUS_LABELS, type ApplicationStatus } from '../types'

/** Colour per pipeline state, so a list is scannable without reading it. */
const VARIANTS: Record<ApplicationStatus, string> = {
  SUBMITTED: 'badge--neutral',
  UNDER_REVIEW: 'badge--info',
  ACCEPTED: 'badge--success',
  REJECTED: 'badge--danger',
}

export default function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <span className={`badge ${VARIANTS[status]}`}>
      {APPLICATION_STATUS_LABELS[status]}
    </span>
  )
}
