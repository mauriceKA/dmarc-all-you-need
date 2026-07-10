import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

const DAY = 86_400

export const RANGE_PRESETS = [
  { key: '7d', label: '7d', days: 7 },
  { key: '30d', label: '30d', days: 30 },
  { key: '90d', label: '90d', days: 90 },
  { key: '1y', label: '1y', days: 365 },
] as const

export type RangeKey = (typeof RANGE_PRESETS)[number]['key'] | 'custom'

interface Filters {
  domain: string | null
  from: number
  to: number
  rangeKey: RangeKey
  /** bumped after a sync finishes so every consumer refetches */
  refreshKey: number
  setDomain: (domain: string) => void
  setPreset: (key: Exclude<RangeKey, 'custom'>) => void
  setCustomRange: (from: number, to: number) => void
  bumpRefresh: () => void
}

const FiltersContext = createContext<Filters | null>(null)

function presetRange(days: number): { from: number; to: number } {
  const now = Math.floor(Date.now() / 1000)
  // include today fully; start at midnight `days` ago so buckets align
  const to = now
  const from = (Math.floor(now / DAY) - days) * DAY
  return { from, to }
}

const STORED_DOMAIN_KEY = 'dmarcayn.domain'
const STORED_RANGE_KEY = 'dmarcayn.range'

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [domain, setDomainState] = useState<string | null>(
    () => localStorage.getItem(STORED_DOMAIN_KEY),
  )
  const [rangeKey, setRangeKey] = useState<RangeKey>(() => {
    const stored = localStorage.getItem(STORED_RANGE_KEY)
    return RANGE_PRESETS.some((p) => p.key === stored) ? (stored as RangeKey) : '30d'
  })
  const [customRange, setCustomRangeState] = useState<{ from: number; to: number } | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const setDomain = useCallback((next: string) => {
    localStorage.setItem(STORED_DOMAIN_KEY, next)
    setDomainState(next)
  }, [])

  const setPreset = useCallback((key: Exclude<RangeKey, 'custom'>) => {
    localStorage.setItem(STORED_RANGE_KEY, key)
    setCustomRangeState(null)
    setRangeKey(key)
  }, [])

  const setCustomRange = useCallback((from: number, to: number) => {
    setCustomRangeState({ from, to })
    setRangeKey('custom')
  }, [])

  const bumpRefresh = useCallback(() => setRefreshKey((k) => k + 1), [])

  const value = useMemo<Filters>(() => {
    const preset = RANGE_PRESETS.find((p) => p.key === rangeKey)
    const range = rangeKey === 'custom' && customRange ? customRange : presetRange(preset?.days ?? 30)
    return {
      domain,
      from: range.from,
      to: range.to,
      rangeKey,
      refreshKey,
      setDomain,
      setPreset,
      setCustomRange,
      bumpRefresh,
    }
  }, [domain, rangeKey, customRange, refreshKey, setDomain, setPreset, setCustomRange, bumpRefresh])

  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>
}

export function useFilters(): Filters {
  const context = useContext(FiltersContext)
  if (!context) throw new Error('useFilters outside FiltersProvider')
  return context
}
