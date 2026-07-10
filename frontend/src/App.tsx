import { useEffect, useState } from 'react'
import { useApi } from './api/client'
import type { DomainInfo } from './api/types'
import { Dashboard } from './components/Dashboard'
import { DateRangePicker } from './components/DateRangePicker'
import { DomainSelector } from './components/DomainSelector'
import { EmptyState } from './components/EmptyState'
import { ReportsList } from './components/ReportsList'
import { SyncButton } from './components/SyncButton'
import { useFilters } from './state/FiltersContext'

type Tab = 'dashboard' | 'reports'

export default function App() {
  const { domain, setDomain, refreshKey } = useFilters()
  const [tab, setTab] = useState<Tab>('dashboard')
  const domains = useApi<DomainInfo[]>('/api/domains', { r: refreshKey })

  // pick a valid domain once the list arrives (or when the stored one vanished)
  useEffect(() => {
    const list = domains.data
    if (!list || list.length === 0) return
    if (!domain || !list.some((d) => d.domain === domain)) {
      setDomain(list[0].domain)
    }
  }, [domains.data, domain, setDomain])

  const hasData = (domains.data?.length ?? 0) > 0

  const tabClass = (active: boolean) =>
    `relative pb-2.5 text-sm font-medium transition ${
      active
        ? 'text-ink after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:rounded-full after:bg-info'
        : 'text-ink-muted hover:text-ink-secondary'
    }`

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-hairline bg-page/85 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 pt-3 sm:px-6">
          <div className="flex items-center gap-2.5">
            <img src="/shield.svg" alt="" className="size-6" />
            <h1 className="text-base font-semibold tracking-tight text-ink">
              DMARC<span className="text-ink-muted font-normal"> · all you need</span>
            </h1>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2.5">
            {hasData && <DomainSelector domains={domains.data ?? []} />}
            {hasData && <DateRangePicker />}
            {hasData && <SyncButton />}
          </div>
        </div>
        <nav className="mx-auto flex max-w-6xl gap-5 px-4 pt-2 sm:px-6" aria-label="Views">
          <button type="button" className={tabClass(tab === 'dashboard')} onClick={() => setTab('dashboard')}>
            Dashboard
          </button>
          <button type="button" className={tabClass(tab === 'reports')} onClick={() => setTab('reports')}>
            Reports
          </button>
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-5 sm:px-6">
        {!hasData && !domains.loading && <EmptyState />}
        {hasData && domain && (tab === 'dashboard' ? <Dashboard /> : <ReportsList />)}
      </main>

      <footer className="mx-auto max-w-6xl px-4 pb-6 text-xs text-ink-muted sm:px-6">
        <a
          href="https://github.com/mauriceKA/dmarc-all-you-need"
          className="hover:text-ink-secondary"
          rel="noreferrer"
        >
          dmarc-all-you-need
        </a>{' '}
        — AGPL-3.0, self-hosted.
      </footer>
    </div>
  )
}
