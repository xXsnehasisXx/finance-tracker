import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { MONTHS, formatINR } from '../../utils/format.js'

export default function IncomeExpenseChart({ data }) {
  const rows = data.map((d) => ({ name: `${MONTHS[d.month_number - 1].slice(0, 3)} ${String(d.year).slice(2)}`, Income: Number(d.income), Expenses: Number(d.expenses) }))
  return (
    <div className="chart" style={{ height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" />
          <YAxis tickFormatter={(v) => (v >= 1000 ? `${v / 1000}k` : v)} width={48} />
          <Tooltip formatter={(v) => formatINR(v)} />
          <Legend />
          <Bar dataKey="Income" fill="#16a34a" radius={[4, 4, 0, 0]} />
          <Bar dataKey="Expenses" fill="#dc2626" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
