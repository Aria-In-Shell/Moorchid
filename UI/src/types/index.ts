// Shared TypeScript types mirroring FastAPI Pydantic schemas

export type Mood = 'Joy' | 'Calm' | 'Neutral' | 'Low' | 'Anxious'

export type MemoryLayer = 'session' | 'event' | 'stage' | 'long_term'
export type StatementKind = 'user_statement' | 'model_inference'
export type MemorySource =
  | 'user'
  | 'pattern_agent'
  | 'soul_chat_agent'
  | 'poet_agent'
  | 'system'

export interface PatternAnalysis {
  emotion: Mood | string
  display_emotion?: string
  valence: number
  intensity: number
  tags: string[]
  themes: string[]
  events?: Array<{ summary: string; confidence: number }>
  inferences?: Array<{ claim: string; confidence: number }>
}

export interface Entry {
  id: number
  user_id: string
  content: string
  emotion: Mood | string
  tags: string[]
  created_at: string
  created_at_epoch?: number
  valence?: number
  intensity?: number
  analysis?: PatternAnalysis | null
}

export interface EntryCreate {
  content: string
  mood?: string
}

export interface EntryUpdate {
  content: string
  emotion: Mood
  tags: string[]
}

export interface MemoryRecord {
  id: string
  layer: MemoryLayer
  content: string
  summary?: string | null
  emotion?: string | null
  valence?: number | null
  intensity?: number | null
  tags: string[]
  themes: string[]
  source: MemorySource
  statement_kind: StatementKind
  confidence: number
  entry_id?: number | null
  conversation_id?: string | null
  created_at: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatHistoryItem {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatHistoryResponse {
  messages: ChatHistoryItem[]
}

export interface ChatRequest {
  message: string
  history?: ChatMessage[]
  conversation_id?: string
  anchor_entry_id?: number
}

export interface ChatResponse {
  reply: string
  conversation_id?: string
}

export interface SSEEvent {
  event: string
  data: string
}

export interface SSEChatMessage {
  content: string
  finished: boolean
}

export interface Conversation {
  id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
  anchor_entry_id?: number | null
}

export interface ConversationListResponse {
  conversations: Conversation[]
  page: number
  page_size: number
  total: number
}

export interface PoetryReport {
  id: number
  user_id: string
  title: string
  poetry_content: string
  quote: string
  quote_author: string
  activity?: string | null
  emotion_distribution: string
  created_at: string
}

export interface HealthStatus {
  status: 'ok'
  deepseek_enabled: boolean
  zhipuai_enabled: boolean
}

export type AppView = 'canvas' | 'chat' | 'poetry'
