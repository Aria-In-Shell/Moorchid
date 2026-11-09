/**
 * Moorchid API client — thin wrapper around fetch() targeting FastAPI.
 *
 * Authentication
 * --------------
 * Each request automatically attaches `Authorization: Bearer <token>` from
 * localStorage. The token is never sent in the request body — the backend
 * resolves the user identity from the JWT alone.
 *
 * On a 401 response the token is cleared and a global `auth:logout` window
 * event is dispatched so React components (via `useAuth`) can redirect to
 * the login screen.
 *
 * Base URL
 * --------
 * Reads `VITE_API_BASE_URL` from the build-time environment (see
 * UI/.env.production / UI/.env.development). Falls back to the dev default
 * when the variable is missing so the app still boots in ad-hoc setups.
 */

import type {
  ChatHistoryResponse,
  Conversation,
  ConversationListResponse,
  Entry,
  EntryCreate,
  EntryUpdate,
  HealthStatus,
  MemoryRecord,
  PoetryReport,
} from '../types'
import { clearToken, getToken } from './auth'

/**
 * Resolve the FastAPI base URL at request time.
 *
 * Strategy:
 *   • Build-time `VITE_API_BASE_URL` wins (see UI/.env.production →
 *     `VITE_API_BASE_URL=/api`).
 *   • When that variable is empty/absent AND we are running inside the
 *     Vite dev server, fall back to `http://localhost:8000` so the
 *     `npm run dev` workflow still hits FastAPI directly.
 *   • In a production build without the env variable, default to the
 *     SAME-ORIGIN relative path `/api`. Nginx in front of FastAPI is
 *     expected to reverse-proxy `/api/*` → `127.0.0.1:8000`, so the
 *     browser never needs to resolve a different hostname/port. This
 *     is critical for mobile users hitting the site over a public
 *     domain / IP — the previous logic that built
 *     `http://${window.location.hostname}:8000` is what produced the
 *     "Failed to fetch" errors on phones, because port 8000 is not
 *     reachable from the public internet.
 */
function resolveApiBase(): string {
  const rawEnv = import.meta.env.VITE_API_BASE_URL
  if (typeof rawEnv === 'string' && rawEnv.trim().length > 0) {
    const trimmed = rawEnv.trim().replace(/\/+$/, '')
    if (/^https?:\/\//i.test(trimmed)) return trimmed
    // Relative env value (e.g. "/api") — use it verbatim.
    return trimmed
  }
  if (typeof window === 'undefined') return '/api'
  if (import.meta.env.DEV) {
    return 'http://localhost:8000'
  }
  return '/api'
}

/**
 * Always re-resolved on access. Cheap (one hostname read) and immune to
 * stale-build artefacts where a constant was captured before the user
 * switched tabs / devices.
 */
export const BASE: string = resolveApiBase()

/** Re-evaluate on every call. Lets HMR / SPA navigation pick up a
 *  freshly-opened tab without stale closures. */
export function getApiBase(): string {
  return resolveApiBase()
}

// ─── Auth-event bus ─────────────────────────────────────────────────────────────
//
// The 401 interceptor below dispatches this event so React components can react
// without us needing a global state library.

export const AUTH_LOGOUT_EVENT = 'soulcontext:auth:logout'

function dispatchLogout() {
  window.dispatchEvent(new CustomEvent(AUTH_LOGOUT_EVENT))
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

export function buildApiUrl(path: string): string {
  const base = getApiBase().replace(/\/+$/, '')
  const endpoint = base.endsWith('/api') ? path.replace(/^\/api(?=\/)/, '') : path
  return base + endpoint
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit & { params?: Record<string, string | number> },
): Promise<T> {
  let url = buildApiUrl(path)
  if (init?.params) {
    const qs = new URLSearchParams(
      Object.fromEntries(
        Object.entries(init.params).map(([k, v]) => [k, String(v)]),
      ),
    ).toString()
    url += `?${qs}`
  }
  const { params: _params, ...fetchInit } = init ?? {}

  // ── Request interceptor: attach Bearer token if we have one.
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(fetchInit.headers as Record<string, string> | undefined),
  }
  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(url, {
    ...fetchInit,
    headers,
  } as RequestInit)

  // ── Response interceptor: handle 401 → clear token + notify.
  if (res.status === 401) {
    clearToken()
    dispatchLogout()
  }

  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const body = (await res.json()) as { detail?: string }
      msg = body.detail ?? msg
    } catch {
      /* ignore parse errors */
    }
    throw new Error(msg)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

// ─── Health ────────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>('/health')
}

// ─── Entries ──────────────────────────────────────────────────────────────────

function localEntryTime(entry: Entry): Entry {
  if (entry.created_at_epoch == null) return entry
  const date = new Date(entry.created_at_epoch * 1000)
  const pad = (n: number) => String(n).padStart(2, '0')
  const day = [date.getFullYear(), pad(date.getMonth() + 1), pad(date.getDate())].join('-')
  const time = [date.getHours(), date.getMinutes(), date.getSeconds()].map(pad).join(':')
  return { ...entry, created_at: day + ' ' + time }
}

export async function listEntries(
  limit = 80,
  offset = 0,
): Promise<Entry[]> {
  return apiFetch<Entry[]>('/api/entries', {
    params: { limit, offset },
  }).then(rows => rows.map(localEntryTime))
}

export async function loadJournalWindow(start: string, end: string, signal: AbortSignal) {
  const result = await apiFetch<{entries: Entry[], has_earlier: boolean}>('/api/journal/window', {
    params: {start, end}, signal,
  })
  return { entries: result.entries.map(localEntryTime), hasEarlier: result.has_earlier }
}

