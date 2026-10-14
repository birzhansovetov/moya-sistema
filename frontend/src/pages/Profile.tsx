import { useState, type FormEvent } from 'react'
import { api, json, type User } from '../api'
import { useAuth } from '../auth'
import { ProfileBackup } from './ProfileBackup'

export function ProfilePage() {
  const { user, setUser, logout } = useAuth()
  const [name, setName] = useState(user?.name || '')
  const [timezone, setTimezone] = useState(user?.timezone || 'Asia/Almaty')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('')
    try {
      const saved = await api<User>('/profile', json('PATCH', { name, timezone }))
      setUser(saved); setMessage('Профиль сохранён')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Не удалось сохранить профиль') }
    finally { setBusy(false) }
  }
  return <div className="pageNarrow">
    <div className="pageHeader"><div><h1>Профиль</h1></div></div>
    <section className="card"><form className="formStack" onSubmit={save}>
      <label>Email<input value={user?.email || ''} disabled /></label>
      <label>Имя<input value={name} maxLength={80} onChange={event => setName(event.target.value)} placeholder="Как к вам обращаться" /></label>
      <label>Часовой пояс<input value={timezone} onChange={event => setTimezone(event.target.value)} placeholder="Asia/Almaty" required /></label>
      <p className="formHint">Часовой пояс определяет, какие задачи показывать в разделе «Мой день».</p>
      {error && <p role="alert" className="errorMessage">{error}</p>}{message && <p role="status" className="successMessage">{message}</p>}
      <div><button className="primaryButton" disabled={busy}>{busy ? 'Сохраняем…' : 'Сохранить изменения'}</button></div>
    </form></section>
    <section className="card"><h2>Ваш подбор</h2><p>Ответы по шести сферам можно изменить. Перед заменой планов вы увидите новый подбор; история занятий сохранится.</p><a className="secondaryButton" href="/onboarding">Изменить ответы</a></section>
    <ProfileBackup />
    <button className="textButton" onClick={() => logout().catch(cause => setError(cause instanceof Error ? cause.message : 'Не удалось выйти'))}>Выйти из аккаунта</button>
  </div>
}
