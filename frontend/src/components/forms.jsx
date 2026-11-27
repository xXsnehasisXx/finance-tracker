import { useState } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import MenuItem from '@mui/material/MenuItem'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import InputAdornment from '@mui/material/InputAdornment'
import { ACCOUNT_TYPES, BUDGET_CATEGORIES, CATEGORIES, MONTHS, formatINR, titleCase, todayISO } from '../utils/format.js'

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
  // Props shared by every field: value, change handler, and error/hint presentation.
  const field = (name, hint) => ({
    name,
    value: values[name],
    onChange: set(name),
    error: Boolean(errors[name]),
    helperText: errors[name] || hint || ' ',
  })
  return { values, errors, busy, formError, field, submit }
}

export const rupeeAdornment = { input: { startAdornment: <InputAdornment position="start">₹</InputAdornment> } }

export function FormActions({ busy, onCancel, label }) {
  return (
    <Stack direction="row" spacing={1.5} sx={{ justifyContent: 'flex-end', pt: 1 }}>
      <Button type="button" color="inherit" onClick={onCancel} disabled={busy}>Cancel</Button>
      <Button type="submit" variant="contained" disabled={busy} startIcon={busy ? <CircularProgress size={16} color="inherit" /> : null}>
        {busy ? 'Saving…' : label}
      </Button>
    </Stack>
  )
}

const FormError = ({ message }) => (message ? <Alert severity="error" role="alert" sx={{ mb: 2 }}>{message}</Alert> : null)
const FormBody = ({ children, ...props }) => <Box component="form" noValidate {...props} sx={{ display: 'grid', gap: 0.5, pt: 0.5 }}>{children}</Box>
const Row = ({ children }) => <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>{children}</Box>
const amountError = (v) => (!v ? 'Amount is required' : !MONEY.test(v) || Number(v) <= 0 ? 'Enter an amount greater than 0 (max 2 decimals)' : '')
const dateField = { inputLabel: { shrink: true } }

const options = (list) => list.map((t) => <MenuItem key={t} value={t}>{titleCase(t)}</MenuItem>)

export function AccountForm({ onSubmit, onCancel }) {
  const f = useForm({ account_name: '', account_type: 'savings', balance: '0' },
    (v) => ({
      ...(v.account_name.trim() ? {} : { account_name: 'Account name is required' }),
      ...(MONEY.test(v.balance) ? {} : { balance: 'Enter a balance of 0 or more' }),
    }),
    (v) => onSubmit({ account_name: v.account_name.trim(), account_type: v.account_type, balance: Number(v.balance) }))
  return (
    <FormBody onSubmit={f.submit}>
      <FormError message={f.formError} />
      <TextField label="Account name" placeholder="e.g. HDFC Savings" autoFocus {...f.field('account_name')} />
      <TextField select label="Account type" {...f.field('account_type')}>{options(ACCOUNT_TYPES)}</TextField>
      <TextField label={f.values.account_type === 'credit' ? 'Outstanding amount owed' : 'Initial balance'} slotProps={{ ...rupeeAdornment, htmlInput: { inputMode: 'decimal' } }} {...f.field('balance')} />
      <FormActions busy={f.busy} onCancel={onCancel} label="Create account" />
    </FormBody>
  )
}

