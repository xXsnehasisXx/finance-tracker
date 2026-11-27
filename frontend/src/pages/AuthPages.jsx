import { useState } from 'react'
import { Link as RouterLink, Navigate } from 'react-router-dom'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import IconButton from '@mui/material/IconButton'
import InputAdornment from '@mui/material/InputAdornment'
import Link from '@mui/material/Link'
import Paper from '@mui/material/Paper'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import AccountBalanceRounded from '@mui/icons-material/AccountBalanceRounded'
import VisibilityOffRounded from '@mui/icons-material/VisibilityOffRounded'
import VisibilityRounded from '@mui/icons-material/VisibilityRounded'
import { useAuth } from '../contexts/AuthContext.jsx'
import ThemeToggle from '../components/layout/ThemeToggle.jsx'
import { rupeeAdornment } from '../components/forms.jsx'

function AuthShell({ title, subtitle, onSubmit, children }) {
  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', placeItems: 'center', p: 2, position: 'relative' }}>
      <ThemeToggle sx={{ position: 'absolute', top: 16, right: 16 }} />
      <Paper component="form" onSubmit={onSubmit} noValidate variant="outlined" sx={{ width: '100%', maxWidth: 440, p: { xs: 3, sm: 4 }, borderRadius: 4, borderColor: 'divider' }}>
        <Stack spacing={2.5}>
          <Stack spacing={1.5} sx={{ alignItems: 'center', textAlign: 'center' }}>
            <Box aria-hidden="true" sx={{ width: 48, height: 48, borderRadius: 3, display: 'grid', placeItems: 'center', bgcolor: 'primary.main', color: 'primary.contrastText' }}>
              <AccountBalanceRounded />
            </Box>
            <Box>
              <Typography variant="h2" component="h1" sx={{ fontSize: '1.5rem' }}>{title}</Typography>
              {subtitle && <Typography color="text.secondary" sx={{ mt: 0.5 }}>{subtitle}</Typography>}
            </Box>
          </Stack>
          {children}
        </Stack>
      </Paper>
    </Box>
  )
}

function PasswordField({ show, onToggle, ...props }) {
  return (
    <TextField type={show ? 'text' : 'password'} label="Password" {...props}
      slotProps={{
        input: {
          endAdornment: (
            <InputAdornment position="end">
              <Tooltip title={show ? 'Hide password' : 'Show password'}>
                <IconButton edge="end" onClick={onToggle} aria-label={show ? 'Hide password' : 'Show password'}>
                  {show ? <VisibilityOffRounded /> : <VisibilityRounded />}
                </IconButton>
              </Tooltip>
            </InputAdornment>
          ),
        },
      }} />
  )
}

const SubmitButton = ({ busy, idle, working }) => (
  <Button type="submit" variant="contained" size="large" fullWidth disabled={busy} startIcon={busy ? <CircularProgress size={18} color="inherit" /> : null}>
    {busy ? working : idle}
  </Button>
)

export function Login() {
  const { user, login } = useAuth()
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [show, setShow] = useState(false)
  if (user) return <Navigate to="/" replace />

  const submit = async (e) => {
    e.preventDefault()
    if (!form.email.trim() || !form.password) return setError('Enter your email and password')
    setBusy(true); setError('')
    try { await login(form.email.trim(), form.password) } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return (
    <AuthShell title="Finance Tracker" subtitle="Sign in to your account" onSubmit={submit}>
      {error && <Alert severity="error" role="alert">{error}</Alert>}
      <TextField label="Email" type="email" autoComplete="username" autoFocus value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
      <PasswordField autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} show={show} onToggle={() => setShow(!show)} />
      <SubmitButton busy={busy} idle="Sign in" working="Signing in…" />
      <Typography color="text.secondary" align="center" variant="body2">New here? <Link component={RouterLink} to="/register">Create an account</Link></Typography>
    </AuthShell>
  )
}

export function Register() {
  const { user, register } = useAuth()
  const [form, setForm] = useState({ name: '', email: '', phone: '', monthly_income: '', password: '' })
  const [errors, setErrors] = useState({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [show, setShow] = useState(false)
  if (user) return <Navigate to="/" replace />
  const field = (k, hint) => ({ value: form[k], onChange: (e) => setForm({ ...form, [k]: e.target.value }), error: Boolean(errors[k]), helperText: errors[k] || hint })

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
    <AuthShell title="Create your account" subtitle="Start tracking your finances" onSubmit={submit}>
      {error && <Alert severity="error" role="alert">{error}</Alert>}
      <TextField label="Full name" autoFocus {...field('name')} />
      <TextField label="Email" type="email" autoComplete="username" {...field('email')} />
      <Box sx={{ display: 'grid', gap: 2.5, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
        <TextField label="Phone (optional)" {...field('phone')} />
        <TextField label="Monthly income" slotProps={{ ...rupeeAdornment, htmlInput: { inputMode: 'decimal' } }} {...field('monthly_income')} />
      </Box>
      <PasswordField autoComplete="new-password" show={show} onToggle={() => setShow(!show)} {...field('password', 'At least 8 characters')} />
      <SubmitButton busy={busy} idle="Create account" working="Creating…" />
      <Typography color="text.secondary" align="center" variant="body2">Already registered? <Link component={RouterLink} to="/login">Sign in</Link></Typography>
    </AuthShell>
  )
}
