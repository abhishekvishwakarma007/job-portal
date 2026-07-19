import { Link } from 'react-router-dom'

/** Catch-all for unrecognised routes. */
export default function NotFoundPage() {
  return (
    <div className="card empty">
      <h1>Page not found</h1>
      <p className="muted">That page does not exist.</p>
      <Link to="/" className="button">
        Browse jobs
      </Link>
    </div>
  )
}
