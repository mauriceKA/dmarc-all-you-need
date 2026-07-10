import { useState } from 'react'
import { RANGE_PRESETS, useFilters } from '../state/FiltersContext'

function toInputValue(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toISOString().slice(0, 10)
}

export function DateRangePicker() {
  const { rangeKey, from, to, setPreset, setCustomRange } = useFilters()
  const [customOpen, setCustomOpen] = useState(rangeKey === 'custom')

  const chip = (active: boolean) =>
    `h-9 rounded-lg px-3 text-sm font-medium transition ${
      active
        ? 'bg-ink text-surface shadow-xs'
        : 'text-ink-secondary hover:bg-wash hover:text-ink'
    }`

  return (
    <div className="flex items-center gap-1 rounded-xl border border-hairline bg-surface p-1 shadow-xs">
      {RANGE_PRESETS.map((preset) => (
        <button
          key={preset.key}
          type="button"
          className={chip(rangeKey === preset.key && !customOpen)}
          onClick={() => {
            setCustomOpen(false)
            setPreset(preset.key)
          }}
        >
          {preset.label}
        </button>
      ))}
      <button
        type="button"
        className={chip(customOpen || rangeKey === 'custom')}
        onClick={() => setCustomOpen((open) => !open)}
      >
        Custom
      </button>
      {(customOpen || rangeKey === 'custom') && (
        <span className="flex items-center gap-1 border-l border-hairline pl-2 text-sm">
          <input
            type="date"
            aria-label="From date"
            value={toInputValue(from)}
            max={toInputValue(to)}
            onChange={(event) => {
              const next = new Date(event.target.value + 'T00:00:00Z').getTime() / 1000
              if (Number.isFinite(next)) setCustomRange(next, to)
            }}
            className="h-9 rounded-lg bg-transparent px-1 text-ink-secondary outline-none
                       focus-visible:ring-2 focus-visible:ring-info/50"
          />
          <span className="text-ink-muted">–</span>
          <input
            type="date"
            aria-label="To date"
            value={toInputValue(to)}
            min={toInputValue(from)}
            onChange={(event) => {
              const next = new Date(event.target.value + 'T23:59:59Z').getTime() / 1000
              if (Number.isFinite(next)) setCustomRange(from, next)
            }}
            className="h-9 rounded-lg bg-transparent px-1 text-ink-secondary outline-none
                       focus-visible:ring-2 focus-visible:ring-info/50"
          />
        </span>
      )}
    </div>
  )
}
