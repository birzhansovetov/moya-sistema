import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, vi } from 'vitest'
import { PersonalPage } from './pages/Personal'
const { apiMock } = vi.hoisted(() => ({ apiMock: vi.fn() }))
vi.mock('./api', async original => ({ ...await original<typeof import('./api')>(), api: apiMock }))
vi.mock('./auth', () => ({ useAuth: () => ({ user: { id: 'one', timezone: 'Asia/Almaty' } }) }))
vi.mock('./useLocalToday', () => ({ useLocalToday: () => '2026-10-10' }))
let entries: Record<string, unknown>[]
let failed: boolean
beforeEach(() => {
  entries = []; failed = false
  apiMock.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    const url = new URL(path, 'https://test.local'); const body = init?.body ? JSON.parse(init.body as string) : {}
    if (url.pathname === '/library/guides') return {items:[]}
    if (url.pathname === '/personal/entries') {
      if (init?.method === 'POST') {
        if (failed) { failed=false; throw new Error('Нет сети') }
        const item={...body, id:'one', deleted:false}; entries.push(item); return item
      }
      const items=entries.filter(item => item.deleted === (url.searchParams.get('deleted') === 'true'))
      return {items:[...items],total:items.length,limit:30,offset:0}
    }
    const item=entries.find(item=>item.id===url.pathname.split('/')[3])!
    if(init?.method==='DELETE'){item.deleted=true;return undefined}
    if(url.pathname.endsWith('/restore')) item.deleted=false
    else if(init?.method==='PATCH') Object.assign(item,body)
    return {...item}
  })
})
function mount(){render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><PersonalPage/></MemoryRouter></QueryClientProvider>)}

test('personal guidance is reachable from the first screen',async()=>{
  mount()
  expect(screen.getByRole('link',{name:'Открыть гайды'})).toHaveAttribute('href','#personal-guides')
  expect(await screen.findByRole('heading',{name:'Готовые гайды'})).toBeInTheDocument()
})

test('free text diary survives failed save and can be edited, removed and restored',async()=>{
  failed=true; mount()
  fireEvent.change(await screen.findByLabelText('Текст записи'),{target:{value:'Моя собственная мысль'}})
  fireEvent.click(screen.getByRole('button',{name:'Сохранить запись'}))
  await screen.findByText('Нет сети')
  expect(screen.getByLabelText('Текст записи')).toHaveValue('Моя собственная мысль')
  fireEvent.click(screen.getByRole('button',{name:'Сохранить запись'}))
  await screen.findByText('Моя собственная мысль',{selector:'p'})
  expect(entries).toHaveLength(1)
  fireEvent.click(screen.getByRole('button',{name:'Изменить запись'}))
  const modal=within(screen.getByRole('dialog'))
  fireEvent.change(modal.getByLabelText('Текст записи'),{target:{value:'Дополненная мысль'}})
  fireEvent.click(modal.getByRole('button',{name:'Сохранить изменения'}))
  await screen.findByText('Дополненная мысль',{selector:'p'})
  fireEvent.click(screen.getByRole('button',{name:'Удалить запись'}))
  await screen.findByRole('button',{name:'Отменить удаление'})
  await waitFor(()=>expect(screen.queryByText('Дополненная мысль',{selector:'p'})).not.toBeInTheDocument())
  fireEvent.click(screen.getByRole('button',{name:'Отменить удаление'}))
  await screen.findByText('Дополненная мысль',{selector:'p'})
})

test('an experiment can stay undated and keeps its result separate from task completion',async()=>{
  mount(); fireEvent.change(await screen.findByLabelText('Тип записи'),{target:{value:'experiment'}})
  fireEvent.change(screen.getByLabelText('Название'),{target:{value:'Попробовать акварель'}})
  fireEvent.change(screen.getByLabelText('Дата'),{target:{value:''}})
  fireEvent.change(screen.getByLabelText('Впечатление'),{target:{value:'Хочу попробовать ещё'}})
  fireEvent.click(screen.getByLabelText('Выполнено'))
  fireEvent.click(screen.getByRole('button',{name:'Сохранить запись'}))
  await screen.findByRole('heading',{name:'Попробовать акварель'})
  expect(entries[0]).toMatchObject({kind:'experiment',date:null,completed:true,impression:'Хочу попробовать ещё'})
  expect(screen.getByRole('article')).toHaveTextContent('Без даты')
})

test('an inline creation finishing cannot close another entry editor',async()=>{
  entries=[{id:'old',kind:'diary',title:'Существующая запись',body:'Первый текст',date:'2026-10-10',mood:null,activity:'other',completed:false,impression:'',deleted:false}]
  const original=apiMock.getMockImplementation()!
  let finish!:(item:Record<string,unknown>)=>void
  apiMock.mockImplementation((path:string,init?:RequestInit)=>path==='/personal/entries'&&init?.method==='POST'?new Promise(resolve=>{finish=resolve}):original(path,init))
  mount()
  await screen.findByText('Первый текст',{selector:'p'})
  fireEvent.change(screen.getByLabelText('Текст записи'),{target:{value:'Новая запись'}})
  fireEvent.click(screen.getByRole('button',{name:'Сохранить запись'}))
  await waitFor(()=>expect(finish).toBeTypeOf('function'))
  fireEvent.click(screen.getByRole('button',{name:'Изменить запись'}))
  const modal=within(screen.getByRole('dialog'))
  fireEvent.change(modal.getByLabelText('Текст записи'),{target:{value:'Не потерять этот черновик'}})
  const item={...entries[0],id:'new',body:'Новая запись'};entries.push(item);finish(item)
  await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('Запись сохранена'))
  expect(within(screen.getByRole('dialog')).getByLabelText('Текст записи')).toHaveValue('Не потерять этот черновик')
})
