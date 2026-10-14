import { apiResponse, json } from './api'

export type BackupPreview = {
  created_at: string
  counts: Record<string, number>
  preview_token: string
}

export async function exportBackup(currentPassword: string): Promise<Blob> {
  const response = await apiResponse('/profile/backup/export', json('POST', { current_password: currentPassword }))
  return response.blob()
}

export async function previewBackup(file: File, archivePassword: string): Promise<BackupPreview> {
  const body = new FormData()
  body.append('archive', file)
  body.append('archive_password', archivePassword)
  const response = await apiResponse('/profile/backup/preview', { method: 'POST', body })
  return response.json() as Promise<BackupPreview>
}

export async function safetyCopy(previewToken: string, currentPassword: string): Promise<{ blob: Blob; restoreToken: string }> {
  const response = await apiResponse('/profile/backup/safety-copy', json('POST', { preview_token: previewToken, current_password: currentPassword }))
  const restoreToken = response.headers.get('X-Restore-Token')
  if (!restoreToken) throw new Error('Не удалось подготовить восстановление. Повторите проверку архива.')
  return { blob: await response.blob(), restoreToken }
}

export async function restoreBackup(file: File, archivePassword: string, currentPassword: string, restoreToken: string): Promise<void> {
  const body = new FormData()
  body.append('archive', file)
  body.append('archive_password', archivePassword)
  body.append('current_password', currentPassword)
  body.append('restore_token', restoreToken)
  await apiResponse('/profile/backup/restore', { method: 'POST', body })
}
