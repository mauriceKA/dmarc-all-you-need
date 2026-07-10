import { useEffect } from 'react'
import { useApi } from '../api/client'
import type { ReportDetail as ReportDetailData, ReportRecord } from '../api/types'
import { fullDate, percent } from '../lib/format'
import { TooltipFrame } from './ui'

function PolicyChip({ label, value }: { label: string; value: string | number | null }) {
  if (value === null || value === '') return null
  return (
    <span className="rounded-lg bg-wash px-2 py-1 text-xs text-ink-secondary">
      {label}=<span className="font-medium text-ink">{value}</span>
    </span>
  )
}

function ResultBadge({ result }: { result: string }) {
  const color =
    result === 'pass'
      ? 'text-pass'
      : result === 'fail' || result === 'permerror'
        ? 'text-fail'
        : 'text-quarantine'
  return <span className={`font-medium ${color}`}>{result}</span>
}

function RecordCard({ record }: { record: ReportRecord }) {
  return (
    <div className="rounded-xl border border-hairline p-3 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-mono text-[13px] text-ink">{record.source_ip}</span>
        <span className="text-xs text-ink-muted">
          {record.count.toLocaleString('en-US')} message{record.count === 1 ? '' : 's'} ·{' '}
          <ResultBadge result={record.dmarc_pass ? 'pass' : 'fail'} /> · {record.disposition}
        </span>
      </div>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        <dt className="text-ink-muted">Evaluated</dt>
        <dd className="text-ink-secondary">
          DKIM <ResultBadge result={record.eval_dkim} /> · SPF{' '}
          <ResultBadge result={record.eval_spf} />
        </dd>
        {record.header_from && (
          <>
            <dt className="text-ink-muted">From</dt>
            <dd className="truncate text-ink-secondary">{record.header_from}</dd>
          </>
        )}
        {record.envelope_from && (
          <>
            <dt className="text-ink-muted">Envelope</dt>
            <dd className="truncate text-ink-secondary">{record.envelope_from}</dd>
          </>
        )}
        {record.reason_type && (
          <>
            <dt className="text-ink-muted">Reason</dt>
            <dd className="text-ink-secondary">
              {record.reason_type}
              {record.reason_comment ? ` — ${record.reason_comment}` : ''}
            </dd>
          </>
        )}
        {record.auth_results.length > 0 && (
          <>
            <dt className="text-ink-muted">Raw auth</dt>
            <dd className="space-y-0.5 text-ink-secondary">
              {record.auth_results.map((auth, index) => (
                <p key={index} className="truncate">
                  {auth.auth_type}
                  {auth.domain ? ` ${auth.domain}` : ''}
                  {auth.selector ? ` (s=${auth.selector})` : ''}
                  {auth.scope ? ` (${auth.scope})` : ''}: <ResultBadge result={auth.result} />
                </p>
              ))}
            </dd>
          </>
        )}
      </dl>
    </div>
  )
}

/** Slide-over panel with one report's published policy and records. */
export function ReportDetail({ reportId, onClose }: { reportId: number; onClose: () => void }) {
  const { data, loading, error } = useApi<ReportDetailData>(`/api/reports/${reportId}`)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const messageTotal = data?.records.reduce((sum, record) => sum + record.count, 0) ?? 0
  const passTotal =
    data?.records.reduce((sum, record) => sum + (record.dmarc_pass ? record.count : 0), 0) ?? 0

  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label="Report detail">
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/30 backdrop-blur-[1px] transition-opacity"
      />
      <aside
        className="absolute inset-y-0 right-0 flex w-full max-w-xl flex-col overflow-y-auto
                   border-l border-hairline bg-page p-6 shadow-2xl
                   max-sm:max-w-full animate-[slideIn_200ms_ease-out]"
      >
        <style>{`@keyframes slideIn { from { transform: translateX(24px); opacity: 0 } to { transform: none; opacity: 1 } }`}</style>
        <header className="mb-4 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold text-ink">{data?.org_name ?? '…'}</h2>
            {data && (
              <p className="mt-0.5 text-xs text-ink-muted">
                {fullDate(data.date_begin)} – {fullDate(data.date_end)} · report{' '}
                <span className="break-all font-mono">{data.report_id}</span>
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            className="rounded-lg p-1.5 text-ink-muted transition hover:bg-wash hover:text-ink"
          >
            <svg viewBox="0 0 16 16" className="size-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <path d="M4 4l8 8M12 4l-8 8" />
            </svg>
          </button>
        </header>

        {error && <p className="text-sm text-fail">Failed to load report: {error}</p>}
        {loading && !data && <p className="text-sm text-ink-muted">Loading…</p>}

        {data && (
          <div className="space-y-5">
            <TooltipFrame label="Published policy">
              <div className="flex flex-wrap gap-1.5 pt-1">
                <PolicyChip label="p" value={data.policy_p} />
                <PolicyChip label="sp" value={data.policy_sp} />
                <PolicyChip label="pct" value={data.policy_pct} />
                <PolicyChip label="adkim" value={data.policy_adkim} />
                <PolicyChip label="aspf" value={data.policy_aspf} />
              </div>
            </TooltipFrame>

            <p className="text-sm text-ink-secondary">
              <span className="font-semibold text-ink">
                {messageTotal.toLocaleString('en-US')}
              </span>{' '}
              messages, <span className="font-medium text-pass">{percent(passTotal, messageTotal)}</span>{' '}
              passing DMARC, from {data.records.length} source
              {data.records.length === 1 ? '' : 's'}
              {data.org_email ? (
                <>
                  {' '}
                  · reported by <span className="break-all">{data.org_email}</span>
                </>
              ) : null}
            </p>

            <div className="space-y-2.5">
              {data.records.map((record) => (
                <RecordCard key={record.id} record={record} />
              ))}
            </div>
          </div>
        )}
      </aside>
    </div>
  )
}
