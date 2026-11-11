/** Chat streaming + history API for the Darsyar UI (Phase 6). */
import { apiFetch } from './client'
import { readSseStream } from './sse'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  status: 'streaming' | 'complete' | 'error'
  errorCode?: string
}

export type ChatStreamHandlers = {
  onAck?: (info: { conversationId: string; messageId: string }) => void
  onDelta?: (text: string) => void
  onDone?: () => void
  onError?: (code: string, message: string) => void
  signal?: AbortSignal
}

export function makeClientRequestId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(8))
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
}

/**
 * Stream a chat turn against POST /chat/stream (fetch-based SSE).
 * The access token is read from the in-memory reader registered on window.
 */
export async function streamChat(
  content: string,
  selectedGrade: number,
  conversationId: string | null,
  handlers: ChatStreamHandlers,
): Promise<void> {
  const headers = new Headers({ Accept: 'text/event-stream', 'Content-Type': 'application/json' })
  const access = (globalThis as { __darsyarAccessTokenReader?: () => string | null }).__darsyarAccessTokenReader
  const auth = access?.()
  if (auth) headers.set('Authorization', `Bearer ${auth}`)

  const body = JSON.stringify({
    conversation_id: conversationId || null,
    content,
    client_request_id: makeClientRequestId(),
    grade_level: selectedGrade,
  })

  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers,
    body,
    signal: handlers.signal,
  })

  if (!response.ok) {
    let payload: { code?: string; message?: string } = {}
    try { payload = await response.json() as typeof payload } catch { /* noop */ }
    handlers.onError?.(payload.code || 'http_error', payload.message || 'Request failed')
    return
  }

  await readSseStream(response, (message) => {
    let payload: {
      request_id?: string
      conversation_id?: string
      message_id?: string
      content?: string
      code?: string
      message?: string
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
        handlers.onDone?.()
        break
      case 'error':
        handlers.onError?.(payload.code || 'stream_error', payload.message || 'Stream error')
        break
    }
  }, handlers.signal)
}

/** Fetch conversation history (used to rehydrate a chat on reload). */
export async function fetchConversationMessages(conversationId: string): Promise<ChatMessage[]> {
  const data = await apiFetch<{ items: Array<{ id: string; role: string; content: string; status: string }> }>(
    `/conversations/${conversationId}/messages?limit=100`,
  )
  return (data.items || []).map((m) => ({
    id: m.id,
    role: m.role === 'user' ? 'user' : 'assistant',
    content: m.content,
    status: m.status === 'failed' ? 'error' : 'complete',
  }))
}