export function RenameForm({ account, onSubmit, onCancel }) {
  const f = useForm({ account_name: account.account_name }, (v) => (v.account_name.trim() ? {} : { account_name: 'Account name is required' }), (v) => onSubmit(v.account_name.trim()))
  return (
    <FormBody onSubmit={f.submit}>
      <FormError message={f.formError} />
      <TextField label="Account name" autoFocus {...f.field('account_name', 'The account type cannot be changed.')} />
      <FormActions busy={f.busy} onCancel={onCancel} label="Save" />
    </FormBody>
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
    <FormBody onSubmit={f.submit}>
      <FormError message={f.formError} />
      <Row>
        <TextField select label="Type" {...f.field('type')}>
          <MenuItem value="debit">Expense (debit)</MenuItem>
          <MenuItem value="credit">Income (credit)</MenuItem>
        </TextField>
        <TextField select label="Account" {...f.field('account_id')}>
          {accounts.map((a) => <MenuItem key={a.id} value={a.id}>{a.account_name} ({a.account_type})</MenuItem>)}
        </TextField>
      </Row>
      <Row>
        <TextField label="Amount" placeholder="0.00" autoFocus slotProps={{ ...rupeeAdornment, htmlInput: { inputMode: 'decimal' } }} {...f.field('amount')} />
        <TextField select label="Category" {...f.field('category')}>{options(CATEGORIES)}</TextField>
      </Row>
      <TextField label="Description" placeholder="e.g. Weekly groceries" slotProps={{ htmlInput: { maxLength: 500 } }} {...f.field('description')} />
      <Row>
        <TextField label="Merchant (optional)" placeholder="e.g. BigBazaar" slotProps={{ htmlInput: { maxLength: 200 } }} {...f.field('merchant')} />
        <TextField label="Date" type="date" slotProps={dateField} {...f.field('transaction_date')} />
      </Row>
      <FormActions busy={f.busy} onCancel={onCancel} label="Add transaction" />
    </FormBody>
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
  const opts = accounts.map((a) => <MenuItem key={a.id} value={a.id}>{a.account_name} — {formatINR(a.balance)}{a.account_type === 'credit' ? ' owed' : ''}</MenuItem>)
  return (
    <FormBody onSubmit={f.submit}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Moves money between your accounts, e.g. paying a credit card. Transfers are not counted as income or expenses.
      </Typography>
      <FormError message={f.formError} />
      <TextField select label="From" {...f.field('source_account_id')}>{opts}</TextField>
      <TextField select label="To" {...f.field('destination_account_id')}>{opts}</TextField>
      <Row>
        <TextField label="Amount" placeholder="0.00" autoFocus slotProps={{ ...rupeeAdornment, htmlInput: { inputMode: 'decimal' } }} {...f.field('amount')} />
        <TextField label="Date" type="date" slotProps={dateField} {...f.field('transfer_date')} />
      </Row>
      <TextField label="Description" slotProps={{ htmlInput: { maxLength: 500 } }} {...f.field('description')} />
      <FormActions busy={f.busy} onCancel={onCancel} label="Transfer" />
    </FormBody>
  )
}

export function BudgetForm({ defaultMonth, defaultYear, onSubmit, onCancel }) {
  const f = useForm(
    { category: 'food', monthly_limit: '', month: defaultMonth, year: defaultYear },
    (v) => ({ ...(amountError(v.monthly_limit) ? { monthly_limit: amountError(v.monthly_limit) } : {}) }),
    (v) => onSubmit({ category: v.category, monthly_limit: Number(v.monthly_limit), month: Number(v.month), year: Number(v.year) }),
  )
  return (
    <FormBody onSubmit={f.submit}>
      <FormError message={f.formError} />
      <TextField select label="Category" {...f.field('category', 'Salary is income only and cannot have a budget.')}>{options(BUDGET_CATEGORIES)}</TextField>
      <TextField label="Monthly limit" placeholder="10000" autoFocus slotProps={{ ...rupeeAdornment, htmlInput: { inputMode: 'decimal' } }} {...f.field('monthly_limit')} />
      <Row>
        <TextField select label="Month" {...f.field('month')}>{MONTHS.map((m, i) => <MenuItem key={m} value={i + 1}>{m}</MenuItem>)}</TextField>
        <TextField label="Year" type="number" slotProps={{ htmlInput: { min: 2000, max: 2100 } }} {...f.field('year')} />
      </Row>
      <FormActions busy={f.busy} onCancel={onCancel} label="Save budget" />
    </FormBody>
  )
}
