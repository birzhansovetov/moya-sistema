import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { api, json, type AuthResult } from '../api'
import { Button, Card, Input } from '../components/ui'
import styles from './Auth.module.css'

type Mode = 'login' | 'register' | 'forgot' | 'verify' | 'reset'

export function AuthPage({ onAuthenticated }: { onAuthenticated: (value: AuthResult) => void }) {
  const location = useLocation()
  const navigate = useNavigate()
  const mode: Mode = location.pathname === '/register' ? 'register'
    : location.pathname === '/forgot-password' ? 'forgot'
    : location.pathname === '/verify-email' ? 'verify'
    : location.pathname === '/reset-password' ? 'reset' : 'login'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [linkToken, setLinkToken] = useState('')

  useEffect(() => {
    setError(''); setMessage('')
    const fragment = new URLSearchParams(location.hash.slice(1))
    setLinkToken(fragment.get('token') || '')
  }, [location.pathname, location.hash])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true); setError(''); setMessage('')
    try {
      if (mode === 'login') {
        const result = await api<AuthResult>('/auth/login', json('POST', { email, password }))
        onAuthenticated(result)
        navigate('/', { replace: true })
      } else if (mode === 'register') {
        await api('/auth/register', json('POST', { email }))
        setMessage('Если адрес доступен, мы отправили письмо для подтверждения. Откройте ссылку в письме.')
      } else if (mode === 'forgot') {
        await api('/auth/password-reset/request', json('POST', { email }))
        setMessage('Если адрес зарегистрирован, мы отправили ссылку для сброса пароля.')
      } else if (mode === 'verify') {
        await api('/auth/verify', json('POST', { token: linkToken, password }))
        setMessage('Адрес подтверждён, пароль сохранён. Теперь можно войти.')
        history.replaceState({}, '', location.pathname)
      } else {
        await api('/auth/password-reset/confirm', json('POST', { token: linkToken, password }))
        setMessage('Пароль обновлён. Войдите с новым паролем.')
        history.replaceState({}, '', location.pathname)
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Не удалось выполнить действие. Повторите попытку.')
    } finally { setBusy(false) }
  }

  const title = { login: 'С возвращением', register: 'Создать аккаунт', forgot: 'Восстановить доступ', verify: 'Подтвердить email', reset: 'Новый пароль' }[mode]
  const description = {
    login: 'Войдите, чтобы продолжить свой план.',
    register: 'Начните с адреса электронной почты.',
    forgot: 'Отправим ссылку для восстановления на вашу почту.',
    verify: 'Придумайте пароль, чтобы завершить регистрацию.',
    reset: 'Задайте новый пароль для вашего аккаунта.',
  }[mode]
  return <main className={styles.page}>
    <div className={styles.brand}><span className={styles.brandMark}>М</span><span>Моя система</span></div>
    <Card className={styles.card}>
      <h1>{title}</h1>
      <p className={styles.subtitle}>{description}</p>
      <form onSubmit={submit}>
        <div className={styles.fields}>
          {['login', 'register', 'forgot'].includes(mode) && <Input label="Email" type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} placeholder="you@example.com" />}
          {['login', 'verify', 'reset'].includes(mode) && <Input label="Пароль" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} minLength={12} required value={password} onChange={event => setPassword(event.target.value)} placeholder={mode === 'login' ? 'Введите пароль' : 'Не менее 12 символов'} />}
        </div>
        <div className={styles.feedbackSlot} aria-live="polite">
          {['verify', 'reset'].includes(mode) && !linkToken && <p role="alert" className={styles.error}>Ссылка не содержит кода. Откройте ссылку из письма целиком.</p>}
          {error && <p role="alert" className={styles.error}>{error}</p>}
          {message && <p role="status" className={styles.success}>{message}</p>}
        </div>
        <Button loading={busy} disabled={['verify', 'reset'].includes(mode) && !linkToken} type="submit">{{ login: 'Войти', register: 'Зарегистрироваться', forgot: 'Отправить ссылку', verify: 'Подтвердить адрес', reset: 'Сохранить пароль' }[mode]}</Button>
      </form>
      <div className={styles.links}>
        {mode === 'login' && <><Link to="/register">Создать аккаунт</Link><Link to="/forgot-password">Забыли пароль?</Link></>}
        {mode !== 'login' && <Link to="/login">Вернуться ко входу</Link>}
      </div>
    </Card>
    <p className={styles.footnote}>Ваши записи доступны только вам.</p>
  </main>
}
