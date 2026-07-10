import type { Summary } from '../api/types'
import { compact, percent } from '../lib/format'

function Tile({
  label,
  value,
  sub,
  accent,
}: {
  label: string
  value: string
  sub: string
  accent?: 'pass' | 'fail'
}) {
  const valueColor =
    accent === 'pass' ? 'text-pass' : accent === 'fail' ? 'text-fail' : 'text-ink'
  return (
    <div className="rounded-2xl border border-hairline bg-surface p-5 shadow-xs">
      <p className="text-sm text-ink-muted">{label}</p>
      <p className={`mt-1 text-3xl font-semibold ${valueColor}`}>{value}</p>
      <p className="mt-1 text-xs text-ink-muted">{sub}</p>
    </div>
  )
}

export function StatCards({ summary, reloading }: { summary: Summary; reloading: boolean }) {
  const total = summary.total_messages
  // a high pass rate is the goal; color the headline rate by whether fails exist
  const rateAccent = total === 0 ? undefined : summary.dmarc_fail === 0 ? 'pass' : undefined
  return (
    <div className={`grid grid-cols-2 gap-4 xl:grid-cols-4 ${reloading ? 'reloading' : ''}`}>
      <Tile
        label="Messages"
        value={compact(total)}
        sub={`${summary.report_count.toLocaleString('en-US')} reports · ${summary.distinct_sources.toLocaleString('en-US')} sources`}
      />
      <Tile
        label="DMARC pass rate"
        value={percent(summary.dmarc_pass, total)}
        sub={`${compact(summary.dmarc_fail)} failing`}
        accent={rateAccent}
      />
      <Tile
        label="DKIM pass rate"
        value={percent(summary.dkim_pass, total)}
        sub={`${compact(summary.dkim_pass)} of ${compact(total)} messages`}
      />
      <Tile
        label="SPF pass rate"
        value={percent(summary.spf_pass, total)}
        sub={`${compact(summary.spf_pass)} of ${compact(total)} messages`}
      />
    </div>
  )
}
