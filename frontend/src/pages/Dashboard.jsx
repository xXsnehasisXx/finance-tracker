import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api.js'
import { useAsync } from '../hooks/useAsync.js'
import { Card, EmptyState, ErrorState, PeriodPicker, Spinner, StatCard } from '../components/ui.jsx'
import { CategoryPieChart, IncomeExpenseBarChart } from '../components/charts/index.jsx'
import BudgetBar from '../components/BudgetBar.jsx'
import TransactionTable from '../components/TransactionTable.jsx'
import { MONTHS, formatINR, formatPercent } from '../utils/format.js'

export default function Dashboard() {
  const now = new Date()
  const [period, setPeriod] = useState({ month: now.getMonth() + 1, year: now.getFullYear() })
  const dash = useAsync(() => api.dashboard(period), [period.month, period.year])
  const trend = useAsync(() => api.incomeVsExpense({ months: 6 }), [])
  const cats = useAsync(() => api.spendingByCategory(period), [period.month, period.year])
  const accounts = useAsync(() => api.accounts(), [])

  const header = (
    <div className="page-head">
      <h1>Dashboard</h1>
      <PeriodPicker month={period.month} year={period.year} months={MONTHS} onChange={(month, year) => setPeriod({ month, year })} />
    </div>
  )
  if (dash.loading && !dash.data) return <>{header}<Spinner /></>
  if (dash.error) return <>{header}<ErrorState error={dash.error} onRetry={dash.reload} /></>
  const d = dash.data
  const names = Object.fromEntries((accounts.data || []).map((a) => [a.id, a.account_name]))
  const rateTone = d.savings_rate >= 20 ? 'good' : d.savings_rate < 0 ? 'bad' : undefined

  return (
    <>
      {header}
      {d.budget_alerts_count > 0 && (
        <div className="banner banner-warn">🔔 {d.budget_alerts_count} budget alert{d.budget_alerts_count > 1 ? 's' : ''} this period. <Link to="/budgets">Review budgets</Link></div>
      )}
      <div className="stats">
        <StatCard label="Net balance" value={formatINR(d.total_balance)} sub={`Assets ${formatINR(d.total_assets)} · Credit owed ${formatINR(d.total_liabilities)}`} />
        <StatCard label="Income" value={formatINR(d.monthly_income)} tone="good" sub={`${MONTHS[d.month - 1]} ${d.year}`} />
        <StatCard label="Expenses" value={formatINR(d.monthly_expenses)} tone="bad" sub="Excludes transfers" />
        <StatCard label="Net cash flow" value={formatINR(d.net_cash_flow)} tone={d.net_cash_flow < 0 ? 'bad' : 'good'} />
        <StatCard label="Savings rate" value={formatPercent(d.savings_rate)} tone={rateTone} sub="(income − expenses) ÷ income" />
      </div>

      <div className="grid-2">
        <Card title="Income vs expenses (6 months)">
          {trend.loading ? <Spinner /> : trend.error ? <ErrorState error={trend.error} onRetry={trend.reload} /> : <IncomeExpenseBarChart data={trend.data} />}
        </Card>
        <Card title="Spending by category">
          {cats.loading ? <Spinner /> : cats.error ? <ErrorState error={cats.error} onRetry={cats.reload} />
            : cats.data.length === 0 ? <EmptyState icon="🥧" title="No spending this month">Add an expense to see your breakdown.</EmptyState>
            : <CategoryPieChart data={cats.data} />}
        </Card>
      </div>

      <div className="grid-2">
        <Card title="Budget utilization" actions={<Link to="/budgets" className="link-btn">Manage</Link>}>
          {d.budget_utilization.length === 0
            ? <EmptyState icon="🎯" title="No budgets for this month"><Link to="/budgets">Set a monthly budget</Link></EmptyState>
            : d.budget_utilization.map((b) => <BudgetBar key={b.category} category={b.category} limit={b.monthly_limit} spent={b.spent} percent={b.utilization_percent} hasAlert={b.has_alert} />)}
        </Card>
        <Card title="Top spending categories">
          {d.top_3_categories.length === 0 ? <EmptyState icon="📉" title="Nothing yet" /> : (
            <ol className="rank">{d.top_3_categories.map((c) => <li key={c.category}><span className={`dot dot-${c.category}`} />{c.category}<strong>{formatINR(c.amount)}</strong></li>)}</ol>
          )}
        </Card>
      </div>

      <Card title="Recent transactions" actions={<Link to="/transactions" className="link-btn">View all</Link>}>
        {d.recent_transactions.length === 0
          ? <EmptyState title="No transactions yet"><Link to="/transactions">Add your first transaction</Link></EmptyState>
          : <TransactionTable items={d.recent_transactions} accountNames={names} />}
      </Card>
    </>
  )
}
