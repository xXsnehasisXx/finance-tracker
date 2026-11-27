import { useMediaQuery } from '@mui/material'
import { alpha, useTheme } from '@mui/material/styles'
import Alert from '@mui/material/Alert'
import AlertTitle from '@mui/material/AlertTitle'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogContentText from '@mui/material/DialogContentText'
import DialogTitle from '@mui/material/DialogTitle'
import IconButton from '@mui/material/IconButton'
import LinearProgress from '@mui/material/LinearProgress'
import MenuItem from '@mui/material/MenuItem'
import MuiPagination from '@mui/material/Pagination'
import Stack from '@mui/material/Stack'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import CloseRounded from '@mui/icons-material/CloseRounded'
import InboxRounded from '@mui/icons-material/InboxRounded'
import RefreshRounded from '@mui/icons-material/RefreshRounded'
import { CATEGORY_COLORS } from '../theme/themeConstants.js'

const TONE_COLOR = { good: 'success', bad: 'error', warn: 'warning', info: 'info' }

export function PageHeader({ title, subtitle, actions }) {
  return (
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 3, alignItems: { sm: 'center' }, justifyContent: 'space-between' }}>
      <Box sx={{ minWidth: 0 }}>
        <Typography variant="h1" component="h1" sx={{ fontSize: { xs: '1.5rem', md: '1.75rem' } }}>{title}</Typography>
        {subtitle && <Typography color="text.secondary" sx={{ mt: 0.5 }}>{subtitle}</Typography>}
      </Box>
      {actions && <Stack direction="row" spacing={1.5} useFlexGap sx={{ flexWrap: 'wrap', alignItems: 'center' }}>{actions}</Stack>}
    </Stack>
  )
}

export function Spinner({ label = 'Loading…', fullScreen = false }) {
  return (
    <Stack role="status" aria-live="polite" direction="row" spacing={1.5}
      sx={{ alignItems: 'center', justifyContent: 'center', color: 'text.secondary', p: 4, ...(fullScreen && { minHeight: '100vh' }) }}>
      <CircularProgress size={22} thickness={5} aria-hidden="true" />
      <Typography variant="body2">{label}</Typography>
    </Stack>
  )
}

export function EmptyState({ icon, title, children, action }) {
  return (
    <Stack spacing={1} sx={{ alignItems: 'center', textAlign: 'center', py: 4, px: 2 }}>
      <Box aria-hidden="true" sx={{ width: 52, height: 52, borderRadius: '50%', display: 'grid', placeItems: 'center', color: 'primary.main', bgcolor: (t) => alpha(t.palette.primary.main, 0.14) }}>
        {icon || <InboxRounded />}
      </Box>
      <Typography variant="h5" component="h3">{title}</Typography>
      {children && <Typography variant="body2" color="text.secondary" component="div" sx={{ maxWidth: 420 }}>{children}</Typography>}
      {action && <Box sx={{ pt: 1 }}>{action}</Box>}
    </Stack>
  )
}

export function ErrorState({ error, onRetry }) {
  return (
    <Alert severity="error" role="alert"
      action={onRetry && <Button color="inherit" size="small" startIcon={<RefreshRounded />} onClick={onRetry}>Try again</Button>}>
      <AlertTitle>Something went wrong</AlertTitle>
      {error?.message || 'Unexpected error'}
    </Alert>
  )
}

