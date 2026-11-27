import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import Alert from '@mui/material/Alert'
import Snackbar from '@mui/material/Snackbar'

const ToastContext = createContext(null)

// Shows one notification at a time; extra ones are queued so none are lost.
export function ToastProvider({ children }) {
  const [queue, setQueue] = useState([])
  const [open, setOpen] = useState(false)
  const nextId = useRef(1)
  const current = queue[0]

  const push = useCallback((kind, message) => {
    setQueue((q) => [...q, { id: nextId.current++, kind, message }])
    setOpen(true)
  }, [])

  const handleClose = (_, reason) => {
    if (reason === 'clickaway') return
    setOpen(false)
  }
  const handleExited = () => {
    setQueue((q) => q.slice(1))
    setOpen(true)
  }

  const api = useMemo(() => ({ success: (m) => push('success', m), error: (m) => push('error', m) }), [push])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <Snackbar
        key={current?.id}
        open={open && Boolean(current)}
        autoHideDuration={4500}
        onClose={handleClose}
        slotProps={{ transition: { onExited: handleExited } }}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        {current ? (
          <Alert severity={current.kind} variant="filled" onClose={handleClose} sx={{ width: '100%', boxShadow: 6 }}>
            {current.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
