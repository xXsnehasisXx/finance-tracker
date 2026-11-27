import { useState } from 'react'
import Alert from '@mui/material/Alert'
import AlertTitle from '@mui/material/AlertTitle'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Stack from '@mui/material/Stack'
import AddRounded from '@mui/icons-material/AddRounded'
import CheckCircleRounded from '@mui/icons-material/CheckCircleRounded'
import SavingsRounded from '@mui/icons-material/SavingsRounded'
import { api } from '../services/api.js'
import { useAsync } from '../hooks/useAsync.js'
import { useToast } from '../contexts/ToastContext.jsx'
import { ConfirmDialog, EmptyState, ErrorState, Modal, PageHeader, PeriodPicker, SectionCard, Spinner } from '../components/ui.jsx'
import { BudgetForm } from '../components/forms.jsx'
import BudgetBar from '../components/BudgetBar.jsx'
import { MONTHS, formatDate, titleCase } from '../utils/format.js'

export default function Budgets() {
  const toast = useToast()
  const now = new Date()
  const [period, setPeriod] = useState({ month: now.getMonth() + 1, year: now.getFullYear() })
  const [adding, setAdding] = useState(false)
  const [toDelete, setToDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const budgets = useAsync(() => api.budgets(period), [period.month, period.year])
  const alerts = useAsync(() => api.budgetAlerts(period), [period.month, period.year])

  const remove = async () => {
    setDeleting(true)
    try { await api.deleteBudget(toDelete.id); toast.success('Budget deleted'); budgets.reload(); alerts.reload() } catch (e) { toast.error(e.message) }
    setDeleting(false)
    setToDelete(null)
  }

  return (
    <>
      <PageHeader title="Budgets" subtitle="Monthly spending limits with alerts at 80% and 100%"
        actions={<>
          <PeriodPicker month={period.month} year={period.year} months={MONTHS} onChange={(month, year) => setPeriod({ month, year })} />
          <Button variant="contained" startIcon={<AddRounded />} onClick={() => setAdding(true)}>Set budget</Button>
        </>} />
      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: 'minmax(0, 1fr)', lg: 'repeat(2, minmax(0, 1fr))' }, alignItems: 'start' }}>
        <SectionCard title={`${MONTHS[period.month - 1]} ${period.year}`}>
          {budgets.loading && !budgets.data ? <Spinner /> : budgets.error ? <ErrorState error={budgets.error} onRetry={budgets.reload} />
            : budgets.data.length === 0 ? <EmptyState icon={<SavingsRounded />} title="No budgets for this month" action={<Button variant="contained" onClick={() => setAdding(true)}>Set a budget</Button>}>Budgets limit your spending per category and alert you at 80% and 100%.</EmptyState>
            : budgets.data.map((b) => <BudgetBar key={b.id} category={b.category} limit={b.monthly_limit} spent={b.spent} remaining={b.remaining} percent={b.utilization_percent} hasAlert={b.has_alert} onDelete={() => setToDelete(b)} />)}
        </SectionCard>
        <SectionCard title="Alerts">
          {alerts.loading && !alerts.data ? <Spinner /> : alerts.error ? <ErrorState error={alerts.error} onRetry={alerts.reload} />
            : alerts.data.length === 0 ? <EmptyState icon={<CheckCircleRounded />} title="No alerts">You're within budget.</EmptyState>
            : (
              <Stack spacing={1.5} component="ul" sx={{ listStyle: 'none', m: 0, p: 0 }}>
                {alerts.data.map((a) => (
                  <li key={a.id}>
                    <Alert severity={a.alert_type === 'exceeded' ? 'error' : 'warning'} sx={{ alignItems: 'flex-start' }}>
                      <AlertTitle sx={{ mb: 0 }}>{titleCase(a.category)}</AlertTitle>
                      {a.alert_type === 'exceeded' ? 'Budget exceeded (100%)' : '80% of budget reached'}
                      <Box component="span" sx={{ display: 'block', fontSize: '0.75rem', opacity: 0.8 }}>{formatDate(a.triggered_at)}</Box>
                    </Alert>
                  </li>
                ))}
              </Stack>
            )}
        </SectionCard>
      </Box>
      {adding && (
        <Modal title="Set monthly budget" onClose={() => setAdding(false)}>
          <BudgetForm defaultMonth={period.month} defaultYear={period.year} onCancel={() => setAdding(false)}
            onSubmit={async (body) => { await api.createBudget(body); setAdding(false); toast.success('Budget saved'); budgets.reload(); alerts.reload() }} />
        </Modal>
      )}
      <ConfirmDialog open={Boolean(toDelete)} title="Delete budget?" busy={deleting} onCancel={() => setToDelete(null)} onConfirm={remove}
        message={toDelete && `Delete the ${titleCase(toDelete.category)} budget for ${MONTHS[toDelete.month - 1]} ${toDelete.year}? Its alerts are removed too.`} />
    </>
  )
}
