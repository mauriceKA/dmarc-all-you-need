import { useState } from 'react'
import { useApi } from '../api/client'
import type { ReportsPage } from '../api/types'
import { compact, fullDate } from '../lib/format'
import { useFilters } from '../state/FiltersContext'
import { ReportDetail } from './ReportDetail'
import { Card } from './ui'

const PAGE_SIZE = 20

export function ReportsList() {
  const { domain, from, to, refreshKey } = useFilters()
  const [page, setPage] = useState(0)
  const [openReport, setOpenReport] = useState<number | null>(null)
  const { data, loading } = useApi<ReportsPage>(domain ? '/api/reports' : null, {
    domain: domain ?? undefined,
    from,
    to,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    r: refreshKey,
  })

  const rows = data?.reports ?? []
  const total = data?.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  if (page >= pageCount && page !== 0) setPage(0)

  return (
    <>
      <Card
        title="Aggregate reports"
        subtitle={`${total.toLocaleString('en-US')} reports in range`}
        reloading={loading}
      >
        {rows.length === 0 ? (
          <p className="flex h-24 items-center justify-center text-sm text-ink-muted">
            No reports in this range
          </p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-hairline text-left text-xs text-ink-muted">
                    <th className="pb-2 pr-4 font-medium">Reporter</th>
                    <th className="pb-2 pr-4 font-medium max-md:hidden">Report ID</th>
                    <th className="pb-2 pr-4 font-medium">Period</th>
                    <th className="pb-2 pr-4 text-right font-medium">Messages</th>
                    <th className="pb-2 text-right font-medium">Failing</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((report) => (
                    <tr
                      key={report.id}
                      onClick={() => setOpenReport(report.id)}
                      className="cursor-pointer border-b border-hairline/60 transition-colors
                                 last:border-0 hover:bg-wash"
                    >
                      <td className="py-2.5 pr-4 font-medium text-ink">{report.org_name}</td>
                      <td className="max-w-56 truncate py-2.5 pr-4 font-mono text-xs text-ink-muted max-md:hidden">
                        {report.report_id}
                      </td>
                      <td className="py-2.5 pr-4 text-ink-secondary">
                        {fullDate(report.date_begin)}
                        {fullDate(report.date_end) !== fullDate(report.date_begin)
                          ? ` – ${fullDate(report.date_end)}`
                          : ''}
                      </td>
                      <td className="py-2.5 pr-4 text-right text-ink tabular-nums">
                        {compact(report.message_count)}
                      </td>
                      <td
                        className={`py-2.5 text-right tabular-nums ${
                          report.fail_count > 0 ? 'font-medium text-fail' : 'text-ink-muted'
                        }`}
                      >
                        {report.fail_count > 0 ? compact(report.fail_count) : '–'}
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
      {openReport !== null && (
        <ReportDetail reportId={openReport} onClose={() => setOpenReport(null)} />
      )}
    </>
  )
}
