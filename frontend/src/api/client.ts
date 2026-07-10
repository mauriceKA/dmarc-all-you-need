import { useEffect, useMemo, useRef, useState } from 'react'

export interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

type Params = Record<string, string | number | undefined>

function buildUrl(path: string, params?: Params): string {
  if (!params) return path
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `${path}?${query}` : path
}

/**
 * Minimal fetch hook. Aborts stale requests and keeps the previous data
 * while reloading, so charts transition instead of flashing empty.
 * Pass `null` as path to skip fetching.
 */
export function useApi<T>(path: string | null, params?: Params): ApiState<T> {
  const url = useMemo(() => (path ? buildUrl(path, params) : null), [path, JSON.stringify(params)])
  const [state, setState] = useState<ApiState<T>>({ data: null, loading: false, error: null })
  const latest = useRef(url)
  latest.current = url

  useEffect(() => {
    if (!url) {
      setState({ data: null, loading: false, error: null })
      return
    }
    const controller = new AbortController()
    setState((s) => ({ ...s, loading: true }))
    fetch(url, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return (await response.json()) as T
      })
      .then((data) => {
        if (latest.current === url) setState({ data, loading: false, error: null })
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        if (latest.current === url)
          setState((s) => ({ data: s.data, loading: false, error: String(error) }))
      })
    return () => controller.abort()
  }, [url])

  return state
}

export async function postSync(): Promise<'started' | 'already_running'> {
  const response = await fetch('/api/sync', { method: 'POST' })
  if (response.status === 409) return 'already_running'
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return 'started'
}
