/**
 * EmotionCalendar.tsx
 *
 * P1 — Minimalist high-end magazine aesthetic.
 *
 * Design philosophy:
 *  - No borders, no boxes, no mechanical circles
 *  - Bare date numbers for empty days — just a whisper of type
 *  - Soft morandi-colour circles with hand-drawn minimal SVG faces for entry days
 *  - Playfair Display italic for month, Caveat for year
 *  - Ultra-wide tracking for weekday headers
 *
 * MinimalMoodIcon design spec:
 *  - Warm morandi backgrounds (no blue/purple/gray washes)
 *  - Pure dark/charcoal line work for facial features
 *  - stroke="currentColor", strokeWidth="1.5", strokeLinecap="round" throughout
 */

import { useState, useCallback, useMemo } from 'react'
import { mapMood, type MoodMapping, type MoodType } from '../utils/moodMapping'
import type { Entry } from '../types'

// ─── Palette ─────────────────────────────────────────────────────────────────

const C = {
  card:     '#FAF7F0',
  ink:      '#2A3328',
  inkMid:   '#5A6B5E',
  inkLight: '#8A9E90',
  terra:    '#B87355',
  border:   '#D6CEBF',
  borderL:  '#E4DDD0',
  moss:     '#3A5247',
  mossMid:  '#4E6B5C',
  mossLight:'#7A9B8A',
  shadow:   'rgba(58,82,71,0.10)',
}

// ─── Mood gradient palette (P2 spec) ──────────────────────────────────────────
// Each mood gets a unique id for <linearGradient> + top-light / bottom-dark stops.

interface MoodGradient {
  id: string
  light: string   // top-right highlight
  dark:  string   // bottom-left shadow
}

export const MOOD_GRADIENTS: Record<MoodType, MoodGradient> = {
  happy:   { id: 'grad-joy',     light: '#FF9EAA', dark: '#FF6B8B' },
  calm:    { id: 'grad-good',    light: '#FFD2A5', dark: '#FFA07A' },
  neutral: { id: 'grad-neutral', light: '#FFE99A', dark: '#F2C94C' },
  low:     { id: 'grad-low',     light: '#FFC078', dark: '#F59F00' },
  anxious: { id: 'grad-anxious', light: '#FF7A59', dark: '#E03131' },
}

const INK = '#1A1A1A'

// ─── MinimalMoodIcon ───────────────────────────────────────────────────────────
/**
 * Self-contained minimal face — matches P2 spec.
 * - 24×24 viewBox
 * - Gradient-filled background circle (top-right light → bottom-left dark)
 * - Solid dot eyes + line/path mouth (all #1A1A1A)
 *
 * Joy face uses a fully-filled semi-circle "big laugh" mouth.
 * Anxious face adds two angled eyebrows over the eyes.
 */
