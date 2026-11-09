/**
 * ChatSidebar — left-hand conversation history list, modelled after
 * DeepSeek / ChatGPT. Hover-revealed row actions keep the chrome clean.
 */

import { useMemo, useState } from 'react'
import type { Conversation } from '../types'

const FONT_SERIF_CN = '"Kaiti SC", "STKaiti", "KaiTi", "Noto Serif SC", "Source Han Serif SC", "Songti SC", "STSong", "SimSun", serif'

const C = {
  bg: '#E8E2D5',
  card: '#FAF7F0',
  moss: '#3A5247',
  mossMid: '#4E6B5C',
  mossLight: '#7A9B8A',
  terra: '#B87355',
  ink: '#2A3328',
  inkMid: '#5A6B5E',
  inkLight: '#8A9E90',
  border: '#D6CEBF',
  borderLight: '#E4DDD0',
}

function formatRelative(updatedAt: string): string {
  // SQLite timestamps look like "YYYY-MM-DD HH:MM:SS" (local).
  const [datePart, timePart] = updatedAt.split(' ')
  const [y, m, d] = datePart.split('-').map(Number)
  const [hh, mm] = (timePart ?? '00:00:00').split(':').map(Number)
  const dt = new Date(y, m - 1, d, hh, mm)
  const now = new Date()
  const diffMs = now.getTime() - dt.getTime()
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} 小时前`
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  const yesterday = new Date(now); yesterday.setDate(now.getDate() - 1)
  if (sameDay(dt, yesterday)) return '昨天'
  if (sameDay(dt, now)) return '今天'
  return `${m}月${d}日`
}

interface ChatSidebarProps {
  conversations: Conversation[]
  currentId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  onRename: (id: string, title: string) => void
  width?: number
}

export function ChatSidebar({
  conversations,
  currentId,
  onSelect,
  onNew,
  onDelete,
  onRename,
  width = 280,
}: ChatSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draftTitle, setDraftTitle] = useState('')
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)

  const grouped = useMemo(() => {
    const today: Conversation[] = []
    const yesterday: Conversation[] = []
    const earlier: Conversation[] = []
    const now = new Date()
    const y = new Date(now); y.setDate(now.getDate() - 1)
    const sameDay = (a: Date, b: Date) =>
      a.getFullYear() === b.getFullYear() &&
      a.getMonth() === b.getMonth() &&
      a.getDate() === b.getDate()
    for (const c of conversations) {
      const [dp, tp] = c.updated_at.split(' ')
      const [yy, mm, dd] = dp.split('-').map(Number)
      const [hh, mi] = (tp ?? '00:00:00').split(':').map(Number)
      const dt = new Date(yy, mm - 1, dd, hh, mi)
      if (sameDay(dt, now)) today.push(c)
      else if (sameDay(dt, y)) yesterday.push(c)
      else earlier.push(c)
    }
    return { today, yesterday, earlier }
  }, [conversations])

  const renderGroup = (label: string, items: Conversation[]) => {
    if (items.length === 0) return null
    return (
      <div key={label} style={{ marginTop: 14 }}>
        <p style={{
          fontSize: 10, letterSpacing: '0.18em', fontWeight: 700,
          color: C.mossLight, padding: '0 14px', marginBottom: 6,
          fontFamily: '"DM Sans", sans-serif',
        }}>
          {label}
        </p>
        {items.map(c => {
          const isActive = c.id === currentId
          const isEditing = editingId === c.id
          const menuOpen = menuOpenId === c.id
          return (
            <div
              key={c.id}
              onClick={() => { if (!isEditing) onSelect(c.id) }}
              onMouseLeave={e => {
                if (!isActive && !isEditing) {
                  (e.currentTarget as HTMLDivElement).style.background = 'transparent'
                }
                if (menuOpen) setMenuOpenId(null)
              }}
              style={{
                position: 'relative',
                margin: '1px 8px',
                padding: '9px 12px',
                borderRadius: 11,
                background: isActive ? 'rgba(58,82,71,0.10)' : 'transparent',
                border: isActive ? `1px solid rgba(58,82,71,0.30)` : '1px solid transparent',
                cursor: isEditing ? 'default' : 'pointer',
                transition: 'background 0.15s, border-color 0.15s',
              }}
              onMouseEnter={e => {
                if (!isActive && !isEditing) {
                  (e.currentTarget as HTMLDivElement).style.background =
                    'rgba(58,82,71,0.05)'
                }
              }}
            >
              {isEditing ? (
                <input
                  autoFocus
                  value={draftTitle}
                  onChange={e => setDraftTitle(e.target.value)}
                  onClick={e => e.stopPropagation()}
                  onKeyDown={e => {
                    if (e.key === 'Enter') {
                      const t = draftTitle.trim()
                      if (t) onRename(c.id, t)
                      setEditingId(null); setDraftTitle('')
                    }
                    if (e.key === 'Escape') {
                      setEditingId(null); setDraftTitle('')
                    }
                  }}
                  onBlur={() => {
                    const t = draftTitle.trim()
                    if (t) onRename(c.id, t)
                    setEditingId(null); setDraftTitle('')
                  }}
                  style={{
                    width: '100%', background: 'transparent', border: 'none',
                    outline: 'none', fontSize: 13, color: C.ink, padding: 0,
                    fontFamily: '"DM Sans", sans-serif',
                  }}
                />
              ) : (
                <p style={{
                  fontSize: 13, color: isActive ? C.ink : C.inkMid,
                  fontWeight: isActive ? 600 : 500,
                  margin: 0, lineHeight: 1.45,
                  overflow: 'hidden', textOverflow: 'ellipsis',
                  display: '-webkit-box', WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical' as const,
                  fontFamily: '"DM Sans", sans-serif',
                }}>
                  {c.title}
                </p>
              )}

              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginTop: 4,
              }}>
                <p style={{
                  fontSize: 10.5, color: C.inkLight, margin: 0,
                  fontFamily: '"DM Sans", sans-serif',
                }}>
                  {formatRelative(c.updated_at)}
                </p>

                {!isEditing && (
                  <button
                    onClick={e => {
                      e.stopPropagation()
                      setMenuOpenId(menuOpen ? null : c.id)
                    }}
                    title="更多"
                    style={{
                      background: 'transparent', border: 'none',
                      cursor: 'pointer', padding: '2px 4px', borderRadius: 6,
                      color: C.mossLight, fontSize: 14, lineHeight: 1,
                      opacity: menuOpen ? 1 : 0,
                      transition: 'opacity 0.15s, background 0.15s',
                    }}
                    onMouseEnter={e => {
                      (e.currentTarget as HTMLButtonElement).style.opacity = '1'
                      ;(e.currentTarget as HTMLButtonElement).style.background =
                        'rgba(58,82,71,0.12)'
                    }}
                    onMouseLeave={e => {
                      ;(e.currentTarget as HTMLButtonElement).style.background =
                        'transparent'
                    }}
                  >
                    ⋯
                  </button>
                )}
              </div>

              {menuOpen && !isEditing && (
                <div
                  onClick={e => e.stopPropagation()}
                  onMouseLeave={() => setMenuOpenId(null)}
                  style={{
                    position: 'absolute', right: 8, top: 28, zIndex: 5,
                    background: C.card, border: `1px solid ${C.border}`,
                    borderRadius: 10, boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
                    minWidth: 110, overflow: 'hidden',
                  }}
                >
                  <button
                    onClick={() => {
                      setEditingId(c.id)
                      setDraftTitle(c.title)
                      setMenuOpenId(null)
                    }}
                    style={{
                      width: '100%', textAlign: 'left', padding: '9px 14px',
                      background: 'transparent', border: 'none', cursor: 'pointer',
                      fontSize: 12.5, color: C.ink, fontFamily: '"DM Sans", sans-serif',
                    }}
                    onMouseEnter={e => {
                      (e.currentTarget as HTMLButtonElement).style.background =
                        'rgba(58,82,71,0.06)'
                    }}
                    onMouseLeave={e => {
                      (e.currentTarget as HTMLButtonElement).style.background =
                        'transparent'
                    }}
                  >
                    重命名
                  </button>
                  <button
                    onClick={() => {
                      onDelete(c.id); setMenuOpenId(null)
                    }}
                    style={{
                      width: '100%', textAlign: 'left', padding: '9px 14px',
                      background: 'transparent', border: 'none', cursor: 'pointer',
                      fontSize: 12.5, color: C.terra, fontFamily: '"DM Sans", sans-serif',
                    }}
                    onMouseEnter={e => {
                      (e.currentTarget as HTMLButtonElement).style.background =
                        'rgba(184,115,85,0.08)'
                    }}
                    onMouseLeave={e => {
                      (e.currentTarget as HTMLButtonElement).style.background =
                        'transparent'
                    }}
                  >
                    删除
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  return (
    <aside
      style={{
        width,
        minWidth: width,
        maxWidth: width,
        height: '100%',
        background: C.card,
        borderRight: `1px solid ${C.borderLight}`,
        display: 'flex', flexDirection: 'column',
        flexShrink: 0,
        overflow: 'hidden',
      }}
    >
      {/* Brand + new conversation */}
      <div style={{ padding: '16px 16px 12px' }}>
        <h2 style={{
          fontFamily: FONT_SERIF_CN, fontSize: 18, fontWeight: 600,
          color: C.moss, margin: 0, letterSpacing: '0.04em',
        }}>
          Moorchid
        </h2>
        <p style={{
          fontSize: 10.5, color: C.inkLight, marginTop: 2, fontWeight: 500,
          fontFamily: '"DM Sans", sans-serif', letterSpacing: '0.06em',
        }}>
          深度对聊 · 历史记录
        </p>
        <button
          onClick={onNew}
          style={{
            marginTop: 14, width: '100%',
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            padding: '10px 0',
            background: C.moss, color: '#FAF7F0',
            border: 'none', borderRadius: 12,
            fontSize: 13, fontWeight: 600, cursor: 'pointer',
            fontFamily: '"DM Sans", sans-serif',
            boxShadow: '0 2px 10px rgba(58,82,71,0.22)',
          }}
        >
          <span style={{ fontSize: 16, lineHeight: 1, marginTop: -2 }}>＋</span>
          新对话
        </button>
      </div>

      {/* Conversation list */}
      <div
        className="sidebar-scroll"
        style={{
          flex: 1,
          overflowY: 'auto',
          paddingBottom: 20,
          WebkitOverflowScrolling: 'touch',
        }}
      >
        {renderGroup('今天', grouped.today)}
        {renderGroup('昨天', grouped.yesterday)}
        {renderGroup('更早', grouped.earlier)}
        {conversations.length === 0 && (
          <div style={{ padding: '40px 18px', textAlign: 'center' }}>
            <p style={{ fontSize: 12.5, color: C.inkLight, fontStyle: 'italic' }}>
              还没有历史对话
            </p>
            <p style={{ fontSize: 11, color: C.mossLight, marginTop: 6 }}>
              点击「新对话」开始一段新的思考
            </p>
          </div>
        )}
      </div>

      <style>{`
        .sidebar-scroll::-webkit-scrollbar { width: 6px; }
        .sidebar-scroll::-webkit-scrollbar-track { background: transparent; }
        .sidebar-scroll::-webkit-scrollbar-thumb { background: rgba(58,82,71,0.18); border-radius: 3px; }
        .sidebar-scroll::-webkit-scrollbar-thumb:hover { background: rgba(58,82,71,0.32); }
      `}</style>
    </aside>
  )
}
