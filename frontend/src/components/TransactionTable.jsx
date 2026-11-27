import { useMediaQuery } from '@mui/material'
import { useTheme } from '@mui/material/styles'
import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Divider from '@mui/material/Divider'
import Stack from '@mui/material/Stack'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import Typography from '@mui/material/Typography'
import ArrowDownwardRounded from '@mui/icons-material/ArrowDownwardRounded'
import ArrowUpwardRounded from '@mui/icons-material/ArrowUpwardRounded'
import SwapHorizRounded from '@mui/icons-material/SwapHorizRounded'
import { CategoryDot } from './ui.jsx'
import { formatDate, formatINR, titleCase } from '../utils/format.js'

const TypeChip = ({ type }) => (
  <Chip size="small" variant="outlined" color={type === 'debit' ? 'error' : 'success'}
    icon={type === 'debit' ? <ArrowUpwardRounded /> : <ArrowDownwardRounded />} label={titleCase(type)} />
)
const TransferChip = ({ sx }) => <Chip size="small" color="info" variant="outlined" icon={<SwapHorizRounded />} label="Transfer" sx={sx} />
const Amount = ({ t }) => (
  <Typography component="span" sx={{ fontWeight: 700, whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums', color: t.type === 'debit' ? 'error.main' : 'success.main' }}>
    {t.type === 'debit' ? '−' : '+'}{formatINR(t.amount)}
  </Typography>
)

// Table on tablet/desktop; stacked list on phones so nothing needs horizontal scrolling.
export default function TransactionTable({ items, accountNames }) {
  const theme = useTheme()
  const compact = useMediaQuery(theme.breakpoints.down('sm'))
  const account = (t) => accountNames?.[t.account_id] || `#${t.account_id}`

  if (compact) {
    return (
      <Box component="ul" sx={{ listStyle: 'none', m: 0, p: 0 }}>
        {items.map((t, i) => (
          <Box component="li" key={t.id}>
            {i > 0 && <Divider />}
            <Stack direction="row" spacing={1.5} sx={{ py: 1.5, justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Box sx={{ minWidth: 0 }}>
                <Typography sx={{ fontWeight: 600, overflowWrap: 'anywhere' }}>{t.description}</Typography>
                <Stack direction="row" spacing={0.75} sx={{ alignItems: 'flex-start', mt: 0.5 }}>
                  <Box sx={{ pt: '5px', display: 'flex' }}><CategoryDot category={t.category} size={8} /></Box>
                  <Typography variant="caption" color="text.secondary" sx={{ minWidth: 0, overflowWrap: 'anywhere' }}>{titleCase(t.category)} · {account(t)}{t.merchant ? ` · ${t.merchant}` : ''}</Typography>
                </Stack>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mt: 0.75 }}>
                  <Typography variant="caption" color="text.secondary">{formatDate(t.transaction_date)}</Typography>
                  {t.is_transfer && <TransferChip />}
                </Stack>
              </Box>
              <Stack sx={{ alignItems: 'flex-end', gap: 0.5, flexShrink: 0 }}><Amount t={t} /><TypeChip type={t.type} /></Stack>
            </Stack>
          </Box>
        ))}
      </Box>
    )
  }

  return (
    <TableContainer>
      <Table aria-label="Transactions">
        <TableHead>
          <TableRow>
            <TableCell>Date</TableCell><TableCell>Description</TableCell><TableCell>Category</TableCell>
            <TableCell>Account</TableCell><TableCell align="right">Amount</TableCell><TableCell>Type</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.map((t) => (
            <TableRow key={t.id} hover>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>{formatDate(t.transaction_date)}</TableCell>
              <TableCell>
                {t.description}{t.is_transfer && <TransferChip sx={{ ml: 1 }} />}
                {t.merchant && <Typography variant="caption" color="text.secondary" component="div">{t.merchant}</Typography>}
              </TableCell>
              <TableCell>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}><CategoryDot category={t.category} /><span>{titleCase(t.category)}</span></Stack>
              </TableCell>
              <TableCell>{account(t)}</TableCell>
              <TableCell align="right"><Amount t={t} /></TableCell>
              <TableCell><TypeChip type={t.type} /></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
