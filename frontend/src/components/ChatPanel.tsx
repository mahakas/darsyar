import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  fetchConversationMessage,
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

type PendingTurn = {
  content: string
  clientRequestId: string
  conversationId: string | null
  temporaryAssistantId: string
  serverMessageId: string | null
}

const RECOVERY_POLL_ATTEMPTS = 60
const RECOVERY_POLL_INTERVAL_MS = 1500

function delay(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds))
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
  const [recovering, setRecovering] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyLoadingMore, setHistoryLoadingMore] = useState(false)
  const [historyNextSequence, setHistoryNextSequence] = useState<number | null>(null)
  const [historyError, setHistoryError] = useState('')
  const [conversationId, setConversationId] = useState<string | null>(initialConversationId)
  const abortRef = useRef<AbortController | null>(null)
  const pendingTurnRef = useRef<PendingTurn | null>(null)

  useEffect(() => {
    let active = true
    abortRef.current?.abort()
    abortRef.current = null
    pendingTurnRef.current = null
    setBusy(false)
    setRecovering(false)
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

  const updateTurnMessage = useCallback((
    turn: PendingTurn,
    patch: Partial<ChatMessage>,
    contentAppend?: string,
  ) => {
    setMessages((prev) => {
      const targetId = turn.serverMessageId || turn.temporaryAssistantId
      const index = prev.findIndex((message) =>
        message.id === targetId || message.id === turn.temporaryAssistantId,
      )
      const current = index >= 0 ? prev[index] : {
        id: targetId,
        role: 'assistant' as const,
        content: '',
        status: 'streaming' as const,
      }
      const nextMessage: ChatMessage = {
        ...current,
        ...patch,
        id: targetId,
      }
      if (contentAppend !== undefined) {
        nextMessage.content = (current.content || '') + contentAppend
      }
      if (index < 0) return [...prev, nextMessage]
      const next = [...prev]
      next[index] = nextMessage
      return next
    })
  }, [])

  const applyServerMessage = useCallback((turn: PendingTurn, message: ChatMessage) => {
    turn.serverMessageId = message.id
    updateTurnMessage(turn, {
      id: message.id,
      content: message.content,
      status: message.status,
      errorCode: message.errorCode,
      sequence: message.sequence,
    })
  }, [updateTurnMessage])

  const pollUntilTerminal = async (
    turn: PendingTurn,
    signal: AbortSignal,
  ): Promise<boolean> => {
    if (!turn.conversationId || !turn.serverMessageId) return false
    setRecovering(true)
    for (let attempt = 0; attempt < RECOVERY_POLL_ATTEMPTS; attempt += 1) {
      if (signal.aborted) return false
      await delay(RECOVERY_POLL_INTERVAL_MS)
      if (signal.aborted) return false
      try {
        const message = await fetchConversationMessage(
          turn.conversationId,
          turn.serverMessageId,
          signal,
        )
        applyServerMessage(turn, message)
        if (message.status !== 'streaming') {
          pendingTurnRef.current = null
          setRecovering(false)
          onConversationChange?.(turn.conversationId)
          return true
        }
      } catch {
        // A transient API/network failure must not discard the idempotency key.
      }
    }
    setRecovering(false)
    return false
  }

  const runTurn = async (turn: PendingTurn, retryOnDisconnect: boolean): Promise<void> => {
    if (!turn.clientRequestId) return
    setBusy(true)
    setHistoryError('')
    setRecovering(false)
    updateTurnMessage(turn, { status: 'streaming', errorCode: undefined })
    const controller = new AbortController()
    abortRef.current = controller
    let terminalStatus: string | undefined
    let streamError: { code: string; message: string } | null = null

    try {
      await streamChat(turn.content, turn.conversationId, turn.clientRequestId, {
        signal: controller.signal,
        onAck: ({ conversationId: cid, messageId }) => {
          turn.conversationId = cid
          turn.serverMessageId = messageId
          setConversationId(cid)
          updateTurnMessage(turn, { id: messageId, content: '', status: 'streaming', errorCode: undefined })
        },
        onDelta: (delta) => updateTurnMessage(turn, {}, delta),
        onDone: (status) => {
          terminalStatus = status
        },
        onError: (code, message) => {
          streamError = { code, message }
        },
      })

      if (controller.signal.aborted) return

      if (terminalStatus === 'streaming') {
        const terminal = await pollUntilTerminal(turn, controller.signal)
        if (terminal) {
          setBusy(false)
          abortRef.current = null
          return
        }
        if (!controller.signal.aborted) {
          updateTurnMessage(turn, { status: 'streaming', errorCode: undefined })
          setBusy(false)
          abortRef.current = null
        }
        return
      }

      if (terminalStatus === 'completed' || terminalStatus === 'complete') {
        updateTurnMessage(turn, { status: 'complete', errorCode: undefined })
        pendingTurnRef.current = null
      } else if (terminalStatus === 'partial') {
        updateTurnMessage(turn, { status: 'partial', errorCode: undefined })
        pendingTurnRef.current = null
      } else if (terminalStatus === 'failed' || terminalStatus === 'cancelled') {
        updateTurnMessage(turn, { status: 'error', errorCode: streamError?.code || terminalStatus })
        pendingTurnRef.current = null
      } else if (streamError) {
        updateTurnMessage(turn, { status: 'error', errorCode: streamError.code })
        pendingTurnRef.current = null
      } else {
        throw new Error('SSE response did not report a terminal status')
      }

      setBusy(false)
      abortRef.current = null
      if (turn.conversationId) onConversationChange?.(turn.conversationId)
    } catch {
      if (controller.signal.aborted) return
      if (retryOnDisconnect) {
        await delay(350)
        if (!controller.signal.aborted) {
          await runTurn(turn, false)
          return
        }
      }
      updateTurnMessage(turn, { status: 'error', errorCode: 'connection_interrupted' })
      setBusy(false)
      setRecovering(false)
      abortRef.current = null
      // Keep the same request ID and conversation binding so a manual resume is idempotent.
      pendingTurnRef.current = turn
    }
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const text = input.trim()
    if (!text || busy || historyLoading) return
    setInput('')
    const clientRequestId = makeClientRequestId()
    const turn: PendingTurn = {
      content: text,
      clientRequestId,
      conversationId,
      temporaryAssistantId: `assistant-${clientRequestId}`,
      serverMessageId: null,
    }
    pendingTurnRef.current = turn
    append({ id: clientRequestId, role: 'user', content: text, status: 'complete' })
    append({ id: turn.temporaryAssistantId, role: 'assistant', content: '', status: 'streaming' })
    await runTurn(turn, true)
  }

  const resume = async () => {
    const turn = pendingTurnRef.current
    if (!turn || busy) return
    await runTurn(turn, false)
  }

  const stop = () => {
    abortRef.current?.abort()
    abortRef.current = null
    const turn = pendingTurnRef.current
    if (turn) {
      updateTurnMessage(turn, { status: 'error', errorCode: 'cancelled' })
      pendingTurnRef.current = null
      if (turn.conversationId) onConversationChange?.(turn.conversationId)
    }
    setBusy(false)
    setRecovering(false)
  }

  return (
    <section className="chat-panel" aria-label={t('smartChat')}>
      <div className="chat-log" aria-live="polite" aria-busy={historyLoading || recovering}>
        {historyLoading && <p className="chat-empty">{t('historyLoading')}</p>}
        {recovering && <p className="chat-empty">{t('responseRecovering')}</p>}
        {historyError && <p className="form-error" role="alert">{historyError}</p>}
        {!historyLoading && messages.length === 0 && (
          <p className="chat-empty">{t('chatEmptyHint')}</p>
        )}
        {messages.map((message) => {
          const pending = pendingTurnRef.current
          const canResume = pending !== null
            && (message.id === pending.serverMessageId || message.id === pending.temporaryAssistantId)
            && (message.status === 'streaming' || message.errorCode === 'connection_interrupted')
          return (
            <article key={message.id} className={`chat-message role-${message.role} status-${message.status}`}>
              <div className="message-role">{message.role === 'user' ? t('you') : t('assistant')}</div>
              <div className="message-content">{message.content || (message.status === 'streaming' ? '…' : '')}</div>
              {message.status === 'error' && <div className="message-error">{message.errorCode}</div>}
              {message.status === 'partial' && <div className="message-status">{t('partialResponse')}</div>}
              {canResume && (
                <button
                  type="button"
                  className="history-item history-messages-more"
                  onClick={() => { void resume() }}
                  disabled={busy}
                >
                  {t('resumeResponse')}
                </button>
              )}
            </article>
          )
        })}
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
            {busy && !recovering && <button type="button" className="stop-button" onClick={stop}>{t('stop')}</button>}
            <button className="send-button" type="submit" disabled={busy || historyLoading || !input.trim()} aria-label={t('sendQuestion')}>↑</button>
          </div>
        </div>
      </form>
    </section>
  )
}
