import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../api/client'
import { requestOtp, verifyOtp, type SessionUser } from '../api/auth'

type AuthPanelProps = {
  onAuthenticated: (user: SessionUser) => void
}

type Step = 'phone' | 'otp'

export default function AuthPanel({ onAuthenticated }: AuthPanelProps) {
  const { t } = useTranslation()
  const [step, setStep] = useState<Step>('phone')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (step === 'phone') {
        await requestOtp(phone.trim())
        setStep('otp')
      } else {
        const user = await verifyOtp(phone.trim(), code.trim())
        onAuthenticated(user)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('loginError'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="auth-panel" aria-labelledby="auth-title">
      <div className="orb" aria-hidden="true"><span>د</span></div>
      <p className="eyebrow">{t('tagline')}</p>
      <h1 id="auth-title">{t('loginTitle')}</h1>
      <p className="intro-copy">{t('loginIntro')}</p>
      <form className="account-form" onSubmit={submit}>
        {step === 'phone' ? (
          <>
            <label htmlFor="login-phone">{t('phoneLabel')}</label>
            <input
              id="login-phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder={t('phonePlaceholder')}
              required
              minLength={8}
              maxLength={20}
              disabled={busy}
            />
            <button className="send-button account-submit" type="submit" disabled={busy || phone.trim().length < 8}>
              {busy ? t('sending') : t('requestOtp')}
            </button>
          </>
        ) : (
          <>
            <div className="otp-destination">
              <span>{t('otpSentTo')}</span>
              <strong dir="ltr">{phone}</strong>
              <button type="button" className="text-button" onClick={() => { setStep('phone'); setCode(''); setError('') }} disabled={busy}>
                {t('changePhone')}
              </button>
            </div>
            <label htmlFor="login-code">{t('otpLabel')}</label>
            <input
              id="login-code"
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder={t('otpPlaceholder')}
              required
              minLength={4}
              maxLength={8}
              disabled={busy}
              dir="ltr"
            />
            <button className="send-button account-submit" type="submit" disabled={busy || code.trim().length < 4}>
              {busy ? t('verifying') : t('verifyOtp')}
            </button>
          </>
        )}
        {error && <p className="form-error" role="alert">{error}</p>}
      </form>
      <p className="auth-privacy">{t('authPrivacy')}</p>
    </section>
  )
}
