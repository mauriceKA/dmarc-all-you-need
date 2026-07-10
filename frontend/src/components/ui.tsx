import type { ReactNode } from 'react'

/** Chart/stat card: surface plane, hairline ring, quiet title row. */
export function Card({
  title,
  subtitle,
  right,
  reloading,
  children,
  className = '',
}: {
  title?: string
  subtitle?: string
  right?: ReactNode
  reloading?: boolean
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={`rounded-2xl border border-hairline bg-surface p-5 shadow-xs ${className}`}
    >
      {(title || right) && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p>}
          </div>
          {right}
        </header>
      )}
      <div className={reloading ? 'reloading' : undefined}>{children}</div>
    </section>
  )
}

/** Tooltip row: value leads (strong), series name follows; line key carries identity. */
export function TooltipRow({
  color,
  name,
  value,
}: {
  color: string
  name: string
  value: string
}) {
  return (
    <div className="flex items-center gap-2">
      <span aria-hidden className="h-0.5 w-3 rounded-full" style={{ background: color }} />
      <span className="font-semibold text-ink tabular-nums">{value}</span>
      <span className="text-ink-muted">{name}</span>
    </div>
  )
}

export function TooltipFrame({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-hairline bg-surface px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-medium text-ink-secondary">{label}</p>
      <div className="space-y-1">{children}</div>
    </div>
  )
}

/** Legend chip: colored mark beside text (text never wears the data color). */
export function LegendKey({
  color,
  label,
  shape = 'rect',
}: {
  color: string
  label: string
  shape?: 'rect' | 'line'
}) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-ink-secondary">
      <span
        aria-hidden
        className={shape === 'rect' ? 'size-2.5 rounded-sm' : 'h-0.5 w-3.5 rounded-full'}
        style={{ background: color }}
      />
      {label}
    </span>
  )
}
