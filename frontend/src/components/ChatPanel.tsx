import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  fetchConversationMessages,
  streamChat,
  makeClientRequestId,
  type ChatMessage,
} from '../api/chat'

export type ChatPanelProps = {
  selectedGrade: number
  initialConversationId?: string | null
  onConversationChange?: (conversationId: string | null) => void
}

export default function ChatPanel({
  selectedGrade,
  initialConversationId = null,
  onConversationChange,
}: ChatPanelProps) {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyLoadingMore, setHistoryLoadingMore] = useState(false)
  const [historyNextSequence, setHistoryNextSequence] = useState<number | null>(null)
  const [historyError, setHistoryError] = useState('')
  const [conversationId, setConversationId] = useState<string | null>(initialConversationId)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    let active = true
    abortRef.current?.abort()
    abortRef.current = null
    setBusy(false)
    setHistoryError('')
    setInput('')
    setConversationId(initialConversationId)
    if (!initialConversationId) {
      setMessages([])
      setHistoryNextSequence(null)
      setHistoryLoading(false)
      return () => {
        active = false
      }
    }
    setMessages([])
    setHistoryLoading(true)
    void fetchConversationMessages(initialConversationId)
      .then((page) => {
        if (active) {
          setMessages(page.items)
          setHistoryNextSequence(page.nextAfterSequence)
        }
      })
      .catch(() => {
        if (active) setHistoryError(t('historyLoadError'))
      })
      .finally(() => {
        if (active) setHistoryLoading(false)
      })
    return () => {
      active = false
    }
  }, [initialConversationId, t])

  const loadMoreMessages = async () => {
    if (!conversationId || historyNextSequence === null || historyLoadingMore) return
    setHistoryLoadingMore(true)
    try {
      const page = await fetchConversationMessages(conversationId, 100, historyNextSequence)
      setMessages((current) => [...current, ...page.items])
      setHistoryNextSequence(page.nextAfterSequence)
    } catch {
      setHistoryError(t('historyLoadError'))
    } finally {
      setHistoryLoadingMore(false)
    }
  }

  useEffect(() => () => {
    abortRef.current?.abort()
  }, [])

  const append = useCallback((msg: ChatMessage) => {
    setMessages((prev) => [...prev, msg])
  }, [])

  const updateLast = useCallback((patch: Partial<ChatMessage>, contentAppend?: string) => {
    setMessages((prev) => {
      const next = [...prev]
      const last = next[next.length - 1]
      if (last && last.role === 'assistant') {
        const merged = { ...last, ...patch }
        if (contentAppend !== undefined) merged.content = (last.content || '') + contentAppend
        next[next.length - 1] = merged
      }
      return next
    })
  }, [])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const text = input.trim()
    if (!text || busy || historyLoading) return
    setInput('')
    append({ id: makeClientRequestId(), role: 'user', content: text, status: 'complete' })
    append({ id: `assistant-${Date.now()}`, role: 'assistant', content: '', status: 'streaming' })
    setBusy(true)

    const controller = new AbortController()
    abortRef.current = controller
    let assistantId = ''
    let activeConversationId = conversationId

    try {
      await streamChat(text, conversationId, {
        signal: controller.signal,
        onAck: ({ conversationId: cid, messageId }) => {
          activeConversationId = cid
          setConversationId(cid)
          assistantId = messageId
        },
        onDelta: (delta) => updateLast({}, delta),
        onDone: (status) => {
          const finalStatus = status === 'partial'
            ? 'partial'
            : status === 'failed' || status === 'cancelled'
              ? 'error'
              : 'complete'
          updateLast({ id: assistantId || `assistant-${Date.now()}`, status: finalStatus })
          setBusy(false)
          abortRef.current = null
          if (activeConversationId) onConversationChange?.(activeConversationId)
        },
        onError: (code, message) => {
          updateLast({ status: 'error', errorCode: code, content: message })
          setBusy(false)
          abortRef.current = null
          if (activeConversationId) onConversationChange?.(activeConversationId)
        },
      })
    } catch {
      if (controller.signal.aborted) return
      updateLast({ status: 'error', errorCode: 'network_error', content: t('networkError') })
      setBusy(false)
      abortRef.current = null
      if (activeConversationId) onConversationChange?.(activeConversationId)
    }
  }

  const stop = () => {
    abortRef.current?.abort()
    abortRef.current = null
    updateLast({ status: 'error', errorCode: 'cancelled', content: t('stopped') })
    setBusy(false)
    if (conversationId) onConversationChange?.(conversationId)
  }

  return (
    <section className="chat-panel" aria-label={t('smartChat')}>
      <div className="chat-log" aria-live="polite" aria-busy={historyLoading}>
        {historyLoading && <p className="chat-empty">{t('historyLoading')}</p>}
        {historyError && <p className="form-error" role="alert">{historyError}</p>}
        {!historyLoading && messages.length === 0 && (
          <p className="chat-empty">{t('chatEmptyHint')}</p>
        )}
        {messages.map((message) => (
          <article key={message.id} className={`chat-message role-${message.role} status-${message.status}`}>
            <div className="message-role">{message.role === 'user' ? t('you') : t('assistant')}</div>
            <div className="message-content">{message.content || (message.status === 'streaming' ? '…' : '')}</div>
            {message.status === 'error' && <div className="message-error">{message.errorCode}</div>}
            {message.status === 'partial' && <div className="message-status">{t('partialResponse')}</div>}
          </article>
        ))}
        {historyNextSequence !== null && (
          <button
            className="history-item history-messages-more"
            type="button"
            onClick={() => { void loadMoreMessages() }}
            disabled={historyLoadingMore || historyLoading}
          >
            {historyLoadingMore ? t('historyLoadingMore') : t('loadMoreMessages')}
          </button>
        )}
      </div>
      <form className="composer" onSubmit={submit}>
        <label className="sr-only" htmlFor="chat-input">{t('askPlaceholder')}</label>
        <textarea
          id="chat-input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={t('askPlaceholder')}
          rows={2}
          disabled={busy || historyLoading}
        />
        <div className="composer-footer">
          <span className="grade-control" aria-label={t('currentGrade')}>
            {t('currentGrade')}: <strong>{selectedGrade}</strong>
          </span>
          <div className="chat-actions">
            {busy && <button type="button" className="stop-button" onClick={stop}>{t('stop')}</button>}
            <button className="send-button" type="submit" disabled={busy || historyLoading || !input.trim()} aria-label={t('sendQuestion')}>↑</button>
          </div>
        </div>
      </form>
    </section>
  )
}
