import type { Entry } from '../../types'
import { formatClock, formatDateLabel } from '../../utils/formatTime'
import { mapMood } from '../../utils/moodMapping'

interface EntryDetailProps {
  entry: Entry
  preview?: boolean
  onContinue: (entry: Entry) => void
}

export default function EntryDetail({ entry, preview, onContinue }: EntryDetailProps) {
  const mood = mapMood(entry.emotion)
  const when = formatDateLabel(entry.created_at)
  const inferences = entry.analysis?.inferences ?? []
  const events = entry.analysis?.events ?? []

  return (
    <div className="panel-enter flex h-full flex-col">
      <p className="text-[11px] tracking-[0.22em] text-[#8b909a] uppercase">那一刻</p>
      <div className="mt-4 flex items-center gap-3">
        <span
          className="h-3 w-3 rounded-full"
          style={{ background: mood.color, boxShadow: `0 0 16px ${mood.glow}` }}
        />
        <h2 className="serif text-3xl text-white">{mood.displayLabel}</h2>
      </div>
      <p className="mt-2 text-sm text-[#8b909a]">
        {when.full} · {formatClock(entry.created_at)}
      </p>

      <p className="mt-6 text-[15px] leading-8 text-[#eceef2]">{entry.content}</p>

      {entry.tags.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          {entry.tags.map((tag) => (
            <span key={tag} className="rounded-full border border-white/8 px-3 py-1 text-xs text-[#8b909a]">
              {tag}
            </span>
          ))}
        </div>
      )}

      {(events.length > 0 || inferences.length > 0) && (
        <div className="mt-8 space-y-4 border-t border-white/6 pt-6">
          <p className="text-[11px] tracking-[0.18em] text-[#8b909a] uppercase">分层记忆</p>
          <div>
            <p className="mb-2 text-xs text-[#5eead4]">用户陈述</p>
            <p className="text-sm leading-6 text-[#c7cbd3]">{entry.content}</p>
          </div>
          {events.map((event) => (
            <div key={event.summary}>
              <p className="mb-1 text-xs text-[#f5c15a]">事件 · 置信度 {event.confidence.toFixed(2)}</p>
              <p className="text-sm leading-6 text-[#c7cbd3]">{event.summary}</p>
            </div>
          ))}
          {inferences.map((item) => (
            <div key={item.claim}>
              <p className="mb-1 text-xs text-[#818cf8]">模型推断 · 置信度 {item.confidence.toFixed(2)}</p>
              <p className="text-sm leading-6 text-[#c7cbd3]">{item.claim}</p>
            </div>
          ))}
        </div>
      )}

      <div className="mt-auto pt-8">
        {preview ? (
          <p className="text-xs leading-6 text-[#8b909a]">这是示例节点。写下你的第一条随记后，将变成你的兰花。</p>
        ) : (
          <button
            type="button"
            onClick={() => onContinue(entry)}
            className="w-full rounded-2xl bg-white py-3 text-sm font-medium text-[#0b0c0f]"
          >
            从这里继续对话
          </button>
        )}
      </div>
    </div>
  )
}
