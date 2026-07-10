/** Shared formatting helpers. */

export function compact(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(value >= 10_000_000 ? 0 : 1)}M`
  if (value >= 10_000) return `${(value / 1_000).toFixed(value >= 100_000 ? 0 : 1)}K`
  return value.toLocaleString('en-US')
}

export function percent(part: number, whole: number): string {
  if (whole === 0) return '–'
  const ratio = (part / whole) * 100
  if (ratio > 0 && ratio < 0.1) return '<0.1%'
  if (ratio > 99.9 && ratio < 100) return '>99.9%'
  return `${ratio.toFixed(ratio === 100 || ratio === 0 ? 0 : 1)}%`
}

export function shortDate(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

export function fullDate(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function dateTime(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function relativeTime(epochSeconds: number): string {
  const delta = Math.floor(Date.now() / 1000) - epochSeconds
  if (delta < 60) return 'just now'
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`
  if (delta < 86_400) return `${Math.floor(delta / 3600)}h ago`
  return `${Math.floor(delta / 86_400)}d ago`
}
