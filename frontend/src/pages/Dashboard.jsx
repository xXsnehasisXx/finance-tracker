import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Grid from '@mui/material/Grid'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import AccountBalanceWalletRounded from '@mui/icons-material/AccountBalanceWalletRounded'
import ArrowForwardRounded from '@mui/icons-material/ArrowForwardRounded'
import PieChartRounded from '@mui/icons-material/PieChartRounded'
import PercentRounded from '@mui/icons-material/PercentRounded'
import ReceiptLongRounded from '@mui/icons-material/ReceiptLongRounded'
import SavingsRounded from '@mui/icons-material/SavingsRounded'
import SwapVertRounded from '@mui/icons-material/SwapVertRounded'
import TrendingDownRounded from '@mui/icons-material/TrendingDownRounded'
import TrendingUpRounded from '@mui/icons-material/TrendingUpRounded'
import { api } from '../services/api.js'
import { useAsync } from '../hooks/useAsync.js'
import { CategoryDot, EmptyState, ErrorState, PageHeader, PeriodPicker, SectionCard, Spinner, StatCard } from '../components/ui.jsx'
import { CategoryPieChart, IncomeExpenseBarChart } from '../components/charts/index.jsx'
import BudgetBar from '../components/BudgetBar.jsx'
import TransactionTable from '../components/TransactionTable.jsx'
import { MONTHS, formatINR, formatPercent, titleCase } from '../utils/format.js'

const twoUp = { display: 'grid', gap: 3, gridTemplateColumns: { xs: 'minmax(0, 1fr)', lg: 'repeat(2, minmax(0, 1fr))' }, mb: 3 }

export default function Dashboard() {
  const now = new Date()
  const [period, setPeriod] = useState({ month: now.getMonth() + 1, year: now.getFullYear() })
  const dash = useAsync(() => api.dashboard(period), [period.month, period.year])
  const trend = useAsync(() => api.incomeVsExpense({ months: 6 }), [])
  const cats = useAsync(() => api.spendingByCategory(period), [period.month, period.year])
  const accounts = useAsync(() => api.accounts(), [])

  const header = (
    <PageHeader title="Dashboard" subtitle="Your financial overview"
      actions={<PeriodPicker month={period.month} year={period.year} months={MONTHS} onChange={(month, year) => setPeriod({ month, year })} />} />
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
        <Alert severity="warning" sx={{ mb: 3 }}
          action={<Button color="inherit" size="small" sx={{ whiteSpace: 'nowrap' }} component={RouterLink} to="/budgets" endIcon={<ArrowForwardRounded />}>Review budgets</Button>}>
          {d.budget_alerts_count} budget alert{d.budget_alerts_count > 1 ? 's' : ''} this period.
        </Alert>
      )}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, lg: 6 }}>
          <StatCard label="Net balance" icon={<AccountBalanceWalletRounded />} value={formatINR(d.total_balance)} sub={`Assets ${formatINR(d.total_assets)} · Credit owed ${formatINR(d.total_liabilities)}`} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard label="Income" icon={<TrendingUpRounded />} value={formatINR(d.monthly_income)} tone="good" sub={`${MONTHS[d.month - 1]} ${d.year}`} />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <StatCard label="Expenses" icon={<TrendingDownRounded />} value={formatINR(d.monthly_expenses)} tone="bad" sub="Excludes transfers" />
        </Grid>
        <Grid size={{ xs: 12, sm: 6, lg: 6 }}>
          <StatCard label="Net cash flow" icon={<SwapVertRounded />} value={formatINR(d.net_cash_flow)} tone={d.net_cash_flow < 0 ? 'bad' : 'good'} />
        </Grid>
        <Grid size={{ xs: 12, sm: 12, lg: 6 }}>
          <StatCard label="Savings rate" icon={<PercentRounded />} value={formatPercent(d.savings_rate)} tone={rateTone} sub="(income − expenses) ÷ income" />
        </Grid>
      </Grid>

      <Box sx={twoUp}>
        <SectionCard title="Income vs expenses (6 months)">
          {trend.loading ? <Spinner /> : trend.error ? <ErrorState error={trend.error} onRetry={trend.reload} /> : <IncomeExpenseBarChart data={trend.data} />}
        </SectionCard>
        <SectionCard title="Spending by category">
          {cats.loading ? <Spinner /> : cats.error ? <ErrorState error={cats.error} onRetry={cats.reload} />
            : cats.data.length === 0 ? <EmptyState icon={<PieChartRounded />} title="No spending this month">Add an expense to see your breakdown.</EmptyState>
            : <CategoryPieChart data={cats.data} />}
        </SectionCard>
      </Box>

      <Box sx={twoUp}>
        <SectionCard title="Budget utilization" actions={<Button size="small" component={RouterLink} to="/budgets" endIcon={<ArrowForwardRounded />}>Manage</Button>}>
          {d.budget_utilization.length === 0
            ? <EmptyState icon={<SavingsRounded />} title="No budgets for this month" action={<Button component={RouterLink} to="/budgets">Set a monthly budget</Button>} />
            : d.budget_utilization.map((b) => <BudgetBar key={b.category} category={b.category} limit={b.monthly_limit} spent={b.spent} percent={b.utilization_percent} hasAlert={b.has_alert} />)}
        </SectionCard>
        <SectionCard title="Top spending categories">
          {d.top_3_categories.length === 0 ? <EmptyState icon={<TrendingDownRounded />} title="Nothing yet" /> : (
            <Stack component="ol" spacing={1.5} sx={{ listStyle: 'none', m: 0, p: 0 }}>
              {d.top_3_categories.map((c, i) => (
                <Stack component="li" key={c.category} direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                  <Typography variant="caption" color="text.secondary" sx={{ width: 18 }}>{i + 1}</Typography>
                  <CategoryDot category={c.category} />
                  <Typography>{titleCase(c.category)}</Typography>
                  <Typography sx={{ ml: 'auto', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{formatINR(c.amount)}</Typography>
                </Stack>
              ))}
            </Stack>
          )}
        </SectionCard>
      </Box>

      <SectionCard title="Recent transactions" actions={<Button size="small" component={RouterLink} to="/transactions" endIcon={<ArrowForwardRounded />}>View all</Button>}>
        {d.recent_transactions.length === 0
          ? <EmptyState icon={<ReceiptLongRounded />} title="No transactions yet" action={<Button component={RouterLink} to="/transactions">Add your first transaction</Button>} />
          : <TransactionTable items={d.recent_transactions} accountNames={names} />}
      </SectionCard>
    </>
  )
}
