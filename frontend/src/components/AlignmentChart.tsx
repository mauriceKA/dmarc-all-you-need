import type { AlignmentCombo } from '../api/types'
import { compact, percent } from '../lib/format'
import { Card } from './ui'

const COMBOS = [
  { dkim: 'pass', spf: 'pass', label: 'DKIM ✓ · SPF ✓' },
  { dkim: 'pass', spf: 'fail', label: 'DKIM ✓ · SPF ✗' },
  { dkim: 'fail', spf: 'pass', label: 'DKIM ✗ · SPF ✓' },
  { dkim: 'fail', spf: 'fail', label: 'DKIM ✗ · SPF ✗' },
] as const

/**
 * DKIM×SPF outcome combos as thin horizontal bars. Polarity coloring:
 * any aligned pass keeps DMARC green; both failing is the red row.
 */
export function AlignmentChart({
  data,
  reloading,
}: {
  data: AlignmentCombo[]
  reloading: boolean
}) {
  const counts = new Map(data.map((combo) => [`${combo.dkim}/${combo.spf}`, combo.count]))
  const total = data.reduce((sum, combo) => sum + combo.count, 0)
  const max = Math.max(1, ...data.map((combo) => combo.count))

  return (
    <Card
      title="Authentication alignment"
      subtitle="DKIM and SPF results behind the DMARC verdict"
      reloading={reloading}
    >
      {total === 0 ? (
        <p className="flex h-48 items-center justify-center text-sm text-ink-muted">
          No data in this range
        </p>
      ) : (
        <ul className="space-y-4 pt-1">
          {COMBOS.map((combo) => {
            const count = counts.get(`${combo.dkim}/${combo.spf}`) ?? 0
            const passing = combo.dkim === 'pass' || combo.spf === 'pass'
            return (
              <li key={combo.label} title={`${count.toLocaleString('en-US')} messages`}>
                <div className="mb-1 flex items-baseline justify-between text-sm">
                  <span className="text-ink-secondary">{combo.label}</span>
                  <span className="font-medium text-ink tabular-nums">
                    {compact(count)}
                    <span className="ml-1.5 text-xs font-normal text-ink-muted">
                      {percent(count, total)}
                    </span>
                  </span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-wash">
                  <div
                    className="h-full rounded-r-[4px] transition-[width] duration-300 ease-out"
                    style={{
                      width: `${(count / max) * 100}%`,
                      background: passing ? 'var(--pass)' : 'var(--fail)',
                    }}
                  />
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}
