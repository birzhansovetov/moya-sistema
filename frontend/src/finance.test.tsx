import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, vi } from 'vitest'
import { FinancePage } from './pages/Finance'

const { apiMock, clock } = vi.hoisted(() => ({ apiMock: vi.fn(), clock: { today: '2026-10-10' } }))
vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), api: apiMock }))
vi.mock('./auth', () => ({ useAuth: () => ({ user: { id: 'one', timezone: 'Asia/Almaty' } }) }))
vi.mock('./useLocalToday', () => ({ useLocalToday: () => clock.today }))

type Item = { id: string; amount: string; currency: string; category_id: string; category_name: string; date: string; note: string; deleted: boolean }
let items: Item[]
let incomes: { id: string; amount: string; currency: string; source: string; date: string; note: string; deleted: boolean }[]
let categories: { id: string; name: string }[]
let currency: string
let failCreate: boolean

beforeEach(() => {
  clock.today = '2026-10-10'
  items = []
  incomes = []
  categories = [{ id: 'food', name: 'Продукты' }, { id: 'home', name: 'Жильё' }]
  currency = 'KZT'
  failCreate = false
  apiMock.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    const url = new URL(path, 'https://example.test')
    const body = init?.body ? JSON.parse(init.body as string) : {}
    if (url.pathname === '/library/guides') return { items: [] }
    if (url.pathname === '/finance/settings') {
      if (init?.method === 'PATCH') currency = body.currency
      return { currency, currencies: ['KZT', 'USD', 'EUR', 'RUB', 'GBP'] }
    }
    if (url.pathname === '/finance/categories') {
      if (init?.method === 'POST') { const category = { id: 'custom', name: body.name }; categories.push(category); return category }
      return { items: [...categories] }
    }
    if (url.pathname.startsWith('/finance/categories/')) {
      const category = categories.find(item => item.id === url.pathname.split('/').pop())!
      category.name = body.name
      return category
    }
    if (url.pathname === '/finance/summary') {
      const selected = url.searchParams.get('currency') || currency
      const selectedMonth = url.searchParams.get('month') || '2026-10'
      const total = items.filter(item => !item.deleted && item.currency === selected && item.date.startsWith(selectedMonth)).reduce((sum, item) => sum + Number(item.amount), 0).toFixed(2)
      const categoryTotals = categories.map(category => ({ id: category.id, name: category.name, amount: items.filter(item => !item.deleted && item.currency === selected && item.date.startsWith(selectedMonth) && item.category_id === category.id).reduce((sum, item) => sum + Number(item.amount), 0).toFixed(2) })).filter(item => item.amount !== '0.00').sort((a, b) => Number(b.amount) - Number(a.amount))
      const incomeTotal = incomes.filter(item => !item.deleted && item.currency === selected && item.date.startsWith(selectedMonth)).reduce((sum, item) => sum + Number(item.amount), 0).toFixed(2)
      return { currency: selected, today: '2026-10-10', week_start: '2026-10-05', week_end: '2026-10-11', month: selectedMonth, today_total: total, week_total: total, month_total: total, income_total: incomeTotal, net_total: (Number(incomeTotal) - Number(total)).toFixed(2), income_sources: [], categories: categoryTotals }
    }
    if (url.pathname === '/finance/incomes') {
      if (init?.method === 'POST') { const item = { ...body, id: `income-${incomes.length}`, deleted: false }; incomes.push(item); return item }
      const filtered = incomes.filter(item => item.currency === url.searchParams.get('currency') && item.deleted === (url.searchParams.get('deleted') === 'true'))
      return { items: [...filtered], total: filtered.length, offset: 0, limit: 30 }
    }
    if (url.pathname.startsWith('/finance/incomes/')) {
      const item = incomes.find(item => item.id === url.pathname.split('/')[3])!
      if (init?.method === 'DELETE') { item.deleted = true; return undefined }
      if (url.pathname.endsWith('/restore')) item.deleted = false
      else Object.assign(item, body)
      return { ...item }
    }
    if (url.pathname === '/finance/expenses') {
      if (init?.method === 'POST') {
        if (failCreate) { failCreate = false; throw new Error('Сеть недоступна') }
        const item = { ...body, id: 'created', deleted: false, category_name: categories.find(item => item.id === body.category_id)!.name }
        items.push(item); return item
      }
      const filtered = items.filter(item => item.currency === url.searchParams.get('currency') && item.deleted === (url.searchParams.get('deleted') === 'true'))
      return { items: [...filtered], total: filtered.length, offset: 0, limit: 30 }
    }
    if (url.pathname.startsWith('/finance/expenses/')) {
      const item = items.find(item => item.id === url.pathname.split('/')[3])!
      if (init?.method === 'DELETE') { item.deleted = true; return undefined }
      if (url.pathname.endsWith('/restore')) item.deleted = false
      else Object.assign(item, body, { category_name: categories.find(item => item.id === body.category_id)!.name })
      return { ...item }
    }
    throw new Error(`Unexpected ${path}`)
  })
})

