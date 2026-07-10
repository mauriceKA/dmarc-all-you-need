import { useEffect, useRef, useState } from 'react'
import { postSync } from '../api/client'
import type { SyncStatus } from '../api/types'
import { relativeTime } from '../lib/format'
import { useFilters } from '../state/FiltersContext'

async function fetchStatus(): Promise<SyncStatus> {
  const response = await fetch('/api/sync/status')
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return (await response.json()) as SyncStatus
}

/** "Sync now" button with a live status pill; polls only while a sync runs. */
export function SyncButton() {
  const { bumpRefresh } = useFilters()
  const [status, setStatus] = useState<SyncStatus | null>(null)
  const [flash, setFlash] = useState<string | null>(null)
  const wasRunning = useRef(false)

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    let cancelled = false

    const tick = async () => {
      try {
        const next = await fetchStatus()
        if (cancelled) return
        setStatus(next)
        if (wasRunning.current && !next.running) {
          // a sync just finished: refresh all data, show what happened
          bumpRefresh()
          if (next.last_result && next.last_result.imported > 0) {
            setFlash(`${next.last_result.imported} new`)
            setTimeout(() => setFlash(null), 5000)
          }
        }
        wasRunning.current = next.running
        timer = setTimeout(tick, next.running ? 2000 : 30_000)
      } catch {
        if (!cancelled) timer = setTimeout(tick, 30_000)
      }
    }
    tick()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [bumpRefresh])

  const running = status?.running ?? false

  const onClick = async () => {
    try {
      await postSync()
      wasRunning.current = true
      setStatus((s) => (s ? { ...s, running: true } : s))
    } catch {
      /* surfaced via status poll */
    }
  }

  return (
    <div className="flex items-center gap-2">
      {flash && <span className="text-sm font-medium text-pass">{flash}</span>}
      {!running && status?.last_error && (
        <span
          className="max-w-56 truncate text-sm text-fail"
          title={status.last_error}
        >
          sync failed
        </span>
      )}
      {!running && !status?.last_error && status?.last_run_at && !flash && (
        <span className="text-sm text-ink-muted max-md:hidden">
          synced {relativeTime(status.last_run_at)}
        </span>
      )}
      <button
        type="button"
        onClick={onClick}
        disabled={running}
        className="flex h-9 items-center gap-2 rounded-lg border border-hairline bg-surface px-3
                   text-sm font-medium text-ink shadow-xs transition hover:bg-wash
                   disabled:cursor-default disabled:opacity-70"
      >
        <svg
          viewBox="0 0 16 16"
          className={`size-4 ${running ? 'animate-spin' : ''}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        >
          <path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 1.5v3h-3" />
        </svg>
        {running ? 'Syncing…' : 'Sync now'}
      </button>
    </div>
  )
}
