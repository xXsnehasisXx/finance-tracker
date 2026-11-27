import { useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Chip from '@mui/material/Chip'
import Divider from '@mui/material/Divider'
import Stack from '@mui/material/Stack'
import Typography from '@mui/material/Typography'
import AccountBalanceRounded from '@mui/icons-material/AccountBalanceRounded'
import AccountBalanceWalletRounded from '@mui/icons-material/AccountBalanceWalletRounded'
import AddRounded from '@mui/icons-material/AddRounded'
import CreditCardRounded from '@mui/icons-material/CreditCardRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import EditRounded from '@mui/icons-material/EditRounded'
import SavingsRounded from '@mui/icons-material/SavingsRounded'
import SwapHorizRounded from '@mui/icons-material/SwapHorizRounded'
import { api } from '../services/api.js'
import { useAsync } from '../hooks/useAsync.js'
import { useToast } from '../contexts/ToastContext.jsx'
import { ConfirmDialog, EmptyState, ErrorState, Modal, PageHeader, SectionCard, Spinner, StatCard } from '../components/ui.jsx'
import { AccountForm, RenameForm, TransferForm } from '../components/forms.jsx'
import { formatINR, titleCase } from '../utils/format.js'

const TYPE_META = {
  savings: { icon: SavingsRounded, color: 'success' },
  checking: { icon: AccountBalanceRounded, color: 'info' },
  credit: { icon: CreditCardRounded, color: 'warning' },
}

function AccountCard({ account, onRename, onDelete }) {
  const meta = TYPE_META[account.account_type] || TYPE_META.checking
  const Icon = meta.icon
  const credit = account.account_type === 'credit'
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ display: 'grid', gap: 0.5, height: '100%', alignContent: 'start' }}>
        <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Chip size="small" color={meta.color} variant="outlined" icon={<Icon />} label={titleCase(account.account_type)} />
          <Typography variant="caption" color="text.secondary">{account.currency}</Typography>
        </Stack>
        <Typography variant="h4" component="h3" sx={{ overflowWrap: 'anywhere' }}>{account.account_name}</Typography>
        <Typography sx={{ fontSize: '1.75rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: credit ? 'warning.main' : 'text.primary' }}>
          {formatINR(account.balance)}
        </Typography>
        <Typography variant="body2" color="text.secondary">{credit ? 'Outstanding amount owed' : 'Available balance'}</Typography>
        <Divider sx={{ my: 1.5 }} />
        <Stack direction="row" spacing={1}>
          <Button size="small" color="inherit" startIcon={<EditRounded />} onClick={onRename} aria-label={`Rename ${account.account_name}`}>Rename</Button>
          <Button size="small" color="error" startIcon={<DeleteOutlineRounded />} onClick={onDelete} aria-label={`Delete ${account.account_name}`}>Delete</Button>
        </Stack>
      </CardContent>
    </Card>
  )
}

export default function Accounts() {
  const toast = useToast()
  const { data, loading, error, reload } = useAsync(() => api.accounts(), [])
  const [modal, setModal] = useState(null) // {kind, account?}
  const [toDelete, setToDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const close = () => setModal(null)

  const done = (message) => { close(); toast.success(message); reload() }

  const remove = async () => {
    setDeleting(true)
    try { await api.deleteAccount(toDelete.id); toast.success('Account deleted'); reload() } catch (e) { toast.error(e.message) }
    setDeleting(false)
    setToDelete(null)
  }

  const assets = (data || []).filter((a) => a.account_type !== 'credit').reduce((s, a) => s + a.balance, 0)
  const owed = (data || []).filter((a) => a.account_type === 'credit').reduce((s, a) => s + a.balance, 0)

  return (
    <>
      <PageHeader title="Accounts" subtitle="Manage your savings, checking and credit accounts"
        actions={<>
          <Button variant="outlined" color="inherit" startIcon={<SwapHorizRounded />} disabled={(data || []).length < 2} onClick={() => setModal({ kind: 'transfer' })}>Transfer / pay card</Button>
          <Button variant="contained" startIcon={<AddRounded />} onClick={() => setModal({ kind: 'create' })}>Add account</Button>
        </>} />
      {loading && !data ? <Spinner /> : error ? <ErrorState error={error} onRetry={reload} /> : data.length === 0 ? (
        <SectionCard>
          <EmptyState icon={<AccountBalanceWalletRounded />} title="No accounts yet" action={<Button variant="contained" onClick={() => setModal({ kind: 'create' })}>Create your first account</Button>}>
            Add a savings, checking or credit account to start tracking.
          </EmptyState>
        </SectionCard>
      ) : (
        <>
          <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, minmax(0, 1fr))' }, mb: 3 }}>
            <StatCard label="Assets" value={formatINR(assets)} tone="good" />
            <StatCard label="Credit owed" value={formatINR(owed)} tone="warn" />
            <StatCard label="Net" value={formatINR(assets - owed)} tone={assets - owed < 0 ? 'bad' : undefined} />
          </Box>
          <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, minmax(0, 1fr))', xl: 'repeat(3, minmax(0, 1fr))' } }}>
            {data.map((a) => (
              <AccountCard key={a.id} account={a} onRename={() => setModal({ kind: 'rename', account: a })} onDelete={() => setToDelete(a)} />
            ))}
          </Box>
        </>
      )}
      {modal?.kind === 'create' && <Modal title="Add account" onClose={close}><AccountForm onCancel={close} onSubmit={async (b) => { await api.createAccount(b); done('Account created') }} /></Modal>}
      {modal?.kind === 'rename' && <Modal title="Rename account" onClose={close}><RenameForm account={modal.account} onCancel={close} onSubmit={async (n) => { await api.renameAccount(modal.account.id, n); done('Account renamed') }} /></Modal>}
      {modal?.kind === 'transfer' && <Modal title="Transfer between accounts" onClose={close}><TransferForm accounts={data} onCancel={close} onSubmit={async (b) => { await api.createTransfer(b); done('Transfer completed') }} /></Modal>}
      <ConfirmDialog open={Boolean(toDelete)} title="Delete account?" busy={deleting} onCancel={() => setToDelete(null)} onConfirm={remove}
        message={toDelete && `Delete "${toDelete.account_name}"? This also deletes ALL of its transactions and cannot be undone.`} />
    </>
  )
}
