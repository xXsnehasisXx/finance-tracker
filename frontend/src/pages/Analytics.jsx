import { useState } from 'react'
import { api } from '../services/api.js'
import { useAsync } from '../hooks/useAsync.js'
import { Card, EmptyState, ErrorState, PeriodPicker, Spinner } from '../components/ui.jsx'
import { CategoryPieChart, IncomeExpenseBarChart } from '../components/charts/index.jsx'
import { CATEGORY_COLORS, MONTHS, formatINR, titleCase } from '../utils/format.js'

export default function Analytics() {
  const now = new Date()
  const [period, setPeriod] = useState({ month: now.getMonth() + 1, year: now.getFullYear() })
  const [months, setMonths] = useState(12)
  const cats = useAsync(() => api.spendingByCategory(period), [period.month, period.year])
  const trend = useAsync(() => api.incomeVsExpense({ months }), [months])
  const total = (cats.data || []).reduce((s, c) => s + c.amount, 0)

  return (
    <>
      <div className="page-head"><h1>Analytics</h1></div>
      <Card title="Income vs expenses" actions={<select value={months} onChange={(e) => setMonths(Number(e.target.value))} aria-label="Range"><option value={6}>Last 6 months</option><option value={12}>Last 12 months</option><option value={24}>Last 24 months</option></select>}>
        {trend.loading && !trend.data ? <Spinner /> : trend.error ? <ErrorState error={trend.error} onRetry={trend.reload} /> : <IncomeExpenseBarChart data={trend.data} />}
      </Card>
      <Card title="Spending by category" actions={<PeriodPicker month={period.month} year={period.year} months={MONTHS} onChange={(month, year) => setPeriod({ month, year })} />}>
        {cats.loading && !cats.data ? <Spinner /> : cats.error ? <ErrorState error={cats.error} onRetry={cats.reload} />
          : cats.data.length === 0 ? <EmptyState icon="🥧" title="No spending in this month" />
          : <div className="grid-2">
              <CategoryPieChart data={cats.data} />
              <ul className="rank">{cats.data.map((c) => (
                <li key={c.category}><span className="dot" style={{ background: CATEGORY_COLORS[c.category] }} />{titleCase(c.category)}
                  <span className="muted small">{total ? ((c.amount / total) * 100).toFixed(1) : 0}%</span><strong>{formatINR(c.amount)}</strong></li>))}
              </ul>
            </div>}
      </Card>
    </>
  )
}
