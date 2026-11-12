import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { CATEGORY_COLORS, formatINR, titleCase } from '../../utils/format.js'

export default function CategoryPie({ data }) {
  const rows = data.map((d) => ({ name: titleCase(d.category), key: d.category, value: Number(d.amount) }))
  return (
    <div className="chart" style={{ height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={rows} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={2}>
            {rows.map((r) => <Cell key={r.key} fill={CATEGORY_COLORS[r.key] || '#64748b'} />)}
          </Pie>
          <Tooltip formatter={(v) => formatINR(v)} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
