import { useMemo, useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import MenuItem from '@mui/material/MenuItem'
import TextField from '@mui/material/TextField'
import AddRounded from '@mui/icons-material/AddRounded'
import FilterListOffRounded from '@mui/icons-material/FilterListOffRounded'
import PieChartRounded from '@mui/icons-material/PieChartRounded'
import ReceiptLongRounded from '@mui/icons-material/ReceiptLongRounded'
import { api } from '../services/api.js'
import { useAsync } from '../hooks/useAsync.js'
import { useToast } from '../contexts/ToastContext.jsx'
import { EmptyState, ErrorState, Modal, PageHeader, Pagination, SectionCard, Spinner } from '../components/ui.jsx'
import { TransactionForm } from '../components/forms.jsx'
import TransactionTable from '../components/TransactionTable.jsx'
import { CategoryPieChart } from '../components/charts/index.jsx'
import { CATEGORIES, titleCase } from '../utils/format.js'

const EMPTY = { account_id: '', category: '', type: '', date_from: '', date_to: '' }
const selectProps = { select: { displayEmpty: true }, inputLabel: { shrink: true } }
const dateProps = { inputLabel: { shrink: true } }

export default function Transactions() {
  const toast = useToast()
  const [filters, setFilters] = useState(EMPTY)
  const [page, setPage] = useState(1)
  const [adding, setAdding] = useState(false)

  const accounts = useAsync(() => api.accounts(), [])
  const f = JSON.stringify(filters)
  // filter state is part of the dependency list so table and pie chart both refresh on change
  const list = useAsync(() => api.transactions({ ...filters, page, page_size: 15 }), [f, page])
  const pie = useAsync(() => api.spendingByCategory({ account_id: filters.account_id, date_from: filters.date_from, date_to: filters.date_to }), [f])

  const names = useMemo(() => Object.fromEntries((accounts.data || []).map((a) => [a.id, a.account_name])), [accounts.data])
  const pieData = useMemo(() => (pie.data || []).filter((c) => !filters.category || c.category === filters.category), [pie.data, filters.category])
  const invalidRange = filters.date_from && filters.date_to && filters.date_from > filters.date_to
  const change = (name) => (e) => { setFilters({ ...filters, [name]: e.target.value }); setPage(1) }
  const filtered = Object.values(filters).some(Boolean)

  return (
    <>
      <PageHeader title="Transactions" subtitle="Record and review income and expenses"
        actions={<Button variant="contained" startIcon={<AddRounded />} disabled={!accounts.data?.length} onClick={() => setAdding(true)}>Add transaction</Button>} />
      {accounts.data?.length === 0 && <Alert severity="info" sx={{ mb: 3 }}>Create an account first on the Accounts page, then add transactions.</Alert>}

      <SectionCard sx={{ mb: 3 }}>
        <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))', lg: 'repeat(5, minmax(0, 1fr))' }, alignItems: 'start' }}>
          <TextField select size="small" label="Account" value={filters.account_id} onChange={change('account_id')} slotProps={selectProps}>
            <MenuItem value="">All accounts</MenuItem>
            {(accounts.data || []).map((a) => <MenuItem key={a.id} value={a.id}>{a.account_name}</MenuItem>)}
          </TextField>
          <TextField select size="small" label="Category" value={filters.category} onChange={change('category')} slotProps={selectProps}>
            <MenuItem value="">All categories</MenuItem>
            {CATEGORIES.map((c) => <MenuItem key={c} value={c}>{titleCase(c)}</MenuItem>)}
          </TextField>
          <TextField select size="small" label="Type" value={filters.type} onChange={change('type')} slotProps={selectProps}>
            <MenuItem value="">Debit &amp; credit</MenuItem>
            <MenuItem value="debit">Debit</MenuItem>
            <MenuItem value="credit">Credit</MenuItem>
          </TextField>
          <TextField size="small" type="date" label="From date" value={filters.date_from} onChange={change('date_from')} error={Boolean(invalidRange)} slotProps={dateProps} />
          <TextField size="small" type="date" label="To date" value={filters.date_to} onChange={change('date_to')} error={Boolean(invalidRange)} slotProps={dateProps} />
        </Box>
        {(filtered || invalidRange) && (
          <Box sx={{ mt: 2, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            {invalidRange && <Alert severity="error" sx={{ py: 0 }}>"From" date must be before "To" date.</Alert>}
            {filtered && <Button size="small" color="inherit" startIcon={<FilterListOffRounded />} onClick={() => { setFilters(EMPTY); setPage(1) }}>Clear filters</Button>}
          </Box>
        )}
      </SectionCard>

      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: 'minmax(0, 1fr)', xl: 'minmax(0, 2fr) minmax(0, 1fr)' }, alignItems: 'start' }}>
        <SectionCard title={list.data ? `${list.data.total} transaction${list.data.total === 1 ? '' : 's'}` : 'Transactions'}>
          {list.loading && !list.data ? <Spinner /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} />
            : list.data.items.length === 0 ? <EmptyState icon={<ReceiptLongRounded />} title={filtered ? 'No transactions match these filters' : 'No transactions yet'}>{filtered ? 'Try clearing a filter.' : 'Record income and expenses to see them here.'}</EmptyState>
            : <><TransactionTable items={list.data.items} accountNames={names} /><Pagination page={page} pages={list.data.pages} onChange={setPage} /></>}
        </SectionCard>
        <SectionCard title="Spending by category">
          {pie.loading && !pie.data ? <Spinner /> : pie.error ? <ErrorState error={pie.error} onRetry={pie.reload} />
            : pieData.length === 0 ? <EmptyState icon={<PieChartRounded />} title="No spending to chart" /> : <CategoryPieChart data={pieData} />}
        </SectionCard>
      </Box>

      {adding && (
        <Modal title="Add transaction" onClose={() => setAdding(false)}>
          <TransactionForm accounts={accounts.data} onCancel={() => setAdding(false)}
            onSubmit={async (body) => { await api.createTransaction(body); setAdding(false); toast.success('Transaction recorded'); list.reload(); pie.reload(); accounts.reload() }} />
        </Modal>
      )}
    </>
  )
}
