import { useState } from 'react'
import { api } from '../services/api.js'
import { useAsync } from '../hooks/useAsync.js'
import { useToast } from '../contexts/ToastContext.jsx'
import { Card, EmptyState, ErrorState, Modal, PeriodPicker, Spinner } from '../components/ui.jsx'
import { BudgetForm } from '../components/forms.jsx'
import BudgetBar from '../components/BudgetBar.jsx'
import { MONTHS, formatDate, titleCase } from '../utils/format.js'

export default function Budgets() {
  const toast = useToast()
  const now = new Date()
  const [period, setPeriod] = useState({ month: now.getMonth() + 1, year: now.getFullYear() })
  const [adding, setAdding] = useState(false)
  const budgets = useAsync(() => api.budgets(period), [period.month, period.year])
  const alerts = useAsync(() => api.budgetAlerts(period), [period.month, period.year])

  const remove = async (b) => {
    if (!window.confirm(`Delete the ${titleCase(b.category)} budget for ${MONTHS[b.month - 1]} ${b.year}? Its alerts are removed too.`)) return
    try { await api.deleteBudget(b.id); toast.success('Budget deleted'); budgets.reload(); alerts.reload() } catch (e) { toast.error(e.message) }
  }

  return (
    <>
      <div className="page-head">
        <h1>Budgets</h1>
        <div className="btn-row">
          <PeriodPicker month={period.month} year={period.year} months={MONTHS} onChange={(month, year) => setPeriod({ month, year })} />
          <button className="btn btn-primary" onClick={() => setAdding(true)}>+ Set budget</button>
        </div>
      </div>
      <div className="grid-2">
        <Card title={`${MONTHS[period.month - 1]} ${period.year}`}>
          {budgets.loading && !budgets.data ? <Spinner /> : budgets.error ? <ErrorState error={budgets.error} onRetry={budgets.reload} />
            : budgets.data.length === 0 ? <EmptyState icon="🎯" title="No budgets for this month" action={<button className="btn btn-primary" onClick={() => setAdding(true)}>Set a budget</button>}>Budgets limit your spending per category and alert you at 80% and 100%.</EmptyState>
            : budgets.data.map((b) => <BudgetBar key={b.id} category={b.category} limit={b.monthly_limit} spent={b.spent} remaining={b.remaining} percent={b.utilization_percent} hasAlert={b.has_alert} onDelete={() => remove(b)} />)}
        </Card>
        <Card title="Alerts">
          {alerts.loading && !alerts.data ? <Spinner /> : alerts.error ? <ErrorState error={alerts.error} onRetry={alerts.reload} />
            : alerts.data.length === 0 ? <EmptyState icon="✅" title="No alerts">You're within budget.</EmptyState>
            : <ul className="alerts">{alerts.data.map((a) => (
              <li key={a.id} className={a.alert_type === 'exceeded' ? 'alert-red' : 'alert-orange'}>
                <span>{a.alert_type === 'exceeded' ? '🚨' : '⚠️'}</span>
                <div><strong>{titleCase(a.category)}</strong> — {a.alert_type === 'exceeded' ? 'budget exceeded (100%)' : '80% of budget reached'}<div className="muted small">{formatDate(a.triggered_at)}</div></div>
              </li>))}</ul>}
        </Card>
      </div>
      {adding && (
        <Modal title="Set monthly budget" onClose={() => setAdding(false)}>
          <BudgetForm defaultMonth={period.month} defaultYear={period.year} onCancel={() => setAdding(false)}
            onSubmit={async (body) => { await api.createBudget(body); setAdding(false); toast.success('Budget saved'); budgets.reload(); alerts.reload() }} />
        </Modal>
      )}
    </>
  )
}
