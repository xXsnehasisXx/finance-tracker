import { createContext, useCallback, useContext, useMemo, useState } from 'react'

const ToastContext = createContext(null)
let nextId = 1

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), [])
  const push = useCallback((kind, message) => {
    const id = nextId++
    setToasts((t) => [...t, { id, kind, message }])
    setTimeout(() => dismiss(id), 4500)
  }, [dismiss])

  const api = useMemo(() => ({
    success: (m) => push('success', m),
    error: (m) => push('error', m),
  }), [push])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`} onClick={() => dismiss(t.id)}>
            <span>{t.kind === 'success' ? '✓' : '⚠'}</span> {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => useContext(ToastContext)
