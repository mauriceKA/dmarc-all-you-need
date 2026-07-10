import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { Summary } from '../api/types'
import { compact, percent } from '../lib/format'
import { useChartColors, type ChartColors } from '../lib/useChartColors'
import { Card, TooltipFrame, TooltipRow } from './ui'

const SLICES = [
  { key: 'none', label: 'Delivered', color: (c: ChartColors) => c.info },
  { key: 'quarantine', label: 'Quarantined', color: (c: ChartColors) => c.quarantine },
  { key: 'reject', label: 'Rejected', color: (c: ChartColors) => c.fail },
] as const

interface PieTooltipItem {
  name?: string | number
  value?: number | string
  payload?: { color?: string }
}

function DispositionTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: PieTooltipItem[]
}) {
  if (!active || !payload?.length) return null
  const item = payload[0]
  return (
    <TooltipFrame label="Disposition">
      <TooltipRow
        color={item.payload?.color ?? 'currentColor'}
        name={String(item.name ?? '')}
        value={Number(item.value ?? 0).toLocaleString('en-US')}
      />
    </TooltipFrame>
  )
}

/** Donut of applied policy dispositions, with direct-labeled legend rows. */
export function DispositionChart({
  summary,
  reloading,
}: {
  summary: Summary
  reloading: boolean
}) {
  const colors = useChartColors()
  const total = summary.total_messages
  const data = SLICES.map((slice) => ({
    key: slice.key,
    name: slice.label,
    color: slice.color(colors),
    value: summary.dispositions[slice.key],
  })).filter((slice) => slice.value > 0)

  return (
    <Card
      title="Dispositions"
      subtitle="What receivers did with the mail"
      reloading={reloading}
    >
      {total === 0 ? (
        <p className="flex h-48 items-center justify-center text-sm text-ink-muted">
          No data in this range
        </p>
      ) : (
        <div className="flex items-center gap-6">
          <div className="relative h-48 w-48 shrink-0">
            <ResponsiveContainer>
              <PieChart>
                <Tooltip content={<DispositionTooltip />} isAnimationActive={false} />
                <Pie
                  data={data}
                  dataKey="value"
                  nameKey="name"
                  innerRadius="68%"
                  outerRadius="100%"
                  paddingAngle={data.length > 1 ? 1.5 : 0}
                  stroke={colors.surface}
                  strokeWidth={2}
                  animationDuration={250}
                  animationEasing="ease-out"
                >
                  {data.map((slice) => (
                    <Cell key={slice.key} fill={slice.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-semibold text-ink">{compact(total)}</span>
              <span className="text-xs text-ink-muted">messages</span>
            </div>
          </div>
          <ul className="min-w-0 flex-1 space-y-2.5">
            {SLICES.map((slice) => (
              <li key={slice.key} className="flex items-center gap-2 text-sm">
                <span
                  aria-hidden
                  className="size-2.5 shrink-0 rounded-sm"
                  style={{ background: slice.color(colors) }}
                />
                <span className="text-ink-secondary">{slice.label}</span>
                <span className="ml-auto font-medium text-ink tabular-nums">
                  {compact(summary.dispositions[slice.key])}
                </span>
                <span className="w-12 text-right text-xs text-ink-muted tabular-nums">
                  {percent(summary.dispositions[slice.key], total)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  )
}
