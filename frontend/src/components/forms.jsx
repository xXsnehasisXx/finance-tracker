import { useState } from 'react'
import { ACCOUNT_TYPES, BUDGET_CATEGORIES, CATEGORIES, MONTHS, formatINR, titleCase, todayISO } from '../utils/format.js'
import { Field } from './ui.jsx'

const MONEY = /^\d+(\.\d{1,2})?$/

function useForm(initial, validate, onSubmit) {
  const [values, setValues] = useState(initial)
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState('')

  const set = (name) => (e) => setValues((v) => ({ ...v, [name]: e.target.value }))
  const submit = async (e) => {
    e.preventDefault()
    const found = validate(values)
    setErrors(found)
    setFormError('')
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      await onSubmit(values)
    } catch (err) {
      setFormError(err.message)
    } finally {
      setBusy(false)
    }
  }
  return { values, errors, busy, formError, set, submit }
}

function Actions({ busy, onCancel, label }) {
  return (
    <div className="form-actions">
      <button type="button" className="btn btn-ghost" onClick={onCancel}>Cancel</button>
      <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : label}</button>
    </div>
  )
}

const FormError = ({ message }) => (message ? <div className="form-error" role="alert">{message}</div> : null)
const amountError = (v) => (!v ? 'Amount is required' : !MONEY.test(v) || Number(v) <= 0 ? 'Enter an amount greater than 0 (max 2 decimals)' : '')

export function AccountForm({ onSubmit, onCancel }) {
  const f = useForm({ account_name: '', account_type: 'savings', balance: '0' },
    (v) => ({
      ...(v.account_name.trim() ? {} : { account_name: 'Account name is required' }),
      ...(MONEY.test(v.balance) ? {} : { balance: 'Enter a balance of 0 or more' }),
    }),
    (v) => onSubmit({ account_name: v.account_name.trim(), account_type: v.account_type, balance: Number(v.balance) }))
  return (
    <form onSubmit={f.submit} noValidate>
      <FormError message={f.formError} />
      <Field label="Account name" error={f.errors.account_name}><input value={f.values.account_name} onChange={f.set('account_name')} placeholder="e.g. HDFC Savings" autoFocus /></Field>
      <Field label="Account type"><select value={f.values.account_type} onChange={f.set('account_type')}>{ACCOUNT_TYPES.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}</select></Field>
      <Field label={f.values.account_type === 'credit' ? 'Outstanding amount owed (₹)' : 'Initial balance (₹)'} error={f.errors.balance}>
        <input inputMode="decimal" value={f.values.balance} onChange={f.set('balance')} />
      </Field>
      <Actions busy={f.busy} onCancel={onCancel} label="Create account" />
    </form>
  )
}

export function RenameForm({ account, onSubmit, onCancel }) {
  const f = useForm({ account_name: account.account_name }, (v) => (v.account_name.trim() ? {} : { account_name: 'Account name is required' }), (v) => onSubmit(v.account_name.trim()))
  return (
    <form onSubmit={f.submit} noValidate>
      <FormError message={f.formError} />
      <Field label="Account name" error={f.errors.account_name} hint="The account type cannot be changed."><input value={f.values.account_name} onChange={f.set('account_name')} autoFocus /></Field>
      <Actions busy={f.busy} onCancel={onCancel} label="Save" />
    </form>
  )
}

export function TransactionForm({ accounts, onSubmit, onCancel, defaults = {} }) {
  const f = useForm(
    { account_id: accounts[0]?.id ?? '', type: 'debit', category: 'food', amount: '', description: '', merchant: '', transaction_date: todayISO(), ...defaults },
    (v) => ({
      ...(v.account_id ? {} : { account_id: 'Choose an account' }),
      ...(amountError(v.amount) ? { amount: amountError(v.amount) } : {}),
      ...(v.description.trim() ? {} : { description: 'Description is required' }),
      ...(v.transaction_date ? {} : { transaction_date: 'Date is required' }),
      ...(v.category === 'salary' && v.type === 'debit' ? { category: 'Salary is income only (credit)' } : {}),
    }),
    (v) => onSubmit({
      account_id: Number(v.account_id), amount: Number(v.amount), type: v.type, category: v.category,
      description: v.description.trim(), merchant: v.merchant.trim() || null, transaction_date: v.transaction_date,
    }),
  )
  return (
    <form onSubmit={f.submit} noValidate>
      <FormError message={f.formError} />
      <div className="form-row">
        <Field label="Type"><select value={f.values.type} onChange={f.set('type')}><option value="debit">Expense (debit)</option><option value="credit">Income (credit)</option></select></Field>
        <Field label="Account" error={f.errors.account_id}>
          <select value={f.values.account_id} onChange={f.set('account_id')}>{accounts.map((a) => <option key={a.id} value={a.id}>{a.account_name} ({a.account_type})</option>)}</select>
        </Field>
      </div>
      <div className="form-row">
        <Field label="Amount (₹)" error={f.errors.amount}><input inputMode="decimal" value={f.values.amount} onChange={f.set('amount')} placeholder="0.00" autoFocus /></Field>
        <Field label="Category" error={f.errors.category}><select value={f.values.category} onChange={f.set('category')}>{CATEGORIES.map((c) => <option key={c} value={c}>{titleCase(c)}</option>)}</select></Field>
      </div>
      <Field label="Description" error={f.errors.description}><input maxLength={500} value={f.values.description} onChange={f.set('description')} placeholder="e.g. Weekly groceries" /></Field>
      <div className="form-row">
        <Field label="Merchant (optional)"><input maxLength={200} value={f.values.merchant} onChange={f.set('merchant')} placeholder="e.g. BigBazaar" /></Field>
        <Field label="Date" error={f.errors.transaction_date}><input type="date" value={f.values.transaction_date} onChange={f.set('transaction_date')} /></Field>
      </div>
      <Actions busy={f.busy} onCancel={onCancel} label="Add transaction" />
    </form>
  )
}

