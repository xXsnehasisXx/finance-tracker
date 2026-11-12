import { useState } from 'react'
import { api } from '../services/api.js'
import { useAsync } from '../hooks/useAsync.js'
import { useToast } from '../contexts/ToastContext.jsx'
import { Card, EmptyState, ErrorState, Modal, Spinner } from '../components/ui.jsx'
import { AccountForm, RenameForm, TransferForm } from '../components/forms.jsx'
import { formatINR, titleCase } from '../utils/format.js'

export default function Accounts() {
  const toast = useToast()
  const { data, loading, error, reload } = useAsync(() => api.accounts(), [])
  const [modal, setModal] = useState(null) // {kind, account?}
  const close = () => setModal(null)

  const done = (message) => { close(); toast.success(message); reload() }

  const remove = async (account) => {
    if (!window.confirm(`Delete "${account.account_name}"? This also deletes ALL of its transactions and cannot be undone.`)) return
    try { await api.deleteAccount(account.id); toast.success('Account deleted'); reload() } catch (e) { toast.error(e.message) }
  }

  const assets = (data || []).filter((a) => a.account_type !== 'credit').reduce((s, a) => s + a.balance, 0)
  const owed = (data || []).filter((a) => a.account_type === 'credit').reduce((s, a) => s + a.balance, 0)

  return (
    <>
      <div className="page-head">
        <h1>Accounts</h1>
        <div className="btn-row">
          <button className="btn" disabled={(data || []).length < 2} onClick={() => setModal({ kind: 'transfer' })}>⇄ Transfer / pay card</button>
          <button className="btn btn-primary" onClick={() => setModal({ kind: 'create' })}>+ Add account</button>
        </div>
      </div>
      {loading && !data ? <Spinner /> : error ? <ErrorState error={error} onRetry={reload} /> : data.length === 0 ? (
        <Card><EmptyState icon="🏦" title="No accounts yet" action={<button className="btn btn-primary" onClick={() => setModal({ kind: 'create' })}>Create your first account</button>}>
          Add a savings, checking or credit account to start tracking.
        </EmptyState></Card>
      ) : (
        <>
          <p className="muted">Assets {formatINR(assets)} · Credit owed {formatINR(owed)} · Net {formatINR(assets - owed)}</p>
          <div className="cards">
            {data.map((a) => (
              <div key={a.id} className="account-card">
                <div className="account-top"><span className={`badge badge-${a.account_type}`}>{titleCase(a.account_type)}</span><span className="muted small">{a.currency}</span></div>
                <h3>{a.account_name}</h3>
                <div className="account-balance">{formatINR(a.balance)}</div>
                <div className="muted small">{a.account_type === 'credit' ? 'Outstanding amount owed' : 'Available balance'}</div>
                <div className="btn-row">
                  <button className="link-btn" onClick={() => setModal({ kind: 'rename', account: a })}>Rename</button>
                  <button className="link-btn danger" onClick={() => remove(a)}>Delete</button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
      {modal?.kind === 'create' && <Modal title="Add account" onClose={close}><AccountForm onCancel={close} onSubmit={async (b) => { await api.createAccount(b); done('Account created') }} /></Modal>}
      {modal?.kind === 'rename' && <Modal title="Rename account" onClose={close}><RenameForm account={modal.account} onCancel={close} onSubmit={async (n) => { await api.renameAccount(modal.account.id, n); done('Account renamed') }} /></Modal>}
      {modal?.kind === 'transfer' && <Modal title="Transfer between accounts" onClose={close}><TransferForm accounts={data} onCancel={close} onSubmit={async (b) => { await api.createTransfer(b); done('Transfer completed') }} /></Modal>}
    </>
  )
}
