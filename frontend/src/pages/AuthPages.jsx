import { useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext.jsx'
import { Field } from '../components/ui.jsx'

export function Login() {
  const { user, login } = useAuth()
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (user) return <Navigate to="/" replace />

  const submit = async (e) => {
    e.preventDefault()
    if (!form.email.trim() || !form.password) return setError('Enter your email and password')
    setBusy(true); setError('')
    try { await login(form.email.trim(), form.password) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit} noValidate>
        <h1>💰 Finance Tracker</h1>
        <p className="muted">Sign in to your account</p>
        {error && <div className="form-error" role="alert">{error}</div>}
        <Field label="Email"><input type="email" autoComplete="username" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} autoFocus /></Field>
        <Field label="Password"><input type="password" autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <p className="muted center">New here? <Link to="/register">Create an account</Link></p>
      </form>
    </div>
  )
}

export function Register() {
  const { user, register } = useAuth()
  const [form, setForm] = useState({ name: '', email: '', phone: '', monthly_income: '', password: '' })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (user) return <Navigate to="/" replace />
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e) => {
    e.preventDefault()
    const found = {}
    if (!form.name.trim()) found.name = 'Name is required'
    if (!/^\S+@\S+\.\S+$/.test(form.email)) found.email = 'Enter a valid email'
    if (form.password.length < 8) found.password = 'At least 8 characters'
    if (form.monthly_income && !/^\d+(\.\d{1,2})?$/.test(form.monthly_income)) found.monthly_income = 'Enter a valid amount'
    setErrors(found); setError('')
    if (Object.keys(found).length) return
    setBusy(true)
    try {
      await register({ name: form.name.trim(), email: form.email.trim(), phone: form.phone.trim() || null, monthly_income: Number(form.monthly_income || 0), password: form.password })
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={submit} noValidate>
        <h1>Create your account</h1>
        {error && <div className="form-error" role="alert">{error}</div>}
        <Field label="Full name" error={errors.name}><input value={form.name} onChange={set('name')} autoFocus /></Field>
        <Field label="Email" error={errors.email}><input type="email" autoComplete="username" value={form.email} onChange={set('email')} /></Field>
        <div className="form-row">
          <Field label="Phone (optional)"><input value={form.phone} onChange={set('phone')} /></Field>
          <Field label="Monthly income (₹)" error={errors.monthly_income}><input inputMode="decimal" value={form.monthly_income} onChange={set('monthly_income')} /></Field>
        </div>
        <Field label="Password" error={errors.password}><input type="password" autoComplete="new-password" value={form.password} onChange={set('password')} /></Field>
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? 'Creating…' : 'Create account'}</button>
        <p className="muted center">Already registered? <Link to="/login">Sign in</Link></p>
      </form>
    </div>
  )
}
