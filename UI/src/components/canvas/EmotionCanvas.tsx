import { useEffect, useMemo, useRef, useState } from 'react'
import type { Entry } from '../../types'
import { gradientStops, layoutCurve } from '../../utils/emotionCurve'
import { formatDateLabel } from '../../utils/formatTime'

interface EmotionCanvasProps {
  entries: Entry[]
  selectedId: number | null
  onSelect: (entry: Entry) => void
  preview?: boolean
}

export default function EmotionCanvas({
  entries,
  selectedId,
  onSelect,
  preview = false,
}: EmotionCanvasProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const pathRef = useRef<SVGPathElement>(null)
  const [size, setSize] = useState({ width: 1100, height: 560 })
  const [pathLength, setPathLength] = useState(1200)

  useEffect(() => {
    const el = hostRef.current
    if (!el) return
    const obs = new ResizeObserver((rows) => {
      const rect = rows[0]?.contentRect
      if (!rect) return
      setSize({
        width: Math.max(1, rect.width),
        height: Math.max(1, rect.height),
      })
    })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  const layout = useMemo(
    () => layoutCurve(entries, size.width, size.height),
    [entries, size.height, size.width],
  )

  useEffect(() => {
    const length = pathRef.current?.getTotalLength()
    if (length && Number.isFinite(length)) setPathLength(length)
  }, [layout.path])

  const stops = gradientStops(layout.points)
  const selected = layout.points.find((p) => p.entry.id === selectedId)

  return (
    <div ref={hostRef} className="relative h-full w-full overflow-hidden">
      <div className="aurora-blob pointer-events-none absolute -left-24 top-10 h-72 w-72 rounded-full bg-[#5eead4]/10 blur-3xl" />
      <div className="aurora-blob pointer-events-none absolute right-0 top-24 h-80 w-80 rounded-full bg-[#fb7185]/10 blur-[90px]" style={{ animationDelay: '-6s' }} />
      <div className="aurora-blob pointer-events-none absolute bottom-10 left-1/3 h-64 w-64 rounded-full bg-[#f5c15a]/8 blur-[80px]" style={{ animationDelay: '-11s' }} />

      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        preserveAspectRatio="xMidYMid meet"
        className="absolute inset-0"
      >
        <defs>
          <linearGradient id="ecg-stroke" gradientUnits="userSpaceOnUse" x1={layout.padX} y1="0" x2={layout.width - layout.padX} y2="0">
            {stops.map((stop) => (
              <stop key={stop.offset} offset={stop.offset} stopColor={stop.color} />
            ))}
          </linearGradient>
          <linearGradient id="ecg-fill" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="rgba(94,234,212,0.16)" />
            <stop offset="100%" stopColor="rgba(11,12,15,0)" />
          </linearGradient>
          <filter id="ecg-glow" x="-20%" y="-40%" width="140%" height="180%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <line
          x1={layout.padX}
          x2={layout.width - layout.padX}
          y1={layout.height / 2}
          y2={layout.height / 2}
          stroke="rgba(255,255,255,0.06)"
          strokeDasharray="4 10"
        />
        <text x={22} y={layout.padTop + 4} fill="#8b909a" fontSize="11" letterSpacing="0.18em">
          HIGH
        </text>
        <text x={22} y={layout.height - layout.padBottom} fill="#8b909a" fontSize="11" letterSpacing="0.18em">
          LOW
        </text>

        {layout.path && (
          <>
            <path
              d={layout.path}
              fill="none"
              stroke="url(#ecg-stroke)"
              strokeWidth="10"
              opacity="0.18"
              filter="url(#ecg-glow)"
            />
            <path
              ref={pathRef}
              d={layout.path}
              fill="none"
              stroke="url(#ecg-stroke)"
              strokeWidth="2.4"
              strokeLinecap="round"
              className="ecg-draw"
              style={{ ['--path-length' as string]: pathLength }}
            />
            <path
              d={layout.path}
              fill="none"
              stroke="url(#ecg-stroke)"
              strokeWidth="2"
              strokeLinecap="round"
              className="ecg-flow"
              opacity="0.85"
              filter="url(#ecg-glow)"
            />
          </>
        )}

        {layout.points.map((point, index) => {
          const active = point.entry.id === selectedId
          const label = formatDateLabel(point.entry.created_at)
          return (
            <g
              key={point.entry.id}
              className="ecg-node cursor-pointer"
              style={{ animationDelay: `${Math.min(index, 4) * 0.04}s` }}
              role="button"
              tabIndex={0}
              aria-label={label.full + '，' + point.count + ' 条记录'}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(point.entry) }
              }}
              onClick={() => onSelect(point.entry)}
            >
              {active && (
                <circle
                  cx={point.x}
                  cy={point.y}
                  r={point.r + 6}
                  fill={point.color}
                  opacity="0.25"
                  className="ecg-pulse"
                />
              )}
              <circle
                cx={point.x}
                cy={point.y}
                r={active ? point.r + 2.5 : point.r}
                fill={point.color}
                stroke="rgba(11,12,15,0.85)"
                strokeWidth="2"
                filter="url(#ecg-glow)"
              />
              <text
                x={point.x}
                y={point.y + point.r + 18}
                textAnchor="middle"
                fill={active ? '#eceef2' : '#8b909a'}
                fontSize="10"
              >
                {(active || layout.points.length < 8 || index % Math.ceil(layout.points.length / 6) === 0) && (label.weekday === '今天' || label.weekday === '昨天' ? label.weekday : label.day)}
              </text>
            </g>
          )
        })}
      </svg>

      {selected && (
        <div className="pointer-events-none absolute left-8 top-8 max-w-sm">
          <p className="text-[11px] tracking-[0.22em] text-[#8b909a] uppercase">
            {formatDateLabel(selected.entry.created_at).full}
          </p>
          <p className="serif mt-2 text-2xl text-white">
            {selected.count} 条记录
          </p>
        </div>
      )}

      {preview && (
        <div className="absolute right-8 top-8 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] tracking-[0.16em] text-[#8b909a]">
          示例轨迹
        </div>
      )}
    </div>
  )
}
