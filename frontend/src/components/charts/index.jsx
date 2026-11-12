import { Suspense, lazy } from 'react'
import { Spinner } from '../ui.jsx'

const Pie = lazy(() => import('./CategoryPie.jsx'))
const Bars = lazy(() => import('./IncomeExpenseChart.jsx'))

export const CategoryPieChart = (props) => <Suspense fallback={<Spinner label="Loading chart…" />}><Pie {...props} /></Suspense>
export const IncomeExpenseBarChart = (props) => <Suspense fallback={<Spinner label="Loading chart…" />}><Bars {...props} /></Suspense>
