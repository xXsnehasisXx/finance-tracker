# Charts and Analytics

Part of the [Finance Tracker documentation library](../Finance%20Tracker.md). Sources: [`components/charts/`](../../frontend/src/components/charts), [`pages/Dashboard.jsx`](../../frontend/src/pages/Dashboard.jsx), [`pages/Analytics.jsx`](../../frontend/src/pages/Analytics.jsx), [`utils/format.js`](../../frontend/src/utils/format.js). Library: **Recharts 2.15** (the only charting library; no other is used).

## 1. Chart components

### `IncomeExpenseChart` (grouped bar chart)
Input `data` = the array returned by `GET /analytics/income-vs-expense` (`[{month, year, month_number, income, expenses}]`).

```jsx
const rows = data.map((d) => ({ name: `${MONTHS[d.month_number - 1].slice(0, 3)} ${String(d.year).slice(2)}`,
                                Income: Number(d.income), Expenses: Number(d.expenses) }))
<ResponsiveContainer width="100%" height="100%">
  <BarChart data={rows}> <CartesianGrid strokeDasharray="3 3" vertical={false}/> <XAxis dataKey="name"/>
    <YAxis tickFormatter={(v) => (v >= 1000 ? `${v/1000}k` : v)} width={48}/>
    <Tooltip formatter={(v) => formatINR(v)}/> <Legend/>
    <Bar dataKey="Income" fill="#16a34a" radius={[4,4,0,0]}/> <Bar dataKey="Expenses" fill="#dc2626" radius={[4,4,0,0]}/>
```

* X label e.g. `Jun 26`; green income bars vs red expense bars; tooltip shows `₹` formatted via `Intl.NumberFormat('en-IN')`; Y axis abbreviates thousands.

### `CategoryPie` (donut)
Input `data` = `GET /analytics/spending-by-category` (`[{category, amount}]`).

```jsx
const rows = data.map((d) => ({ name: titleCase(d.category), key: d.category, value: Number(d.amount) }))
<Pie data={rows} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={2}>
  {rows.map((r) => <Cell key={r.key} fill={CATEGORY_COLORS[r.key] || '#64748b'} />)}
```

`CATEGORY_COLORS` (food `#f97316`, transport `#3b82f6`, utilities `#8b5cf6`, entertainment `#ec4899`, health `#10b981`, salary `#14b8a6`, other `#64748b`) is shared with the CSS `.dot-<category>` classes so a category has the same colour in charts, tables and lists.

Both charts are wrapped in `<ResponsiveContainer>` inside a `.chart` div with fixed height 280 px, so they resize with the card (desktop → mobile).

## 2. Lazy loading

`components/charts/index.jsx`:

```jsx
const Pie  = lazy(() => import('./CategoryPie.jsx'))
const Bars = lazy(() => import('./IncomeExpenseChart.jsx'))
export const CategoryPieChart = (props) => <Suspense fallback={<Spinner label="Loading chart…" />}><Pie {...props} /></Suspense>
```

Vite code-splits Recharts into separate chunks so the initial bundle (login page, dashboard shell) is smaller; the chart code downloads on first use (visible in `frontend/dist/assets`: `generateCategoricalChart-*.js`, `IncomeExpenseChart-*.js`, `CategoryPie-*.js`).

## 3. Where charts appear

| Page | Chart | Data source / parameters |
|---|---|---|
| Dashboard | Income vs expenses (6 months) | `incomeVsExpense({months: 6})` — fixed, independent of the period picker |
| Dashboard | Spending by category | `spendingByCategory({month, year})` from the period picker |
| Transactions | Spending by category | `spendingByCategory({account_id, date_from, date_to})`; additionally filtered client-side by selected category |
| Analytics | Income vs expenses (6/12/24 months) | `incomeVsExpense({months})` |
| Analytics | Spending by category + ranked list | `spendingByCategory({month, year})`; share % computed client-side: `(c.amount / total) * 100` |

Non-chart visualisations: `ProgressBar` / `BudgetBar` (budget utilization, tone colours), KPI `StatCard`s.

## 4. How the numbers are produced

All figures are computed **server-side** (see [Business_Logic §5](../02_Backend/Business_Logic.md)); the frontend only reshapes them (`Number()` conversion, label formatting). Hence charts exclude transfer legs, and the spending pie sums debits only. The Transactions-page pie only forwards `account_id`, `date_from` and `date_to` to the server (it does not send `type` or `category`), then filters by category locally.

## 5. Empty and loading behaviour

* `cats.data.length === 0` → `EmptyState` "No spending…" instead of an empty pie.
* The income/expense bar chart always renders (the API zero-fills every month), so a new user sees empty bars rather than an empty state.
* While loading: `Spinner`; on error: `ErrorState` with retry.

## 6. Limitations

No drill-down, no chart export, no animation configuration changes from Recharts defaults, no explicit text alternative for charts (the ranked list on Analytics provides the same data in text form).
