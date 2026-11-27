import { useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import FormControlLabel from '@mui/material/FormControlLabel'
import Stack from '@mui/material/Stack'
import Switch from '@mui/material/Switch'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import LogoutRounded from '@mui/icons-material/LogoutRounded'
import SaveRounded from '@mui/icons-material/SaveRounded'
import { api } from '../services/api.js'
import { useAuth } from '../contexts/AuthContext.jsx'
import { useToast } from '../contexts/ToastContext.jsx'
import { useColorMode } from '../theme/ThemeContext.jsx'
import { PageHeader, SectionCard } from '../components/ui.jsx'
import { rupeeAdornment } from '../components/forms.jsx'
import { formatDate } from '../utils/format.js'

export default function Profile() {
  const { user, setUser, logout } = useAuth()
  const toast = useToast()
  const { mode, toggleMode } = useColorMode()
  const [form, setForm] = useState({ name: user.name, phone: user.phone || '', monthly_income: String(user.monthly_income) })
  const [errors, setErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const field = (k) => ({ value: form[k], onChange: (e) => setForm({ ...form, [k]: e.target.value }), error: Boolean(errors[k]), helperText: errors[k] || ' ' })

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
      <PageHeader title="Profile" subtitle="Your details and preferences" />
      <Stack spacing={3} sx={{ maxWidth: 720 }}>
        <SectionCard title="Your details">
          <Box component="form" onSubmit={submit} noValidate sx={{ display: 'grid', gap: 0.5 }}>
            <TextField label="Email" value={user.email} disabled helperText=" " />
            <TextField label="Full name" {...field('name')} />
            <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
              <TextField label="Phone" {...field('phone')} />
              <TextField label="Monthly income" slotProps={{ ...rupeeAdornment, htmlInput: { inputMode: 'decimal' } }} {...field('monthly_income')} />
            </Box>
            <Typography variant="caption" color="text.secondary">Member since {formatDate(user.created_at)}</Typography>
            <Stack direction="row" sx={{ justifyContent: 'flex-end', pt: 1 }}>
              <Button type="submit" variant="contained" disabled={busy} startIcon={busy ? <CircularProgress size={16} color="inherit" /> : <SaveRounded />}>
                {busy ? 'Saving…' : 'Save changes'}
              </Button>
            </Stack>
          </Box>
        </SectionCard>

        <SectionCard title="Appearance">
          <FormControlLabel
            control={<Switch checked={mode === 'dark'} onChange={toggleMode} />}
            label={mode === 'dark' ? 'Dark theme' : 'Light theme'} />
          <Typography variant="body2" color="text.secondary">Your choice is saved on this device.</Typography>
        </SectionCard>

        <SectionCard title="Session">
          <Button variant="outlined" color="inherit" startIcon={<LogoutRounded />} onClick={logout}>Log out</Button>
        </SectionCard>
      </Stack>
    </>
  )
}
