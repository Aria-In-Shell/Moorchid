import { line as d3Line, curveCatmullRom } from 'd3-shape'
import type { Entry } from '../types'
import { mapMood, nodeRadius, valenceForMood } from './moodMapping'

export interface CurvePoint {
  entry: Entry
  count: number
  x: number
  y: number
  r: number
  color: string
  glow: string
  valence: number
}

export interface CurveLayout {
  width: number
  height: number
  padX: number
  padTop: number
  padBottom: number
  points: CurvePoint[]
  path: string
}

export function parseStamp(raw: string): number {
  const [datePart, timePart = '00:00:00'] = raw.split(' ')
  const [y, m, d] = datePart.split('-').map(Number)
  const [hh, mm, ss] = timePart.split(':').map(Number)
  return new Date(y, (m || 1) - 1, d || 1, hh || 0, mm || 0, ss || 0).getTime()
}

export function sortEntries(entries: Entry[]): Entry[] {
  return [...entries].sort((a, b) => {
    const dt = parseStamp(a.created_at) - parseStamp(b.created_at)
    return dt !== 0 ? dt : a.id - b.id
  })
}

export function layoutCurve(
  entries: Entry[],
  width: number,
  height: number,
): CurveLayout {
  const padX = Math.min(58, width * 0.13)
  const padTop = Math.min(72, height * 0.25)
  const padBottom = Math.min(48, height * 0.18)
  const days = new Map<string, Entry[]>()
  for (const entry of sortEntries(entries)) {
    const day = entry.created_at.slice(0, 10)
    const group = days.get(day)
    if (group) group.push(entry)
    else days.set(day, [entry])
  }
  const sorted = [...days.values()]
  const innerW = Math.max(1, width - padX * 2)
  const innerH = Math.max(1, height - padTop - padBottom)
  const n = sorted.length

  // ISO calendar days are equally long on this axis, including DST transitions.
  const dates = [...days.keys()].map(day => Date.parse(day + 'T00:00:00Z'))
  const span = dates[n - 1] - dates[0]
  const points: CurvePoint[] = sorted.map((group, index) => {
    const entry = group[group.length - 1]
    const mood = mapMood(entry.emotion)
    const valence = group.reduce((sum, item) => sum + valenceForMood(item.emotion, item.valence), 0) / group.length
    const x = padX + innerW * (n === 1 ? 0.5 : (dates[index] - dates[0]) / span)
    const y = padTop + ((1 - valence) / 2) * innerH
    return {
      entry,
      count: group.length,
      x,
      y,
      r: nodeRadius(entry.intensity),
      color: mood.color,
      glow: mood.glow,
      valence,
    }
  })

  const generator = d3Line<CurvePoint>()
    .x((d) => d.x)
    .y((d) => d.y)
    .curve(curveCatmullRom.alpha(0.65))

  return {
    width,
    height,
    padX,
    padTop,
    padBottom,
    points,
    path: n >= 2 ? generator(points) ?? '' : '',
  }
}

export function gradientStops(points: CurvePoint[]): Array<{ offset: string; color: string }> {
  if (points.length === 0) return []
  if (points.length === 1) {
    return [
      { offset: '0%', color: points[0].color },
      { offset: '100%', color: points[0].color },
    ]
  }
  const start = points[0].x
  const width = points[points.length - 1].x - start
  return points.map(point => ({
    offset: `${((point.x - start) / width) * 100}%`,
    color: point.color,
  }))
}
