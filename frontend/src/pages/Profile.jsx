import { useState } from 'react'
import { api } from '../services/api.js'
import { useAuth } from '../contexts/AuthContext.jsx'
import { useToast } from '../contexts/ToastContext.jsx'
import { Card, Field } from '../components/ui.jsx'
import { formatDate } from '../utils/format.js'

export default function Profile() {
  const { user, setUser, logout } = useAuth()
  const toast = useToast()
  const [form, setForm] = useState({ name: user.name, phone: user.phone || '', monthly_income: String(user.monthly_income) })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    const found = {}
    if (!form.name.trim()) found.name = 'Name is required'
    if (!/^\d+(\.\d{1,2})?$/.test(form.monthly_income)) found.monthly_income = 'Enter a valid amount'
    setErrors(found)
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      setUser(await api.updateMe({ name: form.name.trim(), phone: form.phone.trim() || null, monthly_income: Number(form.monthly_income) }))
      toast.success('Profile updated')
    } catch (err) { toast.error(err.message) } finally { setBusy(false) }
  }

  return (
    <>
      <div className="page-head"><h1>Profile</h1></div>
      <Card title="Your details">
        <form onSubmit={submit} noValidate className="narrow">
          <Field label="Email"><input value={user.email} disabled /></Field>
          <Field label="Full name" error={errors.name}><input value={form.name} onChange={set('name')} /></Field>
          <div className="form-row">
            <Field label="Phone"><input value={form.phone} onChange={set('phone')} /></Field>
            <Field label="Monthly income (₹)" error={errors.monthly_income}><input inputMode="decimal" value={form.monthly_income} onChange={set('monthly_income')} /></Field>
          </div>
          <p className="muted small">Member since {formatDate(user.created_at)}</p>
          <div className="form-actions"><button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</button></div>
        </form>
      </Card>
      <Card title="Session"><button className="btn" onClick={logout}>Log out</button></Card>
    </>
  )
}