function MinimalMoodIcon({ type, size = 34 }: { type: MoodType; size?: number }) {
  const grad = MOOD_GRADIENTS[type] ?? MOOD_GRADIENTS.neutral

  const base = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    style: { display: 'block', flexShrink: 0 },
  }

  if (type === 'happy') {
    // Joy — eyes at y=9, big semi-circle open mouth (filled)
    return (
      <svg {...base}>
        <defs>
          <linearGradient id={grad.id} x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%"   stopColor="#FFFFFF" stopOpacity="0.35" />
            <stop offset="35%"  stopColor={grad.light} />
            <stop offset="100%" stopColor={grad.dark} />
          </linearGradient>
        </defs>
        <circle cx="12" cy="12" r="11" fill={`url(#${grad.id})`} />
        <circle cx="8"  cy="9"  r="1.5" fill={INK} />
        <circle cx="16" cy="9"  r="1.5" fill={INK} />
        <path d="M7 12 C7 17, 17 17, 17 12 Z" fill={INK} />
      </svg>
    )
  }

  if (type === 'calm') {
    // Good — eyes at y=10, gentle arc smile
    return (
      <svg {...base}>
        <defs>
          <linearGradient id={grad.id} x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%"   stopColor="#FFFFFF" stopOpacity="0.35" />
            <stop offset="35%"  stopColor={grad.light} />
            <stop offset="100%" stopColor={grad.dark} />
          </linearGradient>
        </defs>
        <circle cx="12" cy="12" r="11" fill={`url(#${grad.id})`} />
        <circle cx="8"  cy="10" r="1.5" fill={INK} />
        <circle cx="16" cy="10" r="1.5" fill={INK} />
        <path
          d="M8 13 Q12 17 16 13"
          stroke={INK}
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    )
  }

  if (type === 'neutral') {
    // Neutral — eyes at y=10, perfectly horizontal flat mouth
    return (
      <svg {...base}>
        <defs>
          <linearGradient id={grad.id} x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%"   stopColor="#FFFFFF" stopOpacity="0.35" />
            <stop offset="35%"  stopColor={grad.light} />
            <stop offset="100%" stopColor={grad.dark} />
          </linearGradient>
        </defs>
        <circle cx="12" cy="12" r="11" fill={`url(#${grad.id})`} />
        <circle cx="8"  cy="10" r="1.5" fill={INK} />
        <circle cx="16" cy="10" r="1.5" fill={INK} />
        <line
          x1="8" y1="14" x2="16" y2="14"
          stroke={INK}
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    )
  }

  if (type === 'low') {
    // Low — eyes at y=11, gentle downward arc frown
    return (
      <svg {...base}>
        <defs>
          <linearGradient id={grad.id} x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%"   stopColor="#FFFFFF" stopOpacity="0.35" />
            <stop offset="35%"  stopColor={grad.light} />
            <stop offset="100%" stopColor={grad.dark} />
          </linearGradient>
        </defs>
        <circle cx="12" cy="12" r="11" fill={`url(#${grad.id})`} />
        <circle cx="8"  cy="11" r="1.5" fill={INK} />
        <circle cx="16" cy="11" r="1.5" fill={INK} />
        <path
          d="M8 15 Q12 11 16 15"
          stroke={INK}
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    )
  }

  if (type === 'anxious') {
    // Anxious — pressed eyebrows + eyes at y=12 + deep downward arc
    return (
      <svg {...base}>
        <defs>
          <linearGradient id={grad.id} x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%"   stopColor="#FFFFFF" stopOpacity="0.35" />
            <stop offset="35%"  stopColor={grad.light} />
            <stop offset="100%" stopColor={grad.dark} />
          </linearGradient>
        </defs>
        <circle cx="12" cy="12" r="11" fill={`url(#${grad.id})`} />
        {/* Eyebrows — pressed, inner corners raised toward eyes */}
        <line x1="6"  y1="8" x2="10" y2="10" stroke={INK} strokeWidth="1.6" strokeLinecap="round" />
        <line x1="18" y1="8" x2="14" y2="10" stroke={INK} strokeWidth="1.6" strokeLinecap="round" />
        {/* Eyes */}
        <circle cx="8"  cy="12" r="1.5" fill={INK} />
        <circle cx="16" cy="12" r="1.5" fill={INK} />
        {/* Deep downward arc */}
        <path
          d="M8 17 Q12 13 16 17"
          stroke={INK}
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    )
  }

  // Fallback — neutral
  return (
    <svg {...base}>
      <defs>
        <linearGradient id="grad-neutral-fallback" x1="100%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%"   stopColor="#FFFFFF" stopOpacity="0.35" />
          <stop offset="35%"  stopColor={MOOD_GRADIENTS.neutral.light} />
          <stop offset="100%" stopColor={MOOD_GRADIENTS.neutral.dark} />
        </linearGradient>
      </defs>
      <circle cx="12" cy="12" r="11" fill="url(#grad-neutral-fallback)" />
      <circle cx="8"  cy="10" r="1.5" fill={INK} />
      <circle cx="16" cy="10" r="1.5" fill={INK} />
      <line x1="8" y1="14" x2="16" y2="14" stroke={INK} strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

// ─── Types ───────────────────────────────────────────────────────────────────

interface DayEntry {
  entry: Entry
  mapping: MoodMapping
}

interface DayData {
  dateStr: string
  day: number
  entries: DayEntry[]
  dominant: MoodMapping | null
  count: number
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getDateStr(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function buildCalendarData(year: number, month: number, entries: Entry[]): DayData[] {
  const firstDow = new Date(year, month, 1).getDay()
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  const byDate = new Map<string, DayEntry[]>()
  for (const entry of entries) {
    const [datePart] = entry.created_at.split(' ')
    if (!byDate.has(datePart)) byDate.set(datePart, [])
    byDate.get(datePart)!.push({ entry, mapping: mapMood(entry.emotion) })
  }

  const days: DayData[] = Array.from({ length: firstDow }, () =>
    ({ dateStr: '', day: 0, entries: [], dominant: null, count: 0 })
  )

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    const dayEntries = byDate.get(dateStr) ?? []
    let dominant: MoodMapping | null = null
    if (dayEntries.length > 0) {
      dominant = dayEntries.reduce((best, curr) =>
        curr.mapping.score > best.mapping.score ? curr : best
      ).mapping
    }
    days.push({ dateStr, day: d, entries: dayEntries, dominant, count: dayEntries.length })
  }
  return days
}

// ─── Tooltip ─────────────────────────────────────────────────────────────────

interface TooltipState {
  visible: boolean
  x: number
  y: number
  data: DayData | null
}

function DayTooltip({ tooltip }: { tooltip: TooltipState }) {
  if (!tooltip.visible || !tooltip.data || tooltip.data.count === 0) return null
  const { data } = tooltip

  return (
    <div
      style={{
        position: 'fixed',
        left: tooltip.x,
        top: tooltip.y,
        transform: 'translate(-50%, -115%)',
        zIndex: 200,
        background: 'rgba(250,247,240,0.97)',
        borderRadius: 18,
        padding: '14px 16px',
        minWidth: 210,
        maxWidth: 270,
        boxShadow: '0 8px 32px rgba(58,82,71,0.13), 0 2px 8px rgba(58,82,71,0.08)',
        fontFamily: 'DM Sans, sans-serif',
        pointerEvents: 'none',
        backdropFilter: 'blur(4px)',
      }}
    >
      <p style={{ color: '#8A9E90', fontSize: 11, marginBottom: 10, fontWeight: 500 }}>
        {data.dateStr}
        {data.count > 1 && <span style={{ marginLeft: 6 }}>· {data.count} entries</span>}
      </p>
      {data.entries.slice(0, 3).map(({ entry, mapping }, i) => (
        <div key={i} style={{ marginBottom: i < Math.min(data.count - 1, 2) ? 12 : 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
            <MinimalMoodIcon type={mapping.type} size={26} />
            <span style={{ color: '#2A3328', fontSize: 12, fontWeight: 600 }}>{mapping.displayLabel}</span>
          </div>
          <p style={{ color: '#5A6B5E', fontSize: 12, lineHeight: 1.6, paddingLeft: 34 }}>
            {entry.content.length > 55 ? entry.content.slice(0, 55) + '…' : entry.content}
          </p>
        </div>
      ))}
      {data.count > 3 && (
        <p style={{ color: '#8A9E90', fontSize: 11, marginTop: 8, textAlign: 'center' }}>
          +{data.count - 3} more
        </p>
      )}
    </div>
  )
}

// ─── Props ───────────────────────────────────────────────────────────────────

interface EmotionCalendarProps {
  entries: Entry[]
  onSelectDate: (dateStr: string) => void
}

// ─── Main ───────────────────────────────────────────────────────────────────

const WEEKDAY_LABELS = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']

const LEGEND_ITEMS: Array<{ type: MoodType; label: string }> = [
  { type: 'happy',   label: 'Joy' },
  { type: 'calm',    label: 'Calm' },
  { type: 'neutral', label: 'Neutral' },
  { type: 'low',     label: 'Low' },
  { type: 'anxious', label: 'Anxious' },
]

export function EmotionCalendar({ entries, onSelectDate }: EmotionCalendarProps) {
  const now = new Date()
  const [viewYear, setViewYear] = useState(now.getFullYear())
  const [viewMonth, setViewMonth] = useState(now.getMonth())
  const [tooltip, setTooltip] = useState<TooltipState>({ visible: false, x: 0, y: 0, data: null })

  const calendarData = useMemo(
    () => buildCalendarData(viewYear, viewMonth, entries),
    [viewYear, viewMonth, entries],
  )

  const displayMonth = new Date(viewYear, viewMonth, 1).toLocaleString('en-US', { month: 'long' })
  const todayStr = getDateStr(now)

  const navigateMonth = useCallback((delta: -1 | 1) => {
    setViewMonth(m => {
      const next = m + delta
      if (delta === -1 && m === 0)  { setViewYear(y => y - 1); return 11 }
      if (delta === 1  && m === 11) { setViewYear(y => y + 1); return 0 }
      return next
    })
  }, [])

  const handleDayMouseEnter = useCallback((e: React.MouseEvent, data: DayData) => {
    if (data.count === 0) return
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    setTooltip({ visible: true, x: rect.left + rect.width / 2, y: rect.top, data })
  }, [])

  const handleDayMouseLeave = useCallback(() => {
    setTooltip(t => ({ ...t, visible: false }))
  }, [])

  const handleDayClick = useCallback((data: DayData) => {
    if (data.count === 0) return
    onSelectDate(data.dateStr)
  }, [onSelectDate])

  return (
    <div style={{ width: '100%' }}>

      {/* ── Month header ── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 14, padding: '0 2px',
      }}>
        <button
          onClick={() => navigateMonth(-1)}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            padding: '6px 12px', borderRadius: 10,
            color: C.mossMid, fontSize: 20, lineHeight: 1,
            transition: 'background 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(58,82,71,0.07)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'none')}
        >
          ‹
        </button>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
          <p style={{
            fontFamily: "'Playfair Display', serif",
            fontSize: 20,
            fontWeight: 600,
            fontStyle: 'italic',
            color: C.ink,
            letterSpacing: '0.05em',
            lineHeight: 1,
          }}>
            {displayMonth}
          </p>
          <p style={{
            fontFamily: "'Caveat', cursive",
            fontSize: 12,
            fontWeight: 500,
            color: '#C4B8AA',
            letterSpacing: '0.08em',
            lineHeight: 1,
          }}>
            {viewYear}
          </p>
        </div>

        <button
          onClick={() => navigateMonth(1)}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            padding: '6px 12px', borderRadius: 10,
            color: C.mossMid, fontSize: 20, lineHeight: 1,
            transition: 'background 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(58,82,71,0.07)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'none')}
        >
          ›
        </button>
      </div>

      {/* ── Weekday headers ── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
        gap: 2, marginBottom: 6, padding: '0 2px',
      }}>
        {WEEKDAY_LABELS.map((label, i) => (
          <div
            key={label + i}
            style={{
              textAlign: 'center',
              fontSize: 10,
              fontWeight: 500,
              letterSpacing: '0.14em',
              color: i === 0 || i === 6 ? '#D0C8BC' : '#C8C0B4',
              fontFamily: 'DM Sans, sans-serif',
              paddingBottom: 8,
              userSelect: 'none',
            }}
          >
            {label}
          </div>
        ))}
      </div>

      {/* ── Calendar grid ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(7, 1fr)',
        rowGap: 8,
        columnGap: 2,
        placeItems: 'center',
        padding: '0 2px',
      }}>
        {calendarData.map((data, idx) => {
          const isEmpty = data.day === 0
          const hasEntries = data.count > 0
          const { dominant } = data
          const isToday = data.dateStr === todayStr

          return (
            <div
              key={idx}
              style={{
                width: '100%',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: hasEntries ? 'pointer' : 'default',
                padding: '5px 0',
                borderRadius: 14,
                outline: 'none',
                transition: 'background 0.15s',
              }}
              onMouseEnter={e => {
                if (hasEntries) (e.currentTarget as HTMLElement).style.background = 'rgba(58,82,71,0.03)'
                if (hasEntries) handleDayMouseEnter(e as unknown as React.MouseEvent, data)
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.background = 'transparent'
                handleDayMouseLeave()
              }}
              onClick={() => handleDayClick(data)}
            >
              {isEmpty && (
                <span style={{ fontSize: 12, color: 'transparent', lineHeight: 1 }}>·</span>
              )}

              {!isEmpty && !hasEntries && (
                <span
                  style={{
                    fontSize: 11.5,
                    fontWeight: 300,
                    color: isToday ? C.terra : '#C8C0B4',
                    fontFamily: 'DM Sans, sans-serif',
                    lineHeight: 1,
                    userSelect: 'none',
                    letterSpacing: '-0.01em',
                    transition: 'color 0.15s',
                  }}
                  onMouseEnter={e => {
                    if (!isToday) (e.currentTarget as HTMLElement).style.color = '#A8A098'
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLElement).style.color = isToday ? C.terra : '#C8C0B4'
                  }}
                >
                  {data.day}
                </span>
              )}

              {!isEmpty && hasEntries && dominant && (
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'transform 0.15s',
                    }}
                  >
                    <MinimalMoodIcon type={dominant.type} size={36} />
                  </div>

                  {data.count > 1 && (
                    <div style={{
                      position: 'absolute',
                      top: -1,
                      right: -1,
                      width: 5,
                      height: 5,
                      borderRadius: '50%',
                      background: '#B0A898',
                      border: '1px solid #FAF7F0',
                    }} />
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* ── Legend ── */}
      <div style={{
        display: 'flex',
        gap: 14,
        justifyContent: 'center',
        marginTop: 14,
        paddingTop: 12,
        borderTop: '1px solid rgba(214,206,191,0.4)',
      }}>
        {LEGEND_ITEMS.map(({ type, label }) => (
          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <MinimalMoodIcon type={type} size={18} />
            <span style={{
              fontSize: 10,
              color: '#B0A898',
              fontFamily: 'DM Sans, sans-serif',
              fontWeight: 400,
              letterSpacing: '0.02em',
            }}>
              {label}
            </span>
          </div>
        ))}
      </div>

      <DayTooltip tooltip={tooltip} />
    </div>
  )
}
