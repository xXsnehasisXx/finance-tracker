import { useMemo, useState } from 'react'
import { api } from '../services/api.js'
import { useAsync } from '../hooks/useAsync.js'
import { useToast } from '../contexts/ToastContext.jsx'
import { Card, EmptyState, ErrorState, Modal, Pagination, Spinner } from '../components/ui.jsx'
import { TransactionForm } from '../components/forms.jsx'
import TransactionTable from '../components/TransactionTable.jsx'
import { CategoryPieChart } from '../components/charts/index.jsx'
import { CATEGORIES, titleCase } from '../utils/format.js'

const EMPTY = { account_id: '', category: '', type: '', date_from: '', date_to: '' }

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
      <div className="page-head">
        <h1>Transactions</h1>
        <button className="btn btn-primary" disabled={!accounts.data?.length} onClick={() => setAdding(true)}>+ Add transaction</button>
      </div>
      {accounts.data?.length === 0 && <div className="banner">Create an account first on the Accounts page, then add transactions.</div>}

      <Card className="filters">
        <select value={filters.account_id} onChange={change('account_id')} aria-label="Account"><option value="">All accounts</option>{(accounts.data || []).map((a) => <option key={a.id} value={a.id}>{a.account_name}</option>)}</select>
        <select value={filters.category} onChange={change('category')} aria-label="Category"><option value="">All categories</option>{CATEGORIES.map((c) => <option key={c} value={c}>{titleCase(c)}</option>)}</select>
        <select value={filters.type} onChange={change('type')} aria-label="Type"><option value="">Debit &amp; credit</option><option value="debit">Debit</option><option value="credit">Credit</option></select>
        <input type="date" value={filters.date_from} onChange={change('date_from')} aria-label="From date" />
        <input type="date" value={filters.date_to} onChange={change('date_to')} aria-label="To date" />
        {filtered && <button className="btn btn-ghost" onClick={() => { setFilters(EMPTY); setPage(1) }}>Clear</button>}
      </Card>
      {invalidRange && <div className="form-error">"From" date must be before "To" date.</div>}

      <div className="grid-tx">
        <Card title={list.data ? `${list.data.total} transaction${list.data.total === 1 ? '' : 's'}` : 'Transactions'}>
          {list.loading && !list.data ? <Spinner /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} />
            : list.data.items.length === 0 ? <EmptyState title={filtered ? 'No transactions match these filters' : 'No transactions yet'}>{filtered ? 'Try clearing a filter.' : 'Record income and expenses to see them here.'}</EmptyState>
            : <><TransactionTable items={list.data.items} accountNames={names} /><Pagination page={page} pages={list.data.pages} onChange={setPage} /></>}
        </Card>
        <Card title="Spending by category">
          {pie.loading && !pie.data ? <Spinner /> : pie.error ? <ErrorState error={pie.error} onRetry={pie.reload} />
            : pieData.length === 0 ? <EmptyState icon="🥧" title="No spending to chart" /> : <CategoryPieChart data={pieData} />}
        </Card>
      </div>

      {adding && (
        <Modal title="Add transaction" onClose={() => setAdding(false)}>
          <TransactionForm accounts={accounts.data} onCancel={() => setAdding(false)}
            onSubmit={async (body) => { await api.createTransaction(body); setAdding(false); toast.success('Transaction recorded'); list.reload(); pie.reload(); accounts.reload() }} />
        </Modal>
      )}
    </>
  )
}
