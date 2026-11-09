import { motion } from 'motion/react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useEntries } from './hooks/useEntries'
import { useChat } from './hooks/useChat'
import { useAuthState } from './router'
import { clearToken } from './api/auth'
import { listPoetry, generatePoetry } from './api/client'
import EmotionCanvas from './components/canvas/EmotionCanvas'
import RecordComposer from './components/canvas/RecordComposer'
import LeftNav from './components/layout/LeftNav'
import EntryDetail from './components/detail/EntryDetail'
import ChatPanel from './components/chat/ChatPanel'
import PoetryPanel from './components/poetry/PoetryPanel'
import { formatClock } from './utils/formatTime'
import { mapMood } from './utils/moodMapping'
import { sortEntries } from './utils/emotionCurve'
import type { AppView, Entry, PoetryReport } from './types'

export default function App() {
  const { logout } = useAuthState()
  const chat = useChat()
  const [view, setView] = useState<AppView>('canvas')
  const [panelOpen, setPanelOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [poetry, setPoetry] = useState<PoetryReport[]>([])
  const [poetryBusy, setPoetryBusy] = useState(false)
  const [poetryError, setPoetryError] = useState<string | null>(null)

  const [period, setPeriod] = useState(0)
  const end = new Date()
  end.setHours(0, 0, 0, 0)
  end.setDate(end.getDate() - period * 30)
  const start = new Date(end)
  start.setDate(start.getDate() - 29)
  const dayKey = (date: Date) => [date.getFullYear(), String(date.getMonth()+1).padStart(2,'0'), String(date.getDate()).padStart(2,'0')].join('-')
  const first = dayKey(start)
  const last = dayKey(end)
  const until = new Date(end)
  until.setDate(until.getDate() + 1)
  const { entries, loading, submitting, submit, error, justSaved, hasEarlier } = useEntries(start.toISOString(), until.toISOString())
  const canvasEntries = useMemo(() => sortEntries(entries), [entries])
  const selected = canvasEntries.find(e => e.id === selectedId) ?? canvasEntries.at(-1)
  const dayEntries = canvasEntries.filter(e => e.created_at.slice(0, 10) === selected?.created_at.slice(0, 10)).reverse()

  const anchorEntry = useMemo(() => {
    const id = chat.currentConversation?.anchor_entry_id
    if (!id) return selected ?? null
    return entries.find((entry) => entry.id === id) ?? selected
  }, [chat.currentConversation?.anchor_entry_id, entries, selected])

  useEffect(() => {
    listPoetry(100).then(setPoetry).catch(() => setPoetryError('诗篇暂时无法读取'))
  }, [])

  async function handleGeneratePoetry() {
    setPoetryBusy(true)
    setPoetryError(null)
    try {
      const report = await generatePoetry()
      setPoetry(previous => [report, ...previous])
    } catch (err) {
      setPoetryError(err instanceof Error ? err.message : '生成失败，请再试一次。')
    } finally {
      setPoetryBusy(false)
    }
  }

  const handleLogout = useCallback(() => {
    clearToken()
    logout()
  }, [logout])

  const handleSelect = useCallback((entry: Entry) => {
    setSelectedId(entry.id)
    setPanelOpen(true)
    setView('canvas')
  }, [])

  const handleContinue = useCallback(async (entry: Entry) => {
    await chat.startFromEntry(entry)
    setView('chat')
    setPanelOpen(true)
  }, [chat])

  const handleView = useCallback((next: AppView) => {
    setView(next)
    setPanelOpen(true)
  }, [])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0b0c0f] text-[#eceef2]">
      <LeftNav
        view={view}
        panelOpen={panelOpen}
        onView={handleView}
        onTogglePanel={() => setPanelOpen((v) => !v)}
        onLogout={handleLogout}
      />

      <main className="relative flex min-w-0 flex-1 flex-col">
        <header className="flex items-end justify-between gap-2 px-3 pb-2 pt-4 sm:px-8">
          <div>
            <p className="text-[11px] tracking-[0.28em] text-[#8b909a] uppercase">Moorchid</p>
            <h1 className="serif mt-1 text-2xl text-white sm:text-4xl">情绪兰花</h1>
          </div>
          <div className="text-right text-xs text-[#b1b6c1]">
            <p>{first.slice(5)} 至 {last.slice(5)} · 每日平均心情</p>
            <button disabled={loading || submitting || !hasEarlier} onClick={() => setPeriod(p => p + 1)} className="p-2 disabled:opacity-30">上 30 天</button>
            <button disabled={loading || submitting || !period} onClick={() => setPeriod(p => p - 1)} className="p-2 disabled:opacity-30">下 30 天</button>
          </div>
        </header>

        <div className="relative min-h-0 flex-1">
          <EmotionCanvas
            entries={canvasEntries}
            selectedId={dayEntries[0]?.id ?? null}
            onSelect={handleSelect}
          />
          {!canvasEntries.length && <p className="absolute inset-x-3 top-1/3 text-center text-sm text-[#a9aeb8]">{loading ? '正在读取记录…' : period ? '这段时间没有记录' : '记下今天的心情，留下第一个节点。'}</p>}
        </div>
        <div className="shrink-0 px-3 pb-4 sm:px-8">
          <p role="status" className="min-h-6 text-center text-xs text-[#b6c7cc]">{error || (justSaved ? '已保存，今天的心情节点已更新' : '')}</p>
          <RecordComposer submitting={submitting || loading} onSubmit={async (text, mood) => {
            const saved = await submit(text, mood)
            if (!saved) return false
            setPeriod(0)
            setSelectedId(saved.id)
            return true
          }} />
        </div>
      </main>

      <motion.aside
        initial={false}
        animate={{ width: panelOpen ? 'min(420px, calc(100vw - 64px))' : 0 }}
        transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
        className="absolute inset-y-0 right-0 z-10 lg:static shrink-0 overflow-hidden border-l border-white/6 bg-[#12141a]"
      >
        {panelOpen && (
          <div className="flex h-full w-full flex-col overflow-y-auto px-5 py-6">
            {view === 'chat' ? (
              <ChatPanel
                conversations={chat.conversations}
                currentId={chat.currentConversationId}
                messages={chat.messages}
                streamingText={chat.streamingText}
                isLoading={chat.isLoading}
                anchorEntry={anchorEntry ?? null}
                onSelect={(id) => void chat.selectConversation(id)}
                onNew={() => void chat.newConversation()}
                onSend={(text) => void chat.send(text)}
              />
            ) : view === 'poetry' ? (
              <PoetryPanel
                reports={poetry}
                generating={poetryBusy}
                error={poetryError}
                onGenerate={handleGeneratePoetry}
              />
            ) : selected ? (
              <>
              <h2 className="mb-2 text-sm">当天记录 · {dayEntries.length} 条</h2>
              <div className="mb-4 flex flex-col gap-1">
                {dayEntries.map(e => <button key={e.id} onClick={() => setSelectedId(e.id)} aria-pressed={selected.id === e.id} className="truncate rounded px-2 py-2 text-left text-sm aria-pressed:bg-white/10">
                  {formatClock(e.created_at)} · {mapMood(e.emotion).displayLabel}　{e.content}
                </button>)}
              </div>
              <EntryDetail
                entry={selected}
                onContinue={(entry) => void handleContinue(entry)}
              />
              </>
            ) : (
              <p className="serif text-xl text-[#8b909a]">选择画布上的一个节点。</p>
            )}
          </div>
        )}
      </motion.aside>
    </div>
  )
}