function expenseForm() { return within(screen.getByRole('button', { name: 'Добавить расход' }).closest('form')!) }

function mount() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><FinancePage /></MemoryRouter></QueryClientProvider>)
}
async function openRecords() { fireEvent.click(await screen.findByRole('button', { name: 'Записи' })) }
async function openExpense() { await openRecords(); fireEvent.click(screen.getByRole('button', { name: 'Записать расход' })) }
async function openIncome() { await openRecords(); fireEvent.click(screen.getByRole('button', { name: 'Записать доход' })) }

test('finance starts with one clear overview and opens records only on request', async () => {
  mount()
  expect(await screen.findByTestId('finance-net-total')).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'История расходов' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Добавить расход' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Записать расход' }))
  expect(screen.getByRole('heading', { name: 'История расходов' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Добавить расход' })).toBeInTheDocument()
})

test('failed expense save retains the draft and retry key, success adds it to history', async () => {
  failCreate = true
  mount()
  await openExpense()
  fireEvent.change((await screen.findAllByLabelText('Сумма'))[1], { target: { value: '12,34' } })
  fireEvent.change(expenseForm().getByLabelText('Комментарий'), { target: { value: 'Кофе' } })
  fireEvent.click(screen.getByRole('button', { name: 'Добавить расход' }))
  await screen.findByText('Сеть недоступна')
  expect(expenseForm().getByLabelText('Сумма')).toHaveValue('12,34')
  expect(expenseForm().getByLabelText('Комментарий')).toHaveValue('Кофе')
  fireEvent.click(screen.getByRole('button', { name: 'Добавить расход' }))
  await screen.findByText('Кофе', { selector: 'p' })
  await waitFor(() => expect(expenseForm().getByLabelText('Сумма')).toHaveValue(''))
  const calls = apiMock.mock.calls.filter(([path, init]) => path === '/finance/expenses' && init?.method === 'POST')
  const first = JSON.parse(calls[0][1].body)
  const retry = JSON.parse(calls[1][1].body)
  expect(first).toEqual(retry)
  expect(first).toMatchObject({ amount: '12.34', date: '2026-10-10', currency: 'KZT' })
})

test('monthly insight compares the same currency and shows the largest category', async () => {
  items = [
    { id: 'previous', amount: '100.00', currency: 'KZT', category_id: 'home', category_name: 'Жильё', date: '2026-09-12', note: '', deleted: false },
    { id: 'current', amount: '150.00', currency: 'KZT', category_id: 'home', category_name: 'Жильё', date: '2026-10-10', note: '', deleted: false },
    { id: 'foreign', amount: '999.00', currency: 'USD', category_id: 'home', category_name: 'Жильё', date: '2026-10-10', note: '', deleted: false },
  ]
  mount()
  expect(await screen.findByText(/На 50,00 KZT больше, чем в сентябре/)).toBeInTheDocument()
  expect(screen.getByText(/Больше всего записано в категории «Жильё»/)).toBeInTheDocument()
})

test('equal monthly totals use a clear comparison phrase', async () => {
  mount()
  expect(await screen.findByText(/Столько же, сколько в сентябре/)).toBeInTheDocument()
})

test('dashboard shows six months in the selected currency and category share', async () => {
  items = [
    { id: 'aug', amount: '80.00', currency: 'KZT', category_id: 'home', category_name: 'Жильё', date: '2026-08-10', note: '', deleted: false },
    { id: 'home', amount: '75.00', currency: 'KZT', category_id: 'home', category_name: 'Жильё', date: '2026-10-10', note: '', deleted: false },
    { id: 'food', amount: '25.00', currency: 'KZT', category_id: 'food', category_name: 'Продукты', date: '2026-10-10', note: '', deleted: false },
    { id: 'usd', amount: '500.00', currency: 'USD', category_id: 'food', category_name: 'Продукты', date: '2026-10-10', note: '', deleted: false },
  ]
  mount()
  const chart = await screen.findByRole('figure', { name: 'Расходы за 6 месяцев' })
  expect(within(chart).getAllByRole('listitem')).toHaveLength(6)
  expect(within(chart).getByText('80,00 KZT')).toBeInTheDocument()
  expect(screen.getByText(/Жильё.*75,0%/)).toBeInTheDocument()
  expect(screen.getByText(/Продукты.*25,0%/)).toBeInTheDocument()
})

test('expense editing and reversible deletion refresh visible history and totals', async () => {
  items = [{ id: 'one', amount: '1250.50', currency: 'KZT', category_id: 'home', category_name: 'Жильё', date: '2026-10-10', note: 'Квартира', deleted: false }]
  mount()
  await openRecords()
  fireEvent.click(await screen.findByRole('button', { name: 'Изменить расход Квартира' }))
  const dialog = within(screen.getByRole('dialog', { name: 'Редактировать расход' }))
  fireEvent.change(dialog.getByLabelText('Сумма'), { target: { value: '1500' } })
  fireEvent.click(dialog.getByRole('button', { name: 'Сохранить расход' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  await waitFor(() => expect(screen.getByTestId('finance-month-total')).toHaveTextContent('1 500,00'))
  fireEvent.click(screen.getByRole('button', { name: 'Удалить расход Квартира' }))
  await screen.findByText('Расход перемещён в удалённые.')
  await waitFor(() => expect(screen.queryByText('Квартира', { selector: 'p' })).not.toBeInTheDocument())
  expect(screen.getByTestId('finance-month-total')).toHaveTextContent('0,00')
  fireEvent.click(screen.getByRole('button', { name: 'Отменить удаление' }))
  await screen.findByText('Квартира', { selector: 'p' })
})

test('currency view is separate from an unfinished expense and categories are editable', async () => {
  items = [{ id: 'dollar', amount: '9.50', currency: 'USD', category_id: 'home', category_name: 'Жильё', date: '2026-10-10', note: 'Долларовый расход', deleted: false }]
  mount()
  await openExpense()
  fireEvent.change((await screen.findAllByLabelText('Сумма'))[1], { target: { value: '80' } })
  fireEvent.change(screen.getByLabelText('Валюта обзора'), { target: { value: 'USD' } })
  await screen.findByText('Долларовый расход', { selector: 'p' })
  expect(expenseForm().getByLabelText('Сумма')).toHaveValue('80')
  expect(screen.getByLabelText('Валюта расхода')).toHaveValue('KZT')
  fireEvent.change(screen.getByLabelText('Название новой категории'), { target: { value: 'Книги' } })
  fireEvent.click(screen.getByRole('button', { name: 'Добавить категорию' }))
  await screen.findByRole('button', { name: 'Изменить категорию Книги' })
  fireEvent.click(screen.getByRole('button', { name: 'Изменить категорию Книги' }))
  fireEvent.change(screen.getByLabelText('Новое название категории'), { target: { value: 'Чтение' } })
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить категорию' }))
  await screen.findByRole('button', { name: 'Изменить категорию Чтение' })
  fireEvent.change(screen.getByLabelText('Основная валюта'), { target: { value: 'EUR' } })
  fireEvent.click(screen.getByRole('button', { name: 'Сохранить валюту' }))
  await screen.findByText('Основная валюта сохранена.')
  expect(screen.getByLabelText('Валюта расхода')).toHaveValue('KZT')
})


test('a failed background category refresh retains the expense draft through retry', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter><FinancePage /></MemoryRouter></QueryClientProvider>)
  await openExpense()
  fireEvent.change((await screen.findAllByLabelText('Сумма'))[1], { target: { value: '77' } })
  fireEvent.change(expenseForm().getByLabelText('Комментарий'), { target: { value: 'Незаконченный расход' } })
  apiMock.mockRejectedValueOnce(new Error('Обновление недоступно'))
  await client.invalidateQueries({ queryKey: ['finance-categories'] })
  await screen.findByRole('alert')
  expect(expenseForm().getByLabelText('Сумма')).toHaveValue('77')
  expect(expenseForm().getByLabelText('Комментарий')).toHaveValue('Незаконченный расход')
  fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
  await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  expect(expenseForm().getByLabelText('Сумма')).toHaveValue('77')
})

test('a failed expense retry preserves its original date and key after local midnight', async () => {
  failCreate = true
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const view = render(<QueryClientProvider client={client}><MemoryRouter><FinancePage /></MemoryRouter></QueryClientProvider>)
  await openExpense()
  fireEvent.change((await screen.findAllByLabelText('Сумма'))[1], { target: { value: '77' } })
  fireEvent.click(screen.getByRole('button', { name: 'Добавить расход' }))
  await screen.findByText('Сеть недоступна')
  clock.today = '2026-10-11'
  view.rerender(<QueryClientProvider client={client}><MemoryRouter><FinancePage /></MemoryRouter></QueryClientProvider>)
  fireEvent.click(screen.getByRole('button', { name: 'Добавить расход' }))
  await waitFor(() => expect(expenseForm().getByLabelText('Сумма')).toHaveValue(''))
  const calls = apiMock.mock.calls.filter(([path, init]) => path === '/finance/expenses' && init?.method === 'POST')
  expect(JSON.parse(calls[1][1].body)).toEqual(JSON.parse(calls[0][1].body))
  expect(screen.getByLabelText('Дата расхода')).toHaveValue('2026-10-11')
})

test('income is saved, included in monthly difference, and can be edited or removed', async () => {
  mount()
  await openIncome()
  const incomeForm = within((await screen.findByRole('button', { name: 'Добавить доход' })).closest('form')!)
  fireEvent.change(incomeForm.getByLabelText('Сумма'), { target: { value: '250000' } })
  fireEvent.change(incomeForm.getByLabelText('Источник'), { target: { value: 'Зарплата' } })
  fireEvent.click(incomeForm.getByRole('button', { name: 'Добавить доход' }))
  expect(await screen.findByTestId('finance-income-total')).toHaveTextContent('250 000,00')
  expect(screen.getByTestId('finance-net-total')).toHaveTextContent('250 000,00')
  fireEvent.click(screen.getByRole('button', { name: 'Изменить доход Зарплата' }))
  const dialog = within(screen.getByRole('dialog', { name: 'Редактировать доход' }))
  fireEvent.change(dialog.getByLabelText('Сумма'), { target: { value: '260000' } })
  fireEvent.click(dialog.getByRole('button', { name: 'Сохранить доход' }))
  await waitFor(() => expect(screen.getByTestId('finance-income-total')).toHaveTextContent('260 000,00'))
  fireEvent.click(screen.getByRole('button', { name: 'Удалить доход Зарплата' }))
  await waitFor(() => expect(screen.getByTestId('finance-income-total')).toHaveTextContent('0,00'))
  fireEvent.click(screen.getByRole('button', { name: 'Отменить удаление' }))
  await waitFor(() => expect(screen.getByTestId('finance-income-total')).toHaveTextContent('260 000,00'))
})