// Titled panel used for every content block.
export function SectionCard({ title, actions, children, sx }) {
  return (
    <Card sx={{ minWidth: 0, ...sx }}>
      <CardContent>
        {(title || actions) && (
          <Stack direction="row" spacing={1} sx={{ mb: 2, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', rowGap: 1 }}>
            {title && <Typography variant="h4" component="h2">{title}</Typography>}
            {actions && <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>{actions}</Stack>}
          </Stack>
        )}
        {children}
      </CardContent>
    </Card>
  )
}

export function StatCard({ label, value, sub, tone, icon }) {
  const color = TONE_COLOR[tone] || 'primary'
  return (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ display: 'grid', gap: 0.5 }}>
        <Stack direction="row" sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="overline" color="text.secondary">{label}</Typography>
          {icon && (
            <Box aria-hidden="true" sx={{ width: 36, height: 36, borderRadius: 2, display: 'grid', placeItems: 'center',
              color: (t) => (tone || t.palette.mode === 'dark' ? t.palette[color].main : t.palette.primary.dark),
              bgcolor: (t) => alpha(t.palette[color].main, 0.14) }}>
              {icon}
            </Box>
          )}
        </Stack>
        <Typography component="strong" sx={{ fontSize: { xs: '1.35rem', md: '1.5rem' }, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: tone ? `${color}.main` : 'text.primary', overflowWrap: 'anywhere' }}>
          {value}
        </Typography>
        {sub && <Typography variant="caption" color="text.secondary">{sub}</Typography>}
      </CardContent>
    </Card>
  )
}

export function Modal({ title, onClose, children, maxWidth = 'sm' }) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth={maxWidth} fullScreen={fullScreen} aria-labelledby="modal-title">
      <DialogTitle id="modal-title" sx={{ pr: 7 }}>
        {title}
        <Tooltip title="Close">
          <IconButton aria-label="Close" onClick={onClose} sx={{ position: 'absolute', right: 12, top: 12 }}><CloseRounded /></IconButton>
        </Tooltip>
      </DialogTitle>
      <DialogContent sx={{ pt: '8px !important' }}>{children}</DialogContent>
    </Dialog>
  )
}

export function ConfirmDialog({ open, title, message, confirmLabel = 'Delete', busy = false, onConfirm, onCancel }) {
  return (
    <Dialog open={open} onClose={busy ? undefined : onCancel} maxWidth="xs" fullWidth aria-labelledby="confirm-title">
      <DialogTitle id="confirm-title">{title}</DialogTitle>
      <DialogContent><DialogContentText>{message}</DialogContentText></DialogContent>
      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button color="inherit" onClick={onCancel} disabled={busy}>Cancel</Button>
        <Button variant="contained" color="error" onClick={onConfirm} disabled={busy} autoFocus
          startIcon={busy ? <CircularProgress size={16} color="inherit" /> : null}>
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export function CategoryDot({ category, size = 10 }) {
  return <Box component="span" aria-hidden="true" sx={{ display: 'inline-block', flexShrink: 0, width: size, height: size, borderRadius: '50%', bgcolor: CATEGORY_COLORS[category] || CATEGORY_COLORS.other }} />
}

const PROGRESS_COLOR = { ok: 'success', warn: 'warning', danger: 'error' }

export function ProgressBar({ percent, tone, label }) {
  const value = Math.min(100, Math.max(0, percent))
  return <LinearProgress variant="determinate" value={value} color={PROGRESS_COLOR[tone] || 'primary'} aria-label={label || 'Budget utilization'} />
}

export function Pagination({ page, pages, onChange }) {
  if (pages <= 1) return null
  return (
    <Stack sx={{ alignItems: 'center', mt: 2 }}>
      <MuiPagination count={pages} page={page} onChange={(_, p) => onChange(p)} siblingCount={0} boundaryCount={1} />
      <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>Page {page} of {pages}</Typography>
    </Stack>
  )
}

export function PeriodPicker({ month, year, onChange, months }) {
  const thisYear = new Date().getFullYear()
  const years = Array.from({ length: 7 }, (_, i) => thisYear - 3 + i)
  return (
    <Stack direction="row" spacing={1}>
      <TextField select size="small" value={month} onChange={(e) => onChange(Number(e.target.value), year)} sx={{ minWidth: 130 }}
        slotProps={{ select: { SelectDisplayProps: { 'aria-label': 'Month' } } }}>
        {months.map((m, i) => <MenuItem key={m} value={i + 1}>{m}</MenuItem>)}
      </TextField>
      <TextField select size="small" value={year} onChange={(e) => onChange(month, Number(e.target.value))} sx={{ minWidth: 100 }}
        slotProps={{ select: { SelectDisplayProps: { 'aria-label': 'Year' } } }}>
        {years.map((y) => <MenuItem key={y} value={y}>{y}</MenuItem>)}
      </TextField>
    </Stack>
  )
}
