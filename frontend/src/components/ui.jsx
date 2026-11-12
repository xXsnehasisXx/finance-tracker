import { useEffect } from 'react'

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="spinner-wrap" role="status">
      <div className="spinner" />
      <span>{label}</span>
    </div>
  )
}

export function EmptyState({ icon = '📭', title, children, action }) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  )
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="error-state" role="alert">
      <strong>Something went wrong</strong>
      <p>{error?.message || 'Unexpected error'}</p>
      {onRetry && <button className="btn" onClick={onRetry}>Try again</button>}
    </div>
  )
}

export function Card({ title, actions, children, className = '' }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-header">
          <h2>{title}</h2>
          <div className="card-actions">{actions}</div>
        </header>
      )}
      {children}
    </section>
  )
}

export function StatCard({ label, value, sub, tone }) {
  return (
    <div className={`stat ${tone ? `stat-${tone}` : ''}`}>
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  )
}

export function Modal({ title, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <header className="modal-header">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">×</button>
        </header>
        {children}
      </div>
    </div>
  )
}

export function Field({ label, error, children, hint }) {
  return (
    <label className={`field ${error ? 'field-error' : ''}`}>
      <span className="field-label">{label}</span>
      {children}
      {hint && !error && <span className="field-hint">{hint}</span>}
      {error && <span className="field-msg">{error}</span>}
    </label>
  )
}

export function ProgressBar({ percent, tone }) {
  return (
    <div className="progress" role="progressbar" aria-valuenow={Math.round(percent)} aria-valuemin={0} aria-valuemax={100}>
      <div className={`progress-fill progress-${tone}`} style={{ width: `${Math.min(100, Math.max(0, percent))}%` }} />
    </div>
  )
}

export function Pagination({ page, pages, onChange }) {
  if (pages <= 1) return null
  return (
    <div className="pagination">
      <button className="btn btn-ghost" disabled={page <= 1} onClick={() => onChange(page - 1)}>← Prev</button>
      <span>Page {page} of {pages}</span>
      <button className="btn btn-ghost" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next →</button>
    </div>
  )
}

export function PeriodPicker({ month, year, onChange, months }) {
  const thisYear = new Date().getFullYear()
  const years = Array.from({ length: 7 }, (_, i) => thisYear - 3 + i)
  return (
    <div className="period">
      <select value={month} onChange={(e) => onChange(Number(e.target.value), year)} aria-label="Month">
        {months.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
      </select>
      <select value={year} onChange={(e) => onChange(month, Number(e.target.value))} aria-label="Year">
        {years.map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
    </div>
  )
}
