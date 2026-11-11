import { useCallback, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  streamChat,
  makeClientRequestId,
  type ChatMessage,
} from '../api/chat'

export type ChatPanelProps = {
  accessTokenReader?: () => string | null
}

const gradeOptions = Array.from({ length: 12 }, (_, index) => index + 1)

export default function ChatPanel({ accessTokenReader }: ChatPanelProps) {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [grade, setGrade] = useState('7')
  const [busy, setBusy] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // expose token reader for api layer
  if (accessTokenReader) {
    ;(globalThis as { __darsyarAccessTokenReader?: () => string | null }).__darsyarAccessTokenReader = accessTokenReader
  }

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
    if (!text || busy) return
    setInput('')
    append({ id: makeClientRequestId(), role: 'user', content: text, status: 'complete' })
    append({ id: `assistant-${Date.now()}`, role: 'assistant', content: '', status: 'streaming' })
    setBusy(true)

    const controller = new AbortController()
    abortRef.current = controller

    let assistantId = ''
    await streamChat(text, Number(grade), conversationId, {
      signal: controller.signal,
      onAck: ({ conversationId: cid, messageId }) => {
        setConversationId(cid)
        assistantId = messageId
      },
      onDelta: (delta) => updateLast({}, delta),
      onDone: () => {
        updateLast({ id: assistantId || `assistant-${Date.now()}`, status: 'complete' })
        setBusy(false)
      },
      onError: (code, message) => {
        updateLast({ status: 'error', errorCode: code, content: message })
        setBusy(false)
      },
    })
  }

  const stop = () => {
    abortRef.current?.abort()
    setBusy(false)
  }

  return (
    <section className="chat-panel" aria-label={t('smartChat')}>
      <div className="chat-log" aria-live="polite">
        {messages.length === 0 && (
          <p className="chat-empty">{t('chatEmptyHint')}</p>
        )}
        {messages.map((message) => (
          <article key={message.id} className={`chat-message role-${message.role} status-${message.status}`}>
            <div className="message-role">{message.role === 'user' ? t('you') : t('assistant')}</div>
            <div className="message-content">{message.content || (message.status === 'streaming' ? '…' : '')}</div>
            {message.status === 'error' && <div className="message-error">{message.errorCode}</div>}
          </article>
        ))}
      </div>
      <form className="composer" onSubmit={submit}>
        <label className="sr-only" htmlFor="chat-input">{t('askPlaceholder')}</label>
        <textarea
          id="chat-input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={t('askPlaceholder')}
          rows={2}
        />
        <div className="composer-footer">
          <label className="grade-control">{t('chooseGrade')}
            <select value={grade} onChange={(event) => setGrade(event.target.value)} aria-label={t('chooseGrade')}>
              {gradeOptions.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <div className="chat-actions">
            {busy && <button type="button" className="stop-button" onClick={stop}>{t('stop')}</button>}
            <button className="send-button" type="submit" disabled={busy || !input.trim()} aria-label={t('sendQuestion')}>↑</button>
          </div>
        </div>
      </form>
    </section>
  )
}
