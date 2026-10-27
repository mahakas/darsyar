import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from './api/client'

type HealthState = 'checking' | 'connected' | 'disconnected'

const gradeOptions = Array.from({ length: 12 }, (_, index) => index + 1)

export default function App() {
  const { t, i18n } = useTranslation()
  const [health, setHealth] = useState<HealthState>('checking')
  const [grade, setGrade] = useState('7')
  const [question, setQuestion] = useState('')

  useEffect(() => {
    const language = i18n.resolvedLanguage || 'fa'
    document.documentElement.lang = language
    document.documentElement.dir = language === 'en' ? 'ltr' : 'rtl'
  }, [i18n, i18n.resolvedLanguage])

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

  const changeLanguage = (language: string) => {
    void i18n.changeLanguage(language)
  }

  const submitQuestion = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    // Chat is intentionally not wired until the approved API/chat phase is implemented.
    setQuestion('')
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Main navigation">
        <div className="brand-mark" aria-hidden="true">د</div>
        <div className="brand-copy"><strong>{t('appName')}</strong><span>AI Learning</span></div>
        <button className="new-chat" type="button" disabled>＋ <span>{t('newChat')}</span></button>
        <div className="side-label">{t('learningSpace')}</div>
        <button className="nav-item active" type="button">✳ <span>{t('smartChat')}</span></button>
        <button className="nav-item" type="button" disabled>▤ <span>{t('privateTeacher')} <small>{t('soon')}</small></span></button>
        <button className="nav-item" type="button" disabled>▧ <span>{t('projects')} <small>{t('soon')}</small></span></button>
        <div className="sidebar-bottom"><div className="avatar">د</div><div><strong>{t('environment')}</strong><span>{t('preview')}</span></div></div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-title"><span className="status-dot" />{t('foundation')}</div>
          <div className="topbar-actions">
            <label className="sr-only" htmlFor="language">{t('language')}</label>
            <select id="language" aria-label={t('language')} value={i18n.resolvedLanguage || 'fa'} onChange={(event) => changeLanguage(event.target.value)}>
              <option value="fa">فارسی</option><option value="en">English</option><option value="ar">العربية</option>
            </select>
            <span className={`health-pill ${health}`} role="status">{health === 'checking' ? t('checking') : health === 'connected' ? t('connected') : t('disconnected')}</span>
          </div>
        </header>

        <section className="welcome-area">
          <div className="orb" aria-hidden="true"><span>د</span></div>
          <p className="eyebrow">{t('tagline')}</p>
          <h1>{t('welcome')}</h1>
          <p className="intro-copy">{t('intro')}</p>
          <form className="composer" onSubmit={submitQuestion}>
            <label className="sr-only" htmlFor="question">{t('askPlaceholder')}</label>
            <textarea id="question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={t('askPlaceholder')} rows={2} disabled aria-describedby="chat-coming-soon" />
            <div className="composer-footer">
              <label className="grade-control">{t('chooseGrade')}
                <select value={grade} onChange={(event) => setGrade(event.target.value)}>
                  {gradeOptions.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </label>
              <button className="send-button" type="submit" disabled aria-label={t('sendQuestion')}>↑</button>
            </div>
          </form>
          <p id="chat-coming-soon" className="coming-soon">{t('foundationNote')}</p>
          <div className="feature-grid">
            <article className="feature-card"><span className="feature-icon violet">⌕</span><h2>{t('groundedTitle')}</h2><p>{t('groundedDesc')}</p></article>
            <article className="feature-card"><span className="feature-icon teal">✓</span><h2>{t('safeTitle')}</h2><p>{t('safeDesc')}</p></article>
            <article className="feature-card"><span className="feature-icon amber">◇</span><h2>{t('privacyTitle')}</h2><p>{t('privacyDesc')}</p></article>
          </div>
        </section>
        <footer className="footer-note">{t('appName')} · {t('footerNote')} · {t('private')}</footer>
      </main>
    </div>
  )
}
