import Box from '@mui/material/Box'
import IconButton from '@mui/material/IconButton'
import Stack from '@mui/material/Stack'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import ErrorRounded from '@mui/icons-material/ErrorRounded'
import WarningAmberRounded from '@mui/icons-material/WarningAmberRounded'
import { CategoryDot, ProgressBar } from './ui.jsx'
import { formatINR, formatPercent, titleCase, utilizationTone } from '../utils/format.js'

const TONE_COLOR = { ok: 'success.main', warn: 'warning.main', danger: 'error.main' }

// ok < 80%, warn 80-99%, danger >= 100% (alert icon when the backend reports an alert)
export default function BudgetBar({ category, limit, spent, percent, hasAlert, onDelete, remaining }) {
  const tone = utilizationTone(percent)
  const AlertIcon = tone === 'danger' ? ErrorRounded : WarningAmberRounded
  const alertText = tone === 'danger' ? 'Budget exceeded' : 'Warning: 80% reached'
  return (
    <Box sx={{ py: 1.75, borderBottom: 1, borderColor: 'divider', '&:last-child': { borderBottom: 0, pb: 0 }, '&:first-of-type': { pt: 0 } }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', minWidth: 0 }}>
          <CategoryDot category={category} />
          <Typography variant="subtitle1" noWrap>{titleCase(category)}</Typography>
        </Stack>
        <Stack direction="row" spacing={0.5} sx={{ alignItems: 'center' }}>
          {hasAlert && (
            <Tooltip title={alertText}>
              <AlertIcon fontSize="small" aria-label={alertText} role="img" sx={{ color: TONE_COLOR[tone] }} />
            </Tooltip>
          )}
          <Typography sx={{ fontWeight: 700, color: TONE_COLOR[tone], fontVariantNumeric: 'tabular-nums' }}>{formatPercent(percent)}</Typography>
        </Stack>
      </Stack>
      <ProgressBar percent={percent} tone={tone} label={`${titleCase(category)} budget used`} />
      <Stack direction="row" spacing={1} sx={{ mt: 1, alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', rowGap: 0.5 }}>
        <Typography variant="body2" color="text.secondary">{formatINR(spent)} of {formatINR(limit)}</Typography>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
          {remaining !== undefined && (
            <Typography variant="body2" sx={{ fontWeight: 600, color: remaining < 0 ? 'error.main' : 'text.secondary' }}>
              {remaining < 0 ? `${formatINR(-remaining)} over` : `${formatINR(remaining)} left`}
            </Typography>
          )}
          {onDelete && (
            <Tooltip title="Delete budget">
              <IconButton size="small" color="error" onClick={onDelete} aria-label={`Delete ${titleCase(category)} budget`}><DeleteOutlineRounded fontSize="small" /></IconButton>
            </Tooltip>
          )}
        </Stack>
      </Stack>
    </Box>
  )
}
