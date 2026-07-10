import type { DomainInfo } from '../api/types'
import { useFilters } from '../state/FiltersContext'

export function DomainSelector({ domains }: { domains: DomainInfo[] }) {
  const { domain, setDomain } = useFilters()
  if (domains.length === 0) return null
  return (
    <label className="flex items-center gap-2">
      <span className="text-sm text-ink-muted max-sm:hidden">Domain</span>
      <select
        value={domain ?? ''}
        onChange={(event) => setDomain(event.target.value)}
        className="h-9 rounded-lg border border-hairline bg-surface px-3 text-sm font-medium
                   text-ink shadow-xs outline-none transition hover:border-ink-muted/40
                   focus-visible:ring-2 focus-visible:ring-info/50"
      >
        {domains.map((d) => (
          <option key={d.domain} value={d.domain}>
            {d.domain}
          </option>
        ))}
      </select>
    </label>
  )
}
