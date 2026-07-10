import { useState } from 'react'
import { useApi } from '../api/client'
import type { SourcesPage } from '../api/types'
import { compact, percent, shortDate } from '../lib/format'
import { useFilters } from '../state/FiltersContext'
import { Card, LegendKey } from './ui'

const PAGE_SIZE = 12

/** Inline two-segment ratio bar (pass/fail) with a 2px surface gap. */
function RatioBar({ pass, fail }: { pass: number; fail: number }) {
  const total = pass + fail
  if (total === 0) return null
  return (
    <div className="flex h-1.5 w-full gap-[2px] overflow-hidden rounded-full">
      {pass > 0 && (
        <div style={{ width: `${(pass / total) * 100}%`, background: 'var(--pass)' }} />
      )}
      {fail > 0 && (
        <div style={{ width: `${(fail / total) * 100}%`, background: 'var(--fail)' }} />
      )}
    </div>
  )
}

export function SourcesTable() {
  const { domain, from, to, refreshKey } = useFilters()
  const [page, setPage] = useState(0)
  const { data, loading } = useApi<SourcesPage>(domain ? '/api/sources' : null, {
    domain: domain ?? undefined,
    from,
    to,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    r: refreshKey,
  })

  const rows = data?.sources ?? []
  const totalRows = data?.total_rows ?? 0
  const pageCount = Math.max(1, Math.ceil(totalRows / PAGE_SIZE))
  if (page >= pageCount && page !== 0) setPage(0)

  return (
    <Card
      title="Sending sources"
      subtitle={`${totalRows.toLocaleString('en-US')} source IPs in range`}
      reloading={loading}
      right={
        <div className="flex gap-3">
          <LegendKey color="var(--pass)" label="Pass" />
          <LegendKey color="var(--fail)" label="Fail" />
        </div>
      }
    >
      {rows.length === 0 ? (
        <p className="flex h-24 items-center justify-center text-sm text-ink-muted">
          No data in this range
        </p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-hairline text-left text-xs text-ink-muted">
                  <th className="pb-2 pr-4 font-medium">Source IP</th>
                  <th className="pb-2 pr-4 text-right font-medium">Messages</th>
                  <th className="w-1/3 pb-2 pr-4 font-medium">Pass / fail</th>
                  <th className="pb-2 pr-4 text-right font-medium">Pass rate</th>
                  <th className="pb-2 pr-4 text-right font-medium max-md:hidden">Quarantined</th>
                  <th className="pb-2 pr-4 text-right font-medium max-md:hidden">Rejected</th>
                  <th className="pb-2 text-right font-medium max-sm:hidden">Last seen</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.source_ip}
                    className="border-b border-hairline/60 transition-colors last:border-0 hover:bg-wash"
                  >
                    <td className="py-2.5 pr-4 font-mono text-[13px] text-ink">
                      {row.source_ip}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-medium text-ink tabular-nums">
                      {compact(row.total)}
                    </td>
                    <td className="py-2.5 pr-4">
                      <RatioBar pass={row.pass} fail={row.fail} />
                    </td>
                    <td className="py-2.5 pr-4 text-right text-ink-secondary tabular-nums">
                      {percent(row.pass, row.total)}
                    </td>
                    <td className="py-2.5 pr-4 text-right text-ink-secondary tabular-nums max-md:hidden">
                      {row.quarantine > 0 ? compact(row.quarantine) : '–'}
                    </td>
                    <td className="py-2.5 pr-4 text-right text-ink-secondary tabular-nums max-md:hidden">
                      {row.reject > 0 ? compact(row.reject) : '–'}
                    </td>
                    <td className="py-2.5 text-right text-ink-muted tabular-nums max-sm:hidden">
                      {shortDate(row.last_seen)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {pageCount > 1 && (
            <footer className="mt-3 flex items-center justify-end gap-2 text-sm">
              <span className="text-xs text-ink-muted">
                Page {page + 1} of {pageCount}
              </span>
              <button
                type="button"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
                className="rounded-lg border border-hairline px-2.5 py-1 text-ink-secondary
                           transition hover:bg-wash disabled:opacity-40"
              >
                ←
              </button>
              <button
                type="button"
                disabled={page + 1 >= pageCount}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-hairline px-2.5 py-1 text-ink-secondary
                           transition hover:bg-wash disabled:opacity-40"
              >
                →
              </button>
            </footer>
          )}
        </>
      )}
    </Card>
  )
}
