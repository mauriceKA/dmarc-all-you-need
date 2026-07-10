import { SyncButton } from './SyncButton'

/** Shown while the database has no domains yet (first run). */
export function EmptyState() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="max-w-md rounded-2xl border border-hairline bg-surface p-8 text-center shadow-xs">
        <svg viewBox="0 0 32 32" className="mx-auto size-12" aria-hidden>
          <path
            d="M16 2l11 4v9c0 7.2-4.7 12.8-11 15C9.7 27.8 5 22.2 5 15V6l11-4z"
            fill="var(--info)"
            opacity="0.15"
          />
          <path
            d="M16 2l11 4v9c0 7.2-4.7 12.8-11 15C9.7 27.8 5 22.2 5 15V6l11-4z"
            fill="none"
            stroke="var(--info)"
            strokeWidth="1.5"
          />
          <path
            d="M10.5 15.5l4 4 7-8"
            fill="none"
            stroke="var(--info)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <h2 className="mt-4 text-lg font-semibold text-ink">No reports yet</h2>
        <p className="mt-2 text-sm text-ink-secondary">
          Reports appear here once the mailbox sync finds DMARC aggregate reports. Syncs run
          automatically on the configured interval — or start one now.
        </p>
        <div className="mt-5 flex justify-center">
          <SyncButton />
        </div>
      </div>
    </div>
  )
}
