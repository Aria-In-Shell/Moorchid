/**
 * useChat — multi-conversation React hook for the Soul Chat screen.
 *
 * State managed:
 *   • conversations           — list shown in the Sidebar
 *   • currentConversationId   — which thread the ChatArea displays
 *   • messages                — messages of the *current* conversation only
 *   • streamingText           — token buffer for the in-flight assistant reply
 *   • isLoading               — a stream is running (typing dots)
 *   • isInitialLoading        — first conversation list is still loading
 *   • sidebarOpen             — Sidebar visibility (mobile drawer state)
 *   • error                   — last surfaced failure
 *
 * Migration story
 * ───────────────
 * The backend keeps providing backward compatibility for the legacy flat
 * `/api/chat/history` endpoint. New code paths always go through the
 * conversation-aware APIs so a fresh conversation can be created on
 * demand and the active thread switches cleanly.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  createConversation,
  deleteConversation,
  getConversationMessages,
  listConversations,
  renameConversation as apiRenameConversation,
} from '../api/client'
import { chatNonStream, chatStreamFetch } from '../api/client'
import type { ChatMessage, Conversation } from '../types'

export function useChat() {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streamingText, setStreamingText] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isInitialLoading, setIsInitialLoading] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<(() => void) | null>(null)

  // ── Refresh Sidebar list ────────────────────────────────────────────────
  const refreshConversations = useCallback(async () => {
    try {
      const data = await listConversations(1, 100)
      setConversations(data.conversations)
      return data.conversations
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load conversations')
      return [] as Conversation[]
    }
  }, [])

  // ── Load messages for one conversation ─────────────────────────────────
  const loadMessages = useCallback(async (convId: string) => {
    try {
      const { messages: ms } = await getConversationMessages(convId, 200)
      setMessages(ms)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load messages')
      setMessages([])
    }
  }, [])

  // ── Initial mount ───────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false
    setIsInitialLoading(true)
    ;(async () => {
      const list = await refreshConversations()
      if (cancelled) return
      // Auto-select the most recently updated conversation, if any.
      if (list.length > 0) {
        const first = list[0]
        setCurrentConversationId(first.id)
        await loadMessages(first.id)
      }
      if (!cancelled) setIsInitialLoading(false)
    })()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Select / switch conversation ─────────────────────────────────────────
  const selectConversation = useCallback(async (id: string) => {
    if (id === currentConversationId) return
    // Cancel any in-flight stream before switching.
    if (abortRef.current) { abortRef.current(); abortRef.current = null }
    setIsLoading(false)
    setStreamingText('')
    setCurrentConversationId(id)
    await loadMessages(id)
  }, [currentConversationId, loadMessages])

  // ── New conversation ────────────────────────────────────────────────────
  const newConversation = useCallback(async (title?: string, anchorEntryId?: number) => {
    try {
      const conv = await createConversation(title, anchorEntryId)
      setConversations(prev => [conv, ...prev])
      setCurrentConversationId(conv.id)
      setMessages([])
      setStreamingText('')
      setIsLoading(false)
      return conv
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create conversation')
      return null
    }
  }, [])

  // ── Delete conversation ──────────────────────────────────────────────────
  const removeConversation = useCallback(async (id: string) => {
    try {
      await deleteConversation(id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete conversation')
      return
    }
    const remaining = conversations.filter(c => c.id !== id)
    setConversations(remaining)
    if (currentConversationId === id) {
      if (remaining.length > 0) {
        const next = remaining[0]
        setCurrentConversationId(next.id)
        await loadMessages(next.id)
      } else {
        setCurrentConversationId(null)
        setMessages([])
      }
    }
  }, [conversations, currentConversationId, loadMessages])

  // ── Rename conversation ──────────────────────────────────────────────────
  const renameConversationById = useCallback(async (id: string, title: string) => {
    try {
      const updated = await apiRenameConversation(id, title)
      setConversations(prev => prev.map(c => c.id === id ? updated : c))
      return updated
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to rename conversation')
      return null
    }
  }, [])

  const currentConversation = conversations.find(c => c.id === currentConversationId) ?? null

  const startFromEntry = useCallback(async (entry: { id: number; content: string }) => {
    const title = entry.content.replace(/\s+/g, ' ').slice(0, 18)
    return newConversation(title || '从随记继续', entry.id)
  }, [newConversation])

  // ── Send a message ───────────────────────────────────────────────────────
  const send = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed) return

    // Lazy-create a conversation on first send so the user never sees
    // an empty thread in the DB. Mirrors DeepSeek / ChatGPT UX.
    let activeId = currentConversationId
    if (!activeId) {
      const fresh = await newConversation()
      if (!fresh) return
      activeId = fresh.id
    }

    const userMsg: ChatMessage = { role: 'user', content: trimmed }
    setMessages(prev => [...prev, userMsg])
    setStreamingText('')
    setIsLoading(true)
    setError(null)

    const fallbackToNonStream = async () => {
      try {
        const { reply, conversation_id: resolvedId } = await chatNonStream(
          trimmed, [], activeId ?? undefined, currentConversation?.anchor_entry_id ?? undefined,
        )
        setMessages(prev => [...prev, { role: 'assistant', content: reply }])
        setStreamingText('')
        setIsLoading(false)
        // Sidebar ordering changed (touch) → refresh.
        if (resolvedId) await refreshConversations()
      } catch (e) {
        const msg = e instanceof Error ? e.message : 'Failed to get reply'
        setError(msg)
        setIsLoading(false)
        setStreamingText('')
      }
    }

    try {
      let fullText = ''
      await chatStreamFetch(trimmed, [], {
        conversationId: activeId ?? undefined,
        anchorEntryId: currentConversation?.anchor_entry_id ?? undefined,
        onChunk: (chunk) => {
          fullText += chunk
          setStreamingText(fullText)
        },
        onDone: () => {
          setMessages(prev => [...prev, { role: 'assistant', content: fullText }])
          setStreamingText('')
          setIsLoading(false)
          // Touch updated_at → refresh sidebar ordering.
          refreshConversations().catch(() => {})
        },
        onError: () => {
          fallbackToNonStream()
        },
      })
    } catch {
      fallbackToNonStream()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentConversationId, currentConversation?.anchor_entry_id, newConversation, refreshConversations])

  // ── Cancel an in-flight stream (used by future Stop button) ──────────────
  const stop = useCallback(() => {
    if (abortRef.current) { abortRef.current(); abortRef.current = null }
    setIsLoading(false)
  }, [])

  return {
    conversations,
    currentConversationId,
    currentConversation,
    messages,
    streamingText,
    isLoading,
    isInitialLoading,
    sidebarOpen,
    setSidebarOpen,
    error,
    send,
    selectConversation,
    newConversation,
    startFromEntry,
    removeConversation,
    renameConversation: renameConversationById,
    refreshConversations,
    stop,
  }
}
