/** Chat streaming + history API for the Darsyar UI (Phase 6). */
import { apiFetch, getAccessToken } from './client'
import { readSseStream } from './sse'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  status: 'streaming' | 'complete' | 'partial' | 'error'
  errorCode?: string
  sequence?: number
}

export type ConversationSummary = {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export type ChatStreamHandlers = {
  onAck?: (info: { conversationId: string; messageId: string }) => void
  onDelta?: (text: string) => void
  onDone?: (status?: string) => void
  onError?: (code: string, message: string) => void
  signal?: AbortSignal
}

export type ConversationMessagesPage = {
  items: ChatMessage[]
  nextAfterSequence: number | null
}

function mapHistoryMessage(message: {
  id: string
  role: string
  content: string
  status: string
  sequence?: number
}): ChatMessage {
  return {
    id: message.id,
    role: message.role === 'user' ? 'user' : 'assistant',
    content: message.content,
    status: message.status === 'failed' || message.status === 'cancelled'
      ? 'error'
      : message.status === 'partial'
        ? 'partial'
        : message.status === 'streaming'
          ? 'streaming'
          : 'complete',
    errorCode: message.status === 'failed' || message.status === 'cancelled' ? message.status : undefined,
    sequence: message.sequence,
  }
}

export function makeClientRequestId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(8))
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

/**
 * Stream one idempotent turn. The request ID is supplied by the caller and must be
 * reused for any reconnect; generating a new ID would create a second billable turn.
 */
export async function streamChat(
  content: string,
  conversationId: string | null,
  clientRequestId: string,
  handlers: ChatStreamHandlers,
): Promise<void> {
  const headers = new Headers({ Accept: 'text/event-stream', 'Content-Type': 'application/json' })
  const auth = getAccessToken()
  if (auth) headers.set('Authorization', `Bearer ${auth}`)

  const body = JSON.stringify({
    conversation_id: conversationId || null,
    content,
    client_request_id: clientRequestId,
  })

  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers,
    body,
    credentials: 'include',
    signal: handlers.signal,
  })

  if (!response.ok) {
    let payload: { code?: string; message?: string } = {}
    try { payload = await response.json() as typeof payload } catch { /* non-JSON gateway response */ }
    handlers.onError?.(payload.code || 'http_error', payload.message || 'Request failed')
    return
  }

  let receivedDone = false
  await readSseStream(response, (message) => {
    let payload: {
      request_id?: string
      conversation_id?: string
      message_id?: string
      content?: string
      code?: string
      message?: string
      status?: string
    }
    try {
      payload = JSON.parse(message.data)
    } catch {
      return
    }
    switch (message.event) {
      case 'ack':
        if (payload.conversation_id && payload.message_id) {
          handlers.onAck?.({ conversationId: payload.conversation_id, messageId: payload.message_id })
        }
        break
      case 'delta':
        if (typeof payload.content === 'string') handlers.onDelta?.(payload.content)
        break
      case 'done':
        receivedDone = true
        handlers.onDone?.(payload.status)
        break
      case 'error':
        handlers.onError?.(payload.code || 'stream_error', payload.message || 'Stream error')
        break
    }
  }, handlers.signal)

  if (!handlers.signal?.aborted && !receivedDone) {
    throw new Error('SSE stream ended before a terminal done event')
  }
}

/** Fetch the current user's conversation history with bounded pagination. */
export async function listConversations(
  limit = 50,
  offset = 0,
  query = '',
): Promise<{ items: ConversationSummary[]; limit: number; offset: number; total: number }> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) })
  if (query.trim()) params.set('q', query.trim())
  return apiFetch<{ items: ConversationSummary[]; limit: number; offset: number; total: number }>(
    `/conversations?${params.toString()}`,
  )
}

/** Fetch an owner-scoped page of conversation history. */
export async function fetchConversationMessages(
  conversationId: string,
  limit = 100,
  afterSequence?: number,
): Promise<ConversationMessagesPage> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (afterSequence !== undefined) params.set('after_sequence', String(afterSequence))
  const data = await apiFetch<{
    items: Array<{ id: string; role: string; content: string; status: string; sequence: number }>
    next_after_sequence: number | null
  }>(`/conversations/${conversationId}/messages?${params.toString()}`)
  return {
    items: (data.items || []).map(mapHistoryMessage),
    nextAfterSequence: data.next_after_sequence,
  }
}

/** Poll one durable message state after a stream disconnect/replay. */
export async function fetchConversationMessage(
  conversationId: string,
  messageId: string,
  signal?: AbortSignal,
): Promise<ChatMessage> {
  const data = await apiFetch<{
    id: string
    role: string
    content: string
    status: string
    sequence: number
  }>(`/conversations/${conversationId}/messages/${messageId}`, { signal })
  return mapHistoryMessage(data)
}
