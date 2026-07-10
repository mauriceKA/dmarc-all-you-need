import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { TimeseriesBucket } from '../api/types'
import { compact, fullDate, shortDate } from '../lib/format'
import { useChartColors, type ChartColors } from '../lib/useChartColors'
import { Card, LegendKey, TooltipFrame, TooltipRow } from './ui'

interface TooltipPayloadItem {
  dataKey?: string | number
  value?: number | string
}

function ComplianceTooltip({
  active,
  payload,
  label,
  colors,
}: {
  active?: boolean
  payload?: TooltipPayloadItem[]
  label?: number | string
  colors: ChartColors
}) {
  if (!active || !payload?.length || typeof label !== 'number') return null
  const get = (key: string) =>
    Number(payload.find((item) => item.dataKey === key)?.value ?? 0)
  return (
    <TooltipFrame label={fullDate(label)}>
      <TooltipRow color={colors.pass} name="pass" value={get('pass').toLocaleString('en-US')} />
      <TooltipRow color={colors.fail} name="fail" value={get('fail').toLocaleString('en-US')} />
    </TooltipFrame>
  )
}

/** Stacked area: DMARC pass vs fail volume over time. */
export function ComplianceChart({
  data,
  reloading,
}: {
  data: TimeseriesBucket[]
  reloading: boolean
}) {
  const colors = useChartColors()
  return (
    <Card
      title="Compliance over time"
      subtitle="Messages passing vs failing DMARC, per day"
      reloading={reloading}
      right={
        <div className="flex gap-3">
          <LegendKey color={colors.pass} label="Pass" />
          <LegendKey color={colors.fail} label="Fail" />
        </div>
      }
    >
      <div className="h-72">
        {data.length === 0 ? (
          <p className="flex h-full items-center justify-center text-sm text-ink-muted">
            No data in this range
          </p>
        ) : (
          <ResponsiveContainer>
            <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} strokeWidth={1} />
              <XAxis
                dataKey="bucket"
                type="number"
                scale="time"
                domain={['dataMin', 'dataMax']}
                tickFormatter={shortDate}
                tickLine={false}
                axisLine={{ stroke: colors.axis }}
                tick={{ fill: colors.inkMuted, fontSize: 11 }}
                tickMargin={8}
                minTickGap={40}
              />
              <YAxis
                tickFormatter={compact}
                tickLine={false}
                axisLine={false}
                tick={{ fill: colors.inkMuted, fontSize: 11 }}
                width={44}
              />
              <Tooltip
                cursor={{ stroke: colors.axis, strokeWidth: 1 }}
                content={<ComplianceTooltip colors={colors} />}
                isAnimationActive={false}
              />
              <Area
                type="monotone"
                dataKey="pass"
                stackId="dmarc"
                stroke={colors.pass}
                strokeWidth={2}
                fill={colors.pass}
                fillOpacity={0.1}
                animationDuration={250}
                animationEasing="ease-out"
              />
              <Area
                type="monotone"
                dataKey="fail"
                stackId="dmarc"
                stroke={colors.fail}
                strokeWidth={2}
                fill={colors.fail}
                fillOpacity={0.1}
                animationDuration={250}
                animationEasing="ease-out"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  )
}
