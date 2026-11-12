import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { getMyProfile, logout, updateSelectedGrade, type SessionUser } from './api/auth'
import { listConversations, type ConversationSummary } from './api/chat'
import { apiFetch } from './api/client'
import AuthPanel from './components/AuthPanel'
import ChatPanel from './components/ChatPanel'

type HealthState = 'checking' | 'connected' | 'disconnected'
type View = 'chat' | 'welcome'
type SessionState = 'loading' | 'signed_out' | 'signed_in'

const gradeOptions = Array.from({ length: 12 }, (_, index) => index + 1)

export default function App() {
  const { t, i18n } = useTranslation()
  const [health, setHealth] = useState<HealthState>('checking')
  const [view, setView] = useState<View>('welcome')
  const [sessionState, setSessionState] = useState<SessionState>('loading')
  const [user, setUser] = useState<SessionUser | null>(null)
  const [gradeDraft, setGradeDraft] = useState('')
  const [gradeSaving, setGradeSaving] = useState(false)
  const [profileError, setProfileError] = useState('')
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [historyQuery, setHistoryQuery] = useState('')
  const [historyVersion, setHistoryVersion] = useState(0)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyLoadingMore, setHistoryLoadingMore] = useState(false)
  const [historyTotal, setHistoryTotal] = useState(0)
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null)

  useEffect(() => {
    const language = i18n.resolvedLanguage || 'fa'
    document.documentElement.lang = language
    document.documentElement.dir = language === 'en' ? 'ltr' : 'rtl'
  }, [i18n, i18n.resolvedLanguage])

  useEffect(() => {
    let active = true
    void getMyProfile()
      .then((profile) => {
        if (!active) return
        setUser(profile)
        setSessionState('signed_in')
      })
      .catch(() => {
        if (!active) return
        setUser(null)
        setSessionState('signed_out')
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const checkHealth = async () => {
      try {
        await apiFetch<{ status: string }>('/health/live', { signal: controller.signal })
        setHealth('connected')
      } catch {
        if (!controller.signal.aborted) setHealth('disconnected')
      }
    }
    void checkHealth()
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (sessionState !== 'signed_in' || !user || user.selected_grade === null) {
      setConversations([])
      setHistoryTotal(0)
      setHistoryLoading(false)
      setHistoryLoadingMore(false)
      return
    }
    let active = true
    setHistoryLoading(true)
    void listConversations(50, 0, historyQuery)
      .then((page) => {
        if (active) {
          setConversations(page.items)
          setHistoryTotal(page.total)
        }
      })
      .catch(() => {
        if (active) setConversations([])
      })
      .finally(() => {
        if (active) setHistoryLoading(false)
      })
    return () => {
      active = false
    }
  }, [sessionState, user?.id, user?.selected_grade, historyVersion, historyQuery])

  const changeLanguage = (language: string) => {
    void i18n.changeLanguage(language)
  }

  const handleGradeSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const grade = Number(gradeDraft)
    if (!Number.isInteger(grade) || grade < 1 || grade > 12 || gradeSaving) return
    setGradeSaving(true)
    setProfileError('')
    try {
      const updated = await updateSelectedGrade(grade)
      setUser(updated)
      setView('welcome')
    } catch {
      setProfileError(t('profileError'))
    } finally {
      setGradeSaving(false)
    }
  }

  const handleLogout = async () => {
    try {
      await logout()
    } finally {
      setUser(null)
      setConversations([])
      setSelectedConversationId(null)
      setSessionState('signed_out')
      setGradeDraft('')
      setView('welcome')
    }
  }

  const handleAuthenticated = (authenticatedUser: SessionUser) => {
    setUser(authenticatedUser)
    setSessionState('signed_in')
  }

  const startNewChat = () => {
    setSelectedConversationId(null)
    setView('chat')
  }

  const selectConversation = (conversationId: string) => {
    setSelectedConversationId(conversationId)
    setView('chat')
  }

  const loadMoreConversations = async () => {
    if (historyLoadingMore || conversations.length >= historyTotal) return
    setHistoryLoadingMore(true)
    try {
      const page = await listConversations(50, conversations.length, historyQuery)
      setConversations((current) => [...current, ...page.items])
      setHistoryTotal(page.total)
    } catch {
      setProfileError(t('historyLoadError'))
    } finally {
      setHistoryLoadingMore(false)
    }
  }

  const handleConversationChange = (conversationId: string | null) => {
    setSelectedConversationId(conversationId)
    if (conversationId) setHistoryVersion((version) => version + 1)
  }

  const filteredConversations = conversations

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Main navigation">
        <div className="brand-mark" aria-hidden="true">د</div>
        <div className="brand-copy"><strong>{t('appName')}</strong><span>AI Learning</span></div>
        <button className="new-chat" type="button" onClick={startNewChat} disabled={sessionState !== 'signed_in' || user?.selected_grade === null}>＋ <span>{t('newChat')}</span></button>
        <div className="side-label">{t('learningSpace')}</div>
        <button className={'nav-item ' + (view === 'chat' ? 'active' : '')} type="button" onClick={() => setView('chat')} disabled={sessionState !== 'signed_in' || user?.selected_grade === null}>✳ <span>{t('smartChat')}</span></button>
        {sessionState === 'signed_in' && user && user.selected_grade !== null && (
          <section className="conversation-history" aria-label={t('conversationHistory')}>
            <div className="side-label">{t('conversationHistory')}</div>
            <label className="sr-only" htmlFor="history-search">{t('searchHistory')}</label>
            <input
              id="history-search"
              className="history-search"
              type="search"
              value={historyQuery}
              onChange={(event) => setHistoryQuery(event.target.value)}
              placeholder={t('searchHistory')}
            />
            {historyLoading && <span className="history-hint">{t('historyLoading')}</span>}
            {!historyLoading && filteredConversations.length === 0 && (
              <span className="history-hint">{t('historyEmpty')}</span>
            )}
            {filteredConversations.map((conversation) => (
              <button
                key={conversation.id}
                className={'history-item ' + (selectedConversationId === conversation.id ? 'active' : '')}
                type="button"
                onClick={() => selectConversation(conversation.id)}
                title={conversation.title || t('untitledConversation')}
              >
                {conversation.title || t('untitledConversation')}
              </button>
            ))}
            {conversations.length < historyTotal && (
              <button
                className="history-item"
                type="button"
                onClick={() => { void loadMoreConversations() }}
                disabled={historyLoadingMore}
              >
                {historyLoadingMore ? t('historyLoadingMore') : t('loadOlderConversations')}
              </button>
            )}
          </section>
        )}
        <button className="nav-item" type="button" disabled>▤ <span>{t('privateTeacher')} <small>{t('soon')}</small></span></button>
        <button className="nav-item" type="button" disabled>▧ <span>{t('projects')} <small>{t('soon')}</small></span></button>
        <div className="sidebar-bottom"><div className="avatar">د</div><div><strong>{user?.name || user?.phone || t('environment')}</strong><span>{user ? t('signedIn') : t('preview')}</span></div></div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-title"><span className="status-dot" />{t('foundation')}</div>
          <div className="topbar-actions">
            <label className="sr-only" htmlFor="language">{t('language')}</label>
            <select id="language" aria-label={t('language')} value={i18n.resolvedLanguage || 'fa'} onChange={(event) => changeLanguage(event.target.value)}>
              <option value="fa">فارسی</option><option value="en">English</option><option value="ar">العربية</option>
            </select>
            <span className={'health-pill ' + health} role="status">{health === 'checking' ? t('checking') : health === 'connected' ? t('connected') : t('disconnected')}</span>
            {sessionState === 'signed_in' && <button className="text-button" type="button" onClick={() => { void handleLogout() }}>{t('signOut')}</button>}
          </div>
        </header>

        {sessionState === 'loading' && (
          <section className="welcome-area" aria-live="polite"><p>{t('sessionLoading')}</p></section>
        )}

        {sessionState === 'signed_out' && <AuthPanel onAuthenticated={handleAuthenticated} />}

        {sessionState === 'signed_in' && user && user.selected_grade === null && (
          <section className="profile-setup" aria-labelledby="grade-title">
            <div className="orb" aria-hidden="true"><span>د</span></div>
            <p className="eyebrow">{t('tagline')}</p>
            <h1 id="grade-title">{t('selectGradeTitle')}</h1>
            <p className="intro-copy">{t('selectGradeIntro')}</p>
            <form className="account-form" onSubmit={handleGradeSave}>
              <label htmlFor="profile-grade">{t('chooseGrade')}</label>
              <select id="profile-grade" value={gradeDraft} onChange={(event) => setGradeDraft(event.target.value)} required disabled={gradeSaving}>
                <option value="" disabled>—</option>
                {gradeOptions.map((grade) => <option key={grade} value={grade}>{grade}</option>)}
              </select>
              <button className="send-button account-submit" type="submit" disabled={gradeSaving || !gradeDraft}>
                {gradeSaving ? t('savingGrade') : t('saveGrade')}
              </button>
              {profileError && <p className="form-error" role="alert">{profileError}</p>}
            </form>
          </section>
        )}

        {sessionState === 'signed_in' && user && user.selected_grade !== null && (
          view === 'chat' ? (
            <ChatPanel
              key={selectedConversationId || 'new-conversation'}
              selectedGrade={user.selected_grade}
              initialConversationId={selectedConversationId}
              onConversationChange={handleConversationChange}
            />
          ) : (
            <section className="welcome-area">
              <div className="orb" aria-hidden="true"><span>د</span></div>
              <p className="eyebrow">{t('tagline')}</p>
              <h1>{t('welcome')}</h1>
              <p className="intro-copy">{t('intro')}</p>
              <p className="grade-control">{t('currentGrade')}: <strong>{user.selected_grade}</strong></p>
              <button className="send-button start-chat" type="button" onClick={() => setView('chat')}>{t('newChat')}</button>
              <div className="feature-grid">
                <article className="feature-card"><span className="feature-icon violet">⌕</span><h2>{t('groundedTitle')}</h2><p>{t('groundedDesc')}</p></article>
                <article className="feature-card"><span className="feature-icon teal">✓</span><h2>{t('safeTitle')}</h2><p>{t('safeDesc')}</p></article>
                <article className="feature-card"><span className="feature-icon amber">◇</span><h2>{t('privacyTitle')}</h2><p>{t('privacyDesc')}</p></article>
              </div>
            </section>
          )
        )}
        <footer className="footer-note">{t('appName')} · {t('footerNote')} · {t('private')}</footer>
      </main>
    </div>
  )
}