export function TransferForm({ accounts, onSubmit, onCancel }) {
  const credit = accounts.find((a) => a.account_type === 'credit')
  const asset = accounts.find((a) => a.account_type !== 'credit')
  const f = useForm(
    { source_account_id: asset?.id ?? accounts[0]?.id ?? '', destination_account_id: credit?.id ?? accounts[1]?.id ?? '', amount: '', description: 'Transfer', transfer_date: todayISO() },
    (v) => ({
      ...(String(v.source_account_id) === String(v.destination_account_id) ? { destination_account_id: 'Choose a different account' } : {}),
      ...(amountError(v.amount) ? { amount: amountError(v.amount) } : {}),
      ...(v.description.trim() ? {} : { description: 'Description is required' }),
    }),
    (v) => onSubmit({ source_account_id: Number(v.source_account_id), destination_account_id: Number(v.destination_account_id), amount: Number(v.amount), description: v.description.trim(), transfer_date: v.transfer_date }),
  )
  const opts = accounts.map((a) => <option key={a.id} value={a.id}>{a.account_name} — {formatINR(a.balance)}{a.account_type === 'credit' ? ' owed' : ''}</option>)
  return (
    <form onSubmit={f.submit} noValidate>
      <p className="muted">Moves money between your accounts, e.g. paying a credit card. Transfers are not counted as income or expenses.</p>
      <FormError message={f.formError} />
      <Field label="From"><select value={f.values.source_account_id} onChange={f.set('source_account_id')}>{opts}</select></Field>
      <Field label="To" error={f.errors.destination_account_id}><select value={f.values.destination_account_id} onChange={f.set('destination_account_id')}>{opts}</select></Field>
      <div className="form-row">
        <Field label="Amount (₹)" error={f.errors.amount}><input inputMode="decimal" value={f.values.amount} onChange={f.set('amount')} placeholder="0.00" autoFocus /></Field>
        <Field label="Date"><input type="date" value={f.values.transfer_date} onChange={f.set('transfer_date')} /></Field>
      </div>
      <Field label="Description" error={f.errors.description}><input maxLength={500} value={f.values.description} onChange={f.set('description')} /></Field>
      <Actions busy={f.busy} onCancel={onCancel} label="Transfer" />
    </form>
  )
}

export function BudgetForm({ defaultMonth, defaultYear, onSubmit, onCancel }) {
  const f = useForm(
    { category: 'food', monthly_limit: '', month: defaultMonth, year: defaultYear },
    (v) => ({ ...(amountError(v.monthly_limit) ? { monthly_limit: amountError(v.monthly_limit) } : {}) }),
    (v) => onSubmit({ category: v.category, monthly_limit: Number(v.monthly_limit), month: Number(v.month), year: Number(v.year) }),
  )
  return (
    <form onSubmit={f.submit} noValidate>
      <FormError message={f.formError} />
      <Field label="Category" hint="Salary is income only and cannot have a budget."><select value={f.values.category} onChange={f.set('category')}>{BUDGET_CATEGORIES.map((c) => <option key={c} value={c}>{titleCase(c)}</option>)}</select></Field>
      <Field label="Monthly limit (₹)" error={f.errors.monthly_limit}><input inputMode="decimal" value={f.values.monthly_limit} onChange={f.set('monthly_limit')} placeholder="10000" autoFocus /></Field>
      <div className="form-row">
        <Field label="Month"><select value={f.values.month} onChange={f.set('month')}>{MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></Field>
        <Field label="Year"><input type="number" min="2000" max="2100" value={f.values.year} onChange={f.set('year')} /></Field>
      </div>
      <Actions busy={f.busy} onCancel={onCancel} label="Save budget" />
    </form>
  )
}