export async function createEntry(body: EntryCreate): Promise<Entry> {
  return apiFetch<Entry>('/api/entries', {
    method: 'POST',
    body: JSON.stringify(body),
  }).then(localEntryTime)
}

export async function deleteEntry(entryId: number): Promise<void> {
  return apiFetch<void>(`/api/entries/${entryId}`, { method: 'DELETE' })
}

export async function updateEntry(
  entryId: number,
  body: EntryUpdate,
): Promise<Entry> {
  return apiFetch<Entry>(`/api/entries/${entryId}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

// ─── Chat (multi-conversation) ────────────────────────────────────────────────

export async function chatNonStream(
  message: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }>,
  conversationId?: string,
  anchorEntryId?: number,
): Promise<{ reply: string; conversation_id?: string }> {
  return apiFetch<{ reply: string; conversation_id?: string }>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      history: history.map((m) => ({ role: m.role, content: m.content })),
      ...(conversationId ? { conversation_id: conversationId } : {}),
      ...(anchorEntryId ? { anchor_entry_id: anchorEntryId } : {}),
    }),
  })
}

export async function getChatHistory(
  limit = 50,
  offset = 0,
): Promise<ChatHistoryResponse> {
  // Legacy endpoint — kept for backwards compatibility. Newer UI should
  // call `getConversationMessages` against the active conversation id.
  return apiFetch<ChatHistoryResponse>('/api/chat/history', {
    params: { limit, offset },
  })
}

export async function clearChatHistory(): Promise<void> {
  return apiFetch<void>('/api/chat/history', { method: 'DELETE' })
}

// ─── Conversations ─────────────────────────────────────────────────────────────

export async function listConversations(
  page = 1,
  pageSize = 30,
): Promise<ConversationListResponse> {
  return apiFetch<ConversationListResponse>('/api/conversations', {
    params: { page, page_size: pageSize },
  })
}

export async function createConversation(
  title?: string,
  anchorEntryId?: number,
): Promise<Conversation> {
  return apiFetch<Conversation>('/api/conversations', {
    method: 'POST',
    body: JSON.stringify({
      ...(title ? { title } : {}),
      ...(anchorEntryId ? { anchor_entry_id: anchorEntryId } : {}),
    }),
  })
}

export async function getConversationMessages(
  conversationId: string,
  limit = 200,
  offset = 0,
): Promise<ChatHistoryResponse> {
  return apiFetch<ChatHistoryResponse>(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
    { params: { limit, offset } },
  )
}

export async function renameConversation(
  conversationId: string,
  title: string,
): Promise<Conversation> {
  return apiFetch<Conversation>(
    `/api/conversations/${encodeURIComponent(conversationId)}`,
    {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    },
  )
}

export async function deleteConversation(conversationId: string): Promise<void> {
  return apiFetch<void>(
    `/api/conversations/${encodeURIComponent(conversationId)}`,
    { method: 'DELETE' },
  )
}

// ─── SSE stream (browser only) ────────────────────────────────────────────────

export interface SSEStreamOptions {
  onChunk: (text: string) => void
  onDone: () => void
  onError: (err: Error) => void
}

/**
 * SSE streaming via fetch + ReadableStream.
 * Manually attaches the Authorization header (EventSource cannot),
 * and reports 401 the same way apiFetch does.
 */
export async function chatStreamFetch(
  message: string,
  history: Array<{ role: 'user' | 'assistant'; content: string }>,
  opts:
    | Omit<SSEStreamOptions, 'onDone'>
    | (SSEStreamOptions & { conversationId?: string; anchorEntryId?: number })
    & { conversationId?: string; anchorEntryId?: number },
): Promise<void> {
  const { conversationId, anchorEntryId, onChunk, onDone, onError } = opts as SSEStreamOptions & {
    conversationId?: string
    anchorEntryId?: number
  }
  const url = buildApiUrl('/api/chat/stream')
  try {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`

    const res = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message,
        history: history.map((m) => ({ role: m.role, content: m.content })),
        ...(conversationId ? { conversation_id: conversationId } : {}),
        ...(anchorEntryId ? { anchor_entry_id: anchorEntryId } : {}),
      }),
    })

    if (res.status === 401) {
      clearToken()
      dispatchLogout()
      throw new Error('HTTP 401')
    }

    if (!res.ok) {
      let msg = `HTTP ${res.status}`
      try {
        const body = (await res.json()) as { detail?: string }
        msg = body.detail ?? msg
      } catch {
        /* ignore */
      }
      throw new Error(msg)
    }

    if (!res.body) throw new Error('No response body')

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data:')) continue
        const raw = line.slice(5).trim()
        if (!raw) continue

        try {
          const payload = JSON.parse(raw) as {
            content?: string
            finished?: boolean
          }
          if (payload.content !== undefined) onChunk(payload.content)
          if (payload.finished) {
            onDone?.()
            return
          }
        } catch {
          /* ignore malformed */
        }
      }
    }
    onDone?.()
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)))
  }
}

// ─── Poetry ────────────────────────────────────────────────────────────────────

export async function listMemories(
  layer?: string,
  entryId?: number,
  limit = 50,
): Promise<MemoryRecord[]> {
  return apiFetch<MemoryRecord[]>('/api/memories', {
    params: {
      limit,
      ...(layer ? { layer } : {}),
      ...(entryId ? { entry_id: entryId } : {}),
    },
  })
}

export async function listPoetry(limit = 10): Promise<PoetryReport[]> {
  return apiFetch<PoetryReport[]>('/api/poetry', { params: { limit } })
}

export async function generatePoetry(): Promise<PoetryReport> {
  return apiFetch<PoetryReport>('/api/poetry/generate', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}
