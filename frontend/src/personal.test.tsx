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

test('diary keeps guidance off the writing screen',async()=>{mount();expect(screen.queryByRole('heading',{name:'Готовые гайды'})).not.toBeInTheDocument()})

test('free text diary survives failed save and can be edited, removed and restored',async()=>{
  failed=true; mount()
  fireEvent.change(await screen.findByLabelText('Что хотите записать?'),{target:{value:'Моя собственная мысль'}})
  fireEvent.click(screen.getByRole('button',{name:'Сохранить запись'}))
  await screen.findByText('Нет сети')
  expect(screen.getByLabelText('Что хотите записать?')).toHaveValue('Моя собственная мысль')
  fireEvent.click(screen.getByRole('button',{name:'Сохранить запись'}))
  await screen.findByText('Моя собственная мысль',{selector:'p'})
  expect(entries).toHaveLength(1)
  fireEvent.click(screen.getByRole('button',{name:'Изменить запись'}))
  const modal=within(screen.getByRole('dialog'))
  fireEvent.change(modal.getByLabelText('Что хотите записать?'),{target:{value:'Дополненная мысль'}})
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
  fireEvent.change(screen.getByLabelText('Что хотите записать?'),{target:{value:'Новая запись'}})
  fireEvent.click(screen.getByRole('button',{name:'Сохранить запись'}))
  await waitFor(()=>expect(finish).toBeTypeOf('function'))
  fireEvent.click(screen.getByRole('button',{name:'История'}))
  fireEvent.click(screen.getByRole('button',{name:'Изменить запись'}))
  const modal=within(screen.getByRole('dialog'))
  fireEvent.change(modal.getByLabelText('Что хотите записать?'),{target:{value:'Не потерять этот черновик'}})
  const item={...entries[0],id:'new',body:'Новая запись'};entries.push(item);finish(item)
  await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('Запись сохранена'))
  expect(within(screen.getByRole('dialog')).getByLabelText('Что хотите записать?')).toHaveValue('Не потерять этот черновик')
})

test('quick diary saves mood and multiple activities without prose', async () => {
  mount()
  fireEvent.click(await screen.findByRole('button', {name:'Хорошо'}))
  fireEvent.click(screen.getByLabelText('Встреча'))
  fireEvent.click(screen.getByLabelText('Отдых'))
  fireEvent.click(screen.getByRole('button',{name:'Сохранить запись'}))
  await screen.findByText('Настроение: Хорошее')
  expect(entries[0]).toMatchObject({kind:'diary',mood:'good',activities:['meeting','rest'],body:''})
  expect(screen.getByRole('article')).toHaveTextContent('Встреча')
  expect(screen.getByRole('article')).toHaveTextContent('Отдых')
})

test('dated diary history can be opened from its calendar day', async () => {
  entries=[{id:'dated',kind:'diary',title:'',body:'Прогулка вечером',date:'2026-10-10',mood:'good',activity:'walk',activities:['walk'],completed:false,impression:'',deleted:false}]
  mount()
  fireEvent.click(screen.getByRole('button',{name:'История'}))
  fireEvent.click(screen.getByText('Календарь записей',{exact:true}))
  expect(await screen.findByText('Прогулка вечером')).toBeInTheDocument()
  fireEvent.click(await screen.findByRole('button',{name:'10 октября, 1 запись'}))
  expect(screen.getByLabelText('С')).toHaveValue('2026-10-10')
  expect(screen.getByLabelText('По')).toHaveValue('2026-10-10')
})

test('diary starts with a quick entry and keeps history and date secondary',async()=>{
 mount()
 expect(screen.getByRole('button',{name:'Хорошо'})).toBeVisible()
 expect(screen.queryByRole('textbox',{name:'Дата'})).not.toBeInTheDocument()
 expect(screen.queryByRole('heading',{name:'История'})).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'История'}))
 expect(screen.getByRole('heading',{name:'История'})).toBeVisible()
 fireEvent.click(screen.getByRole('button',{name:'Запись'}))
 fireEvent.click(screen.getByText('Добавить детали',{exact:true}))
 expect(screen.getByLabelText('Дата')).toBeVisible()
})
