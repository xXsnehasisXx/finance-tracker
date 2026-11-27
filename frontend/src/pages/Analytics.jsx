import { useState } from 'react'
import Box from '@mui/material/Box'
import MenuItem from '@mui/material/MenuItem'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import PieChartRounded from '@mui/icons-material/PieChartRounded'
import { api } from '../services/api.js'
import { useAsync } from '../hooks/useAsync.js'
import { CategoryDot, EmptyState, ErrorState, PageHeader, PeriodPicker, SectionCard, Spinner } from '../components/ui.jsx'
import { CategoryPieChart, IncomeExpenseBarChart } from '../components/charts/index.jsx'
import { MONTHS, formatINR, titleCase } from '../utils/format.js'

export default function Analytics() {
  const now = new Date()
  const [period, setPeriod] = useState({ month: now.getMonth() + 1, year: now.getFullYear() })
  const [months, setMonths] = useState(12)
  const cats = useAsync(() => api.spendingByCategory(period), [period.month, period.year])
  const trend = useAsync(() => api.incomeVsExpense({ months }), [months])
  const total = (cats.data || []).reduce((s, c) => s + c.amount, 0)

  return (
    <>
      <PageHeader title="Analytics" subtitle="Trends and spending breakdown" />
      <Stack spacing={3}>
        <SectionCard title="Income vs expenses"
          actions={
            <TextField select size="small" value={months} onChange={(e) => setMonths(Number(e.target.value))} sx={{ minWidth: 160 }} slotProps={{ select: { SelectDisplayProps: { 'aria-label': 'Range' } } }}>
              <MenuItem value={6}>Last 6 months</MenuItem>
              <MenuItem value={12}>Last 12 months</MenuItem>
              <MenuItem value={24}>Last 24 months</MenuItem>
            </TextField>
          }>
          {trend.loading && !trend.data ? <Spinner /> : trend.error ? <ErrorState error={trend.error} onRetry={trend.reload} /> : <IncomeExpenseBarChart data={trend.data} />}
        </SectionCard>
        <SectionCard title="Spending by category" actions={<PeriodPicker month={period.month} year={period.year} months={MONTHS} onChange={(month, year) => setPeriod({ month, year })} />}>
          {cats.loading && !cats.data ? <Spinner /> : cats.error ? <ErrorState error={cats.error} onRetry={cats.reload} />
            : cats.data.length === 0 ? <EmptyState icon={<PieChartRounded />} title="No spending in this month" />
            : (
              <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'repeat(2, minmax(0, 1fr))' }, alignItems: 'center' }}>
                <CategoryPieChart data={cats.data} />
                <Stack component="ul" spacing={1.5} sx={{ listStyle: 'none', m: 0, p: 0 }}>
                  {cats.data.map((c) => (
                    <Stack component="li" key={c.category} direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
                      <CategoryDot category={c.category} />
                      <Typography>{titleCase(c.category)}</Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ ml: 'auto !important' }}>{total ? ((c.amount / total) * 100).toFixed(1) : 0}%</Typography>
                      <Typography sx={{ fontWeight: 700, minWidth: 96, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{formatINR(c.amount)}</Typography>
                    </Stack>
                  ))}
                </Stack>
              </Box>
            )}
        </SectionCard>
      </Stack>
    </>
  )
}
