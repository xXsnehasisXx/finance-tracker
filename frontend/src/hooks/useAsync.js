import { useCallback, useEffect, useRef, useState } from 'react'

// Runs an async loader; exposes data/loading/error and a reload() function. Re-runs when deps change.
export function useAsync(loader, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null })
  const run = useRef(0)

  const load = useCallback(() => {
    const id = ++run.current
    setState((s) => ({ ...s, loading: true, error: null }))
    return loader()
      .then((data) => { if (id === run.current) setState({ data, loading: false, error: null }) })
      .catch((error) => { if (id === run.current) setState({ data: null, loading: false, error }) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => { load() }, [load])
  return { ...state, reload: load }
}
