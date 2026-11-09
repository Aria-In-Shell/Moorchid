import { useEffect, useRef, useState } from 'react'
import type { ChatMessage, Conversation, Entry } from '../../types'
import { formatRelative } from '../../utils/formatTime'

interface ChatPanelProps {
  conversations: Conversation[]
  currentId: string | null
  messages: ChatMessage[]
  streamingText: string
  isLoading: boolean
  anchorEntry?: Entry | null
  onSelect: (id: string) => void
  onNew: () => void
  onSend: (text: string) => void
}

export default function ChatPanel({
  conversations,
  currentId,
  messages,
  streamingText,
  isLoading,
  anchorEntry,
  onSelect,
  onNew,
  onSend,
}: ChatPanelProps) {
  const [draft, setDraft] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingText])

  return (
    <div className="panel-enter flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] tracking-[0.22em] text-[#8b909a] uppercase">Soul Chat</p>
          <h2 className="serif mt-1 text-2xl text-white">深度对话</h2>
        </div>
        <button
          type="button"
          onClick={onNew}
          className="rounded-full border border-white/10 px-3 py-1 text-xs text-[#c7cbd3] hover:bg-white/5"
        >
          新对话
        </button>
      </div>

      <div className="mt-4 flex gap-2 overflow-x-auto pb-2">
        {conversations.slice(0, 8).map((conv) => (
          <button
            key={conv.id}
            type="button"
            onClick={() => onSelect(conv.id)}
            className={`max-w-[140px] shrink-0 truncate rounded-full px-3 py-1 text-xs ${
              conv.id === currentId ? 'bg-white text-[#0b0c0f]' : 'bg-white/6 text-[#8b909a]'
            }`}
          >
            {conv.title}
          </button>
        ))}
      </div>

      {anchorEntry && (
        <div className="mt-3 rounded-2xl border border-white/8 bg-white/4 px-4 py-3">
          <p className="text-[10px] tracking-[0.16em] text-[#5eead4] uppercase">锚定随记</p>
          <p className="mt-1 line-clamp-3 text-sm leading-6 text-[#c7cbd3]">{anchorEntry.content}</p>
        </div>
      )}

      <div className="panel-scroll mt-4 flex-1 space-y-4 pr-1">
        {messages.length === 0 && !streamingText && (
          <p className="serif text-lg leading-8 text-[#8b909a]">
            我在这里。可以从一条兰花节点走进来，也可以直接说此刻的事。
          </p>
        )}
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={message.role === 'user' ? 'text-right' : 'text-left'}>
            <div
              className={`inline-block max-w-[92%] rounded-3xl px-4 py-3 text-[14px] leading-7 ${
                message.role === 'user'
                  ? 'bg-white text-[#0b0c0f]'
                  : 'bg-white/6 text-[#eceef2]'
              }`}
            >
              {message.content}
            </div>
          </div>
        ))}
        {streamingText && (
          <div className="text-left">
            <div className="inline-block max-w-[92%] rounded-3xl bg-white/6 px-4 py-3 text-[14px] leading-7 text-[#eceef2]">
              {streamingText}
            </div>
          </div>
        )}
        {isLoading && !streamingText && (
          <p className="text-xs tracking-[0.18em] text-[#8b909a]">倾听中…</p>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        className="mt-4 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          const text = draft.trim()
          if (!text) return
          onSend(text)
          setDraft('')
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="继续说…"
          className="h-12 flex-1 rounded-2xl border border-white/8 bg-white/4 px-4 text-sm outline-none placeholder:text-[#5d626c]"
        />
        <button type="submit" className="h-12 rounded-2xl bg-white px-4 text-sm font-medium text-[#0b0c0f]">
          发送
        </button>
      </form>
      {currentId && (
        <p className="mt-2 text-[10px] text-[#5d626c]">
          {conversations.find((c) => c.id === currentId)?.updated_at
            ? formatRelative(conversations.find((c) => c.id === currentId)!.updated_at)
            : ''}
        </p>
      )}
    </div>
  )
}
