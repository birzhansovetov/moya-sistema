import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { api, type User } from '../api'
import { exportBackup, previewBackup, restoreBackup, safetyCopy, type BackupPreview } from '../backupApi'
import { useAuth } from '../auth'

const MAX_FILE_BYTES = 8 * 1024 * 1024
const TABLE_LABELS: Record<string, string> = {
  tasks: 'Задачи', subtasks: 'Шаги задач', task_completions: 'Выполнения задач',
  sport_plans: 'Планы тренировок', workout_logs: 'Тренировки', training_feedback: 'Оценки сложности тренировок',
  nutrition_profiles: 'Настройки питания', nutrition_menus: 'Меню', food_logs: 'Приёмы пищи', weight_logs: 'Вес',
  expense_categories: 'Категории расходов', expenses: 'Расходы', personal_entries: 'Личные записи',
  reading_books: 'Книги', reading_logs: 'Записи о чтении', study_plans: 'Учебные планы',
  study_attempts: 'Результаты уроков', study_drafts: 'Черновики уроков', study_reviews: 'Повторения',
}

function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : 'Не удалось выполнить действие. Повторите попытку.'
}

export function ProfileBackup() {
  const { setUser } = useAuth()
  const queryClient = useQueryClient()
  const [exportPassword, setExportPassword] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [fileInputKey, setFileInputKey] = useState(0)
  const [archivePassword, setArchivePassword] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [preview, setPreview] = useState<BackupPreview | null>(null)
  const [restoreToken, setRestoreToken] = useState('')
  const [safetySaved, setSafetySaved] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  function resetConfirmation() {
    setPreview(null)
    setRestoreToken('')
    setSafetySaved(false)
  }

  async function download() {
    setBusy('export'); setError(''); setMessage('')
    try {
      const blob = await exportBackup(exportPassword)
      saveFile(blob, 'moya-sistema.moya-backup')
      setExportPassword('')
      setMessage('Архив подготовлен. Сохраните файл в надёжном месте; для открытия понадобится этот пароль.')
    } catch (cause) { setError(errorText(cause)) }
    finally { setBusy('') }
  }

  async function checkArchive() {
    if (!file) return
    setBusy('preview'); setError(''); setMessage(''); resetConfirmation()
    try { setPreview(await previewBackup(file, archivePassword)) }
    catch (cause) { setError(errorText(cause)) }
    finally { setBusy('') }
  }

  async function downloadSafetyCopy() {
    if (!preview) return
    setBusy('safety'); setError(''); setMessage(''); setRestoreToken(''); setSafetySaved(false)
    try {
      const result = await safetyCopy(preview.preview_token, currentPassword)
      saveFile(result.blob, 'moya-sistema-pered-vosstanovleniem.moya-backup')
      setRestoreToken(result.restoreToken)
      setMessage('Текущая копия подготовлена. Проверьте, что файл сохранился, прежде чем заменять данные.')
    } catch (cause) { setError(errorText(cause)) }
    finally { setBusy('') }
  }

  async function replace() {
    if (!file || !preview || !restoreToken || !safetySaved) return
    setBusy('restore'); setError(''); setMessage('')
    try {
      await restoreBackup(file, archivePassword, currentPassword, restoreToken)
      queryClient.clear()
      setFile(null); setFileInputKey(value => value + 1); setArchivePassword(''); setCurrentPassword('')
      resetConfirmation()
      try {
        setUser(await api<User>('/profile'))
        setMessage('Данные восстановлены. Разделы обновятся при открытии.')
      } catch {
        setMessage('Данные восстановлены. Обновите страницу, чтобы увидеть все изменения.')
      }
    } catch (cause) { setError(errorText(cause)) }
    finally { setBusy('') }
  }

  const active = Boolean(busy)
  return <section className="card profileBackup" aria-labelledby="profile-backup-title">
    <div className="profileBackupHeader">
      <div><span className="eyebrow">ВАШИ ДАННЫЕ</span><h2 id="profile-backup-title">Резервная копия</h2></div>
      <span className="profileBackupTag">Личный архив</span>
    </div>
    <p className="muted">Скачайте зашифрованный файл вручную. Он содержит ваши планы, записи и историю во всех разделах. Пароль входа на момент скачивания нужен для открытия файла.</p>
    <div className="profileBackupBlock">
      <h3>1. Скачать архив</h3>
      <label className="profileBackupLabel">Пароль входа для архива
        <input type="password" autoComplete="off" value={exportPassword} onChange={event => setExportPassword(event.target.value)} />
      </label>
      <button type="button" className="secondaryButton" disabled={active || !exportPassword} onClick={download}>{busy === 'export' ? 'Подготавливаем…' : 'Скачать архив'}</button>
    </div>
    <div className="profileBackupBlock">
      <h3>2. Восстановить из файла</h3>
      <p className="formHint">Текущие записи будут заменены. Сначала вы увидите состав архива и скачаете свежую копию текущих данных.</p>
      <label className="profileBackupLabel">Файл архива
        <input key={fileInputKey} type="file" accept=".moya-backup,application/octet-stream" onChange={event => {
          const chosen = event.currentTarget.files?.[0] || null
          resetConfirmation(); setError(''); setMessage('')
          if (chosen && chosen.size > MAX_FILE_BYTES) { setFile(null); setError('Архив слишком большой: максимум 8 МиБ.'); return }
          setFile(chosen)
        }} />
      </label>
      {file && <p className="formHint">Выбран файл: <strong>{file.name}</strong></p>}
      <label className="profileBackupLabel">Пароль архива
        <input type="password" autoComplete="off" value={archivePassword} onChange={event => { setArchivePassword(event.target.value); resetConfirmation() }} />
      </label>
      <button type="button" className="secondaryButton" disabled={active || !file || !archivePassword} onClick={checkArchive}>{busy === 'preview' ? 'Проверяем…' : 'Проверить архив'}</button>
      {preview && <div className="profileBackupPreview" aria-live="polite">
        <strong>В архиве</strong>
        <p>Создан: {new Date(preview.created_at).toLocaleString('ru-RU')}</p>
        <ul>{Object.entries(preview.counts).filter(([, count]) => count > 0).map(([table, count]) => <li key={table}>{TABLE_LABELS[table] || table}: {count}</li>)}</ul>
        <p className="formHint">Пароль архива может отличаться от текущего пароля входа, если вы меняли пароль.</p>
      </div>}
      {preview && <div className="profileBackupConfirm">
        <label className="profileBackupLabel">Текущий пароль
          <input type="password" autoComplete="off" value={currentPassword} onChange={event => { setCurrentPassword(event.target.value); setRestoreToken(''); setSafetySaved(false) }} />
        </label>
        <button type="button" className="secondaryButton" disabled={active || !currentPassword} onClick={downloadSafetyCopy}>{busy === 'safety' ? 'Подготавливаем…' : 'Скачать текущую копию'}</button>
        {restoreToken && <label className="profileBackupCheck"><input type="checkbox" checked={safetySaved} onChange={event => setSafetySaved(event.target.checked)} /> Копия текущих данных сохранена на моём устройстве</label>}
        <button type="button" className="dangerButton" disabled={active || !restoreToken || !safetySaved} onClick={replace}>{busy === 'restore' ? 'Восстанавливаем…' : 'Заменить данные'}</button>
      </div>}
    </div>
    {error && <p role="alert" className="errorMessage">{error}</p>}
    {message && <p role="status" className="successMessage">{message}</p>}
  </section>
}
