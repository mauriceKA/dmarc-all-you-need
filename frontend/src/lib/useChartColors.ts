import { useEffect, useState } from 'react'

export interface ChartColors {
  pass: string
  fail: string
  quarantine: string
  info: string
  axis: string
  inkMuted: string
  surface: string
}

function resolve(): ChartColors {
  const style = getComputedStyle(document.documentElement)
  const read = (name: string) => style.getPropertyValue(name).trim()
  return {
    pass: read('--pass'),
    fail: read('--fail'),
    quarantine: read('--quarantine'),
    info: read('--info'),
    axis: read('--axis'),
    inkMuted: read('--ink-muted'),
    surface: read('--surface'),
  }
}

/**
 * Recharts writes fill/stroke as SVG *attributes*, where `var(--x)` does not
 * resolve — so charts need concrete color values. This resolves the design
 * tokens once and re-resolves when the color scheme flips.
 */
export function useChartColors(): ChartColors {
  const [colors, setColors] = useState<ChartColors>(resolve)
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const update = () => setColors(resolve())
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  return colors
}
