import { useState } from 'react'
import type { Mood } from '../../types'
import { mapMood } from '../../utils/moodMapping'

const MOODS: Mood[] = ['Joy', 'Calm', 'Neutral', 'Low', 'Anxious']

interface RecordComposerProps {
  submitting?: boolean
  onSubmit: (content: string, mood?: string) => Promise<boolean>
}

export default function RecordComposer({ submitting, onSubmit }: RecordComposerProps) {
  const [content, setContent] = useState('')
  const [mood, setMood] = useState<Mood | ''>('')

  async function handleSubmit() {
    const text = content.trim()
    if (!text || submitting) return
    if (!await onSubmit(text, mood || undefined)) return
    setContent('')
    setMood('')
  }

  return (
    <div className="glass-composer pointer-events-auto mx-auto w-full max-w-3xl rounded-3xl px-5 py-4">
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <p className="text-sm text-[#c7cbd3]">此刻的心情</p>
        <div role="group" aria-label="选择心情或让 AI 判断" className="flex flex-wrap gap-1.5">
          {(['', ...MOODS] as const).map(item => {
            const active = mood === item
            const mapped = mapMood(item)
            return (
              <button
                key={item || 'auto'}
                type="button"
                aria-pressed={active}
                disabled={submitting}
                onClick={() => setMood(item)}
                className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition"
                style={{
                  background: active ? 'rgba(255,255,255,0.10)' : 'transparent',
                  borderColor: active ? '#aab1be' : 'rgba(255,255,255,0.12)',
                  color: active ? '#ffffff' : '#b3b8c2',
                }}
              >
                {item && <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ background: mapped.color }} />}
                {item ? mapped.displayLabel : 'AI 判断'}
              </button>
            )
          })}
        </div>
      </div>
      <div className="flex items-end gap-3">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault()
              void handleSubmit()
            }
          }}
          placeholder="把这一刻轻轻写下……"
          disabled={submitting}
          rows={2}
          className="min-h-[72px] flex-1 resize-none bg-transparent text-[15px] leading-7 text-[#eceef2] outline-none placeholder:text-[#5d626c]"
        />
        <button
          type="button"
          disabled={!content.trim() || submitting}
          onClick={() => void handleSubmit()}
          className="h-11 shrink-0 rounded-2xl bg-white px-5 text-sm font-medium text-[#0b0c0f] transition disabled:opacity-40"
        >
          {submitting ? '写入中' : '落下'}
        </button>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-1 text-xs text-[#a8aeb9]">
        <span aria-live="polite">{mood ? `这条随记会按你选的「${mapMood(mood).displayLabel}」记录。` : '可以自己选心情，也可以直接写，让 AI 根据文字判断。'}</span>
        <span className="hidden text-[11px] sm:inline">⌘/Ctrl + Enter</span>
      </div>
    </div>
  )
}
