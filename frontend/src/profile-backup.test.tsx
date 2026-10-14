import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { vi } from 'vitest'

import { ProfilePage } from './pages/Profile'

const { exportMock, previewMock, safetyMock, restoreMock, setUserMock, apiMock } = vi.hoisted(() => ({
  exportMock: vi.fn(), previewMock: vi.fn(), safetyMock: vi.fn(), restoreMock: vi.fn(),
  setUserMock: vi.fn(), apiMock: vi.fn(),
}))
vi.mock('./backupApi', () => ({
  exportBackup: exportMock, previewBackup: previewMock,
  safetyCopy: safetyMock, restoreBackup: restoreMock,
}))
vi.mock('./auth', () => ({ useAuth: () => ({ user: { id: 'one', email: 'one@example.com', name: 'Мой профиль', timezone: 'Asia/Almaty' }, setUser: setUserMock, logout: vi.fn() }) }))
vi.mock('./api', async importOriginal => ({ ...await importOriginal<typeof import('./api')>(), api: apiMock }))

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><ProfilePage /></QueryClientProvider>)
  return client
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:backup'), revokeObjectURL: vi.fn() })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
  exportMock.mockResolvedValue(new Blob(['encrypted']))
  previewMock.mockResolvedValue({ created_at: '2026-10-10T10:00:00Z', counts: { tasks: 1, expenses: 2 }, preview_token: 'preview' })
  safetyMock.mockResolvedValue({ blob: new Blob(['current']), restoreToken: 'restore' })
  restoreMock.mockResolvedValue({ status: 'restored' })
  apiMock.mockResolvedValue({ id: 'one', email: 'one@example.com', name: 'После восстановления', timezone: 'Asia/Almaty' })
})

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

test('profile downloads encrypted backup and gates replacement behind fresh copy', async () => {
  setup()
  fireEvent.change(screen.getByLabelText('Пароль входа для архива'), { target: { value: 'current-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Скачать архив' }))
  await waitFor(() => expect(exportMock).toHaveBeenCalledWith('current-password'))
  const file = new File(['encrypted'], 'saved.moya-backup', { type: 'application/octet-stream' })
  fireEvent.change(screen.getByLabelText('Файл архива'), { target: { files: [file] } })
  fireEvent.change(screen.getByLabelText('Пароль архива'), { target: { value: 'old-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Проверить архив' }))
  await waitFor(() => expect(screen.getByText(/Задачи: 1/)).toBeInTheDocument())
  expect(screen.getByRole('button', { name: 'Заменить данные' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Текущий пароль'), { target: { value: 'current-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Скачать текущую копию' }))
  await waitFor(() => expect(safetyMock).toHaveBeenCalledWith('preview', 'current-password'))
  expect(screen.getByRole('button', { name: 'Заменить данные' })).toBeDisabled()
  fireEvent.click(screen.getByRole('checkbox', { name: /Копия текущих данных сохранена/ }))
  expect(screen.getByRole('button', { name: 'Заменить данные' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Заменить данные' }))
  await waitFor(() => expect(restoreMock).toHaveBeenCalledWith(file, 'old-password', 'current-password', 'restore'))
  await waitFor(() => expect(setUserMock).toHaveBeenCalledWith(expect.objectContaining({ name: 'После восстановления' })))
})

test('failed restore keeps selected file and passwords for retry', async () => {
  setup()
  const file = new File(['encrypted'], 'saved.moya-backup')
  fireEvent.change(screen.getByLabelText('Файл архива'), { target: { files: [file] } })
  fireEvent.change(screen.getByLabelText('Пароль архива'), { target: { value: 'old-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Проверить архив' }))
  await waitFor(() => expect(previewMock).toHaveBeenCalled())
  fireEvent.change(screen.getByLabelText('Текущий пароль'), { target: { value: 'current-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Скачать текущую копию' }))
  await waitFor(() => expect(safetyMock).toHaveBeenCalled())
  fireEvent.click(screen.getByRole('checkbox', { name: /Копия текущих данных сохранена/ }))
  restoreMock.mockRejectedValueOnce(new Error('Сервис временно недоступен'))
  fireEvent.click(screen.getByRole('button', { name: 'Заменить данные' }))
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Сервис временно недоступен'))
  expect(screen.getByLabelText('Пароль архива')).toHaveValue('old-password')
  expect(screen.getByLabelText('Текущий пароль')).toHaveValue('current-password')
  expect(screen.getByText('saved.moya-backup')).toBeInTheDocument()
})
