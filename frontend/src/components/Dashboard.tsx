import { useApi } from '../api/client'
import type { AlignmentCombo, Summary, TimeseriesBucket } from '../api/types'
import { useFilters } from '../state/FiltersContext'
import { AlignmentChart } from './AlignmentChart'
import { ComplianceChart } from './ComplianceChart'
import { DispositionChart } from './DispositionChart'
import { SourcesTable } from './SourcesTable'
import { StatCards } from './StatCards'

const DAY = 86_400

export function Dashboard() {
  const { domain, from, to, refreshKey } = useFilters()
  const params = { domain: domain ?? undefined, from, to, r: refreshKey }
  // week buckets once a daily line would be too dense to read
  const interval = to - from > 200 * DAY ? 'week' : 'day'

  const summary = useApi<Summary>(domain ? '/api/summary' : null, params)
  const timeseries = useApi<TimeseriesBucket[]>(domain ? '/api/timeseries' : null, {
    ...params,
    interval,
  })
  const alignment = useApi<AlignmentCombo[]>(domain ? '/api/alignment' : null, params)

  return (
    <div className="space-y-4">
      {summary.data && <StatCards summary={summary.data} reloading={summary.loading} />}
      {timeseries.data && (
        <ComplianceChart data={timeseries.data} reloading={timeseries.loading} />
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        {summary.data && (
          <DispositionChart summary={summary.data} reloading={summary.loading} />
        )}
        {alignment.data && (
          <AlignmentChart data={alignment.data} reloading={alignment.loading} />
        )}
      </div>
      <SourcesTable />
    </div>
  )
}
