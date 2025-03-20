import { useCallback, useEffect, useRef, useState } from 'react'
import { errorMessage } from './errors'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
  setData: (value: T | null) => void
}

/**
 * Fetch data on mount (and whenever `deps` change) with loading and error
 * states. The error message always contains the backend `detail` when there is
 * one, so the UI never shows a generic "request failed".
 */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [nonce, setNonce] = useState(0)
  const mounted = useRef(true)
  const loaderRef = useRef(loader)
  loaderRef.current = loader

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    loaderRef
      .current()
      .then((value) => {
        if (cancelled || !mounted.current) return
        setData(value)
        setLoading(false)
      })
      .catch((cause: unknown) => {
        if (cancelled || !mounted.current) return
        setError(errorMessage(cause, 'The request failed.'))
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce])

  const reload = useCallback(() => setNonce((value) => value + 1), [])

  return { data, loading, error, reload, setData }
}

/** Simple mutation helper: tracks busy state and surfaces backend errors. */
export function useMutation<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
): {
  run: (...args: TArgs) => Promise<TResult | null>
  busy: boolean
  error: string | null
  reset: () => void
} {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const actionRef = useRef(action)
  actionRef.current = action

  const run = useCallback(async (...args: TArgs): Promise<TResult | null> => {
    setBusy(true)
    setError(null)
    try {
      return await actionRef.current(...args)
    } catch (cause) {
      setError(errorMessage(cause, 'The action failed.'))
      return null
    } finally {
      setBusy(false)
    }
  }, [])

  return { run, busy, error, reset: () => setError(null) }
}
