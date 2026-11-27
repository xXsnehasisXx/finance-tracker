import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useTheme } from '@mui/material/styles'
import Box from '@mui/material/Box'
import { MONTHS, formatINR } from '../../utils/format.js'
import { chartTooltipStyles } from './chartStyles.js'

export default function IncomeExpenseChart({ data }) {
  const theme = useTheme()
  const tick = { fill: theme.palette.text.secondary, fontSize: 12 }
  const rows = data.map((d) => ({ name: `${MONTHS[d.month_number - 1].slice(0, 3)} ${String(d.year).slice(2)}`, Income: Number(d.income), Expenses: Number(d.expenses) }))
  return (
    <Box sx={{ height: { xs: 260, sm: 300 }, width: '100%' }} role="img" aria-label="Income versus expenses chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={theme.palette.divider} />
          <XAxis dataKey="name" tick={tick} axisLine={{ stroke: theme.palette.divider }} tickLine={false} />
          <YAxis tickFormatter={(v) => (v >= 1000 ? `${v / 1000}k` : v)} width={48} tick={tick} axisLine={false} tickLine={false} />
          <Tooltip formatter={(v) => formatINR(v)} {...chartTooltipStyles(theme)} />
          <Legend wrapperStyle={{ color: theme.palette.text.secondary, fontSize: 13 }} />
          <Bar dataKey="Income" fill={theme.palette.success.main} radius={[4, 4, 0, 0]} />
          <Bar dataKey="Expenses" fill={theme.palette.error.main} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </Box>
  )
}
