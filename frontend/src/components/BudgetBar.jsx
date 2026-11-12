import { ProgressBar } from './ui.jsx'
import { formatINR, formatPercent, titleCase, utilizationTone } from '../utils/format.js'

// green < 80%, orange 80-99%, red >= 100% (with alert icon when exceeded)
export default function BudgetBar({ category, limit, spent, percent, hasAlert, onDelete, remaining }) {
  const tone = utilizationTone(percent)
  return (
    <div className={`budget budget-${tone}`}>
      <div className="budget-head">
        <strong><span className={`dot dot-${category}`} />{titleCase(category)}</strong>
        <span className="budget-pct">
          {hasAlert && <span className="alert-icon" title={tone === 'danger' ? 'Budget exceeded' : 'Warning: 80% reached'} aria-label="Budget alert">{tone === 'danger' ? '🚨' : '⚠️'}</span>}
          {formatPercent(percent)}
        </span>
      </div>
      <ProgressBar percent={percent} tone={tone} />
      <div className="budget-foot">
        <span>{formatINR(spent)} of {formatINR(limit)}</span>
        {remaining !== undefined && <span className={remaining < 0 ? 'neg' : 'muted'}>{remaining < 0 ? `${formatINR(-remaining)} over` : `${formatINR(remaining)} left`}</span>}
        {onDelete && <button className="link-btn" onClick={onDelete}>Delete</button>}
      </div>
    </div>
  )
}
