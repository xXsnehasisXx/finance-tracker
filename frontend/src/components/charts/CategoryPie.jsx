import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { useTheme } from '@mui/material/styles'
import Box from '@mui/material/Box'
import { CATEGORY_COLORS } from '../../theme/themeConstants.js'
import { formatINR, titleCase } from '../../utils/format.js'
import { chartTooltipStyles } from './chartStyles.js'

export default function CategoryPie({ data }) {
  const theme = useTheme()
  const rows = data.map((d) => ({ name: titleCase(d.category), key: d.category, value: Number(d.amount) }))
  return (
    <Box sx={{ height: { xs: 260, sm: 300 }, width: '100%' }} role="img" aria-label="Spending by category chart">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={rows} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="85%" paddingAngle={2} stroke={theme.palette.background.paper} strokeWidth={2}>
            {rows.map((r) => <Cell key={r.key} fill={CATEGORY_COLORS[r.key] || CATEGORY_COLORS.other} />)}
          </Pie>
          <Tooltip formatter={(v) => formatINR(v)} {...chartTooltipStyles(theme)} />
          <Legend wrapperStyle={{ color: theme.palette.text.secondary, fontSize: 13 }} />
        </PieChart>
      </ResponsiveContainer>
    </Box>
  )
}
