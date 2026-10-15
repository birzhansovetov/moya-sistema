import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { vi, beforeEach } from 'vitest'
import { ReadingPage } from './pages/Reading'
const { apiMock }=vi.hoisted(()=>({apiMock:vi.fn()}))
vi.mock('./api',async original=>({...await original<typeof import('./api')>(),api:apiMock}))
vi.mock('./auth',()=>({useAuth:()=>({user:{id:'one',timezone:'Asia/Almaty'}})}))
vi.mock('./useLocalToday',()=>({useLocalToday:()=> '2026-10-10'}))
let book:Record<string,unknown>;let logs:Record<string,unknown>[];let fail:boolean
beforeEach(()=>{
  book={id:'one',title:'Моя книга',author:'Автор',pages:100,current_page:10,next_page:25,daily_pages:15,status:'reading',start_date:null,end_date:null,cover_url:'',final_impression:'',deleted:false};logs=[];fail=false
  apiMock.mockReset().mockImplementation(async(path:string,init?:RequestInit)=>{
    const url=new URL(path,'https://test.local');const body=init?.body?JSON.parse(init.body as string):{}
    if(url.pathname==='/library/guides'||url.pathname==='/library/books')return {items:[]}
    if(url.pathname==='/reading/books/uploads/status')return {enabled:false,max_bytes:15728640}
    if(url.pathname==='/reading/books')return {items:[{...book}],total:1,limit:30,offset:0}
    if(url.pathname==='/reading/books/one')return {...book}
    if(url.pathname==='/reading/books/one/logs'){
      if(init?.method==='POST'){
        if(fail){fail=false;throw new Error('Не удалось отправить')}
        const item={...body,id:'log',book_id:'one',deleted:false};logs.push(item)
        if(body.page!==null){book.current_page=body.page;book.next_page=45}
        return item
      }
      return {items:[...logs],total:logs.length,limit:30,offset:0}
    }
    throw new Error('Unexpected '+path)
  })
})
test('manual book entry remains available when private file storage is disabled',async()=>{
  mount()
  expect(await screen.findByText('Загрузка файлов пока недоступна. Готовые книги и запись названия доступны ниже.')).toBeInTheDocument()
  expect(screen.getByRole('button',{name:'Записать свою книгу'})).toBeEnabled()
})

test('personal EPUB reader resumes and saves position without a reading log',async()=>{
  const original=apiMock.getMockImplementation()!
  let saved:Record<string,unknown>|null=null
  apiMock.mockImplementation((path:string,init?:RequestInit)=>{
    if(path==='/reading/books/uploads/status')return Promise.resolve({enabled:true,max_bytes:15728640})
    if(path==='/reading/books/uploads')return Promise.resolve({items:[{id:'private-one',title:'Моя EPUB',format:'epub',original_filename:'book.epub',size_bytes:1024,page_count:null}]})
    if(path==='/reading/books/uploads/private-one/reader-state'){
      if(init?.method==='PUT'){saved=JSON.parse(init.body as string);return Promise.resolve({...saved,checksum:'abc'})}
      return Promise.resolve({location:{format:'epub',chapter:1,position:60},bookmarks:[],checksum:'abc'})
    }
    if(path.startsWith('/reading/books/uploads/private-one/read'))return Promise.resolve({paragraphs:['Личный текст.'],chapters:[{title:'Глава 1',offset:0},{title:'Глава 2',offset:60}],total:120,next_offset:null})
    return original(path,init)
  })
  mount()
  fireEvent.click(screen.getByRole('button',{name:'Мои файлы'}))
  fireEvent.click(await screen.findByRole('button',{name:/Моя EPUB/}))
  await waitFor(()=>expect(screen.getByText('Личный текст.')).toBeInTheDocument())
  await waitFor(()=>expect(apiMock.mock.calls.some(([path])=>String(path).includes('/uploads/private-one/read?offset=60'))).toBe(true))
  fireEvent.click(screen.getAllByRole('button',{name:'Добавить закладку'}).at(-1)!)
  await waitFor(()=>expect(saved).toMatchObject({bookmarks:[{format:'epub',chapter:1,position:60}]}))
  expect(logs).toHaveLength(0)
})
function mount(){render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/education/reading?book=one']}><ReadingPage/></MemoryRouter></QueryClientProvider>)}
test('reading allows a free-text-only note and retains it after a failed save',async()=>{
  fail=true;mount()
  fireEvent.change(await screen.findByLabelText('Свободная заметка'),{target:{value:'Эта мысль напомнила мне о семье.'}})
  fireEvent.click(screen.getByRole('button',{name:'Сохранить чтение'}))
  await screen.findByText('Не удалось отправить')
  expect(screen.getByLabelText('Свободная заметка')).toHaveValue('Эта мысль напомнила мне о семье.')
  fireEvent.click(screen.getByRole('button',{name:'Сохранить чтение'}))
  await screen.findByText('Эта мысль напомнила мне о семье.',{selector:'p'})
  expect(logs).toHaveLength(1)
  expect(logs[0]).toMatchObject({page:null,reflection:{}})
  await waitFor(()=>expect(screen.getByLabelText('Свободная заметка')).toHaveValue(''))
})

test('catalog reader resumes a chapter and saves a bookmark without a reading log',async()=>{
 const original=apiMock.getMockImplementation()!
 const suggestion={id:'test-book',title:'Тестовый роман',author:'Автор',interest:'',genres:[],source:'https://example.test',description:'Книга',questions:[],check:'',available_offline:true}
 let saved:Record<string,unknown>|null=null
 apiMock.mockImplementation((path:string,init?:RequestInit)=>{
   if(path==='/library/books')return Promise.resolve({items:[suggestion]})
   if(path==='/reading/books/reader-state/test-book'){
     if(init?.method==='PUT'){saved=JSON.parse(init.body as string);return Promise.resolve({...saved,checksum:'abc'})}
     return Promise.resolve({location:{format:'epub',chapter:1,position:60},bookmarks:[],checksum:'abc'})
   }
   if(path.startsWith('/library/books/test-book/read'))return Promise.resolve({paragraphs:['Текст второй главы.'],total:120,next_offset:120,chapters:[{title:'Глава 1',offset:0},{title:'Глава 2',offset:60}],checksum:'abc'})
   return original(path,init)
 })
 mount()
 fireEvent.click(screen.getByRole('button',{name:'Библиотека'}))
 fireEvent.click(await screen.findByRole('button',{name:'Читать здесь'}))
 expect(await screen.findByText('Текст второй главы.')).toBeInTheDocument()
 expect(apiMock.mock.calls.some(([path])=>String(path).includes('offset=60'))).toBe(true)
 fireEvent.click(screen.getByText('Настройки чтения'))
 fireEvent.click(screen.getByRole('button',{name:'Добавить закладку'}))
 await waitFor(()=>expect(saved).toMatchObject({bookmarks:[{format:'epub',chapter:1,position:60}]}))
 expect(logs).toHaveLength(0)
})
test('saving a reading page updates the bookmark and the next reading step',async()=>{
  mount()
  await screen.findByText('Страницы 11–25')
  fireEvent.change(screen.getByLabelText('Страница (необязательно)'),{target:{value:'30'}})
  fireEvent.click(screen.getByRole('button',{name:'Сохранить чтение'}))
  await screen.findByText('Страницы 31–45')
  expect(screen.getByText('30 / 100 страниц')).toBeInTheDocument()
})

test('a pending book save cannot dismiss its dialog and retains the draft on late failure',async()=>{
  const original=apiMock.getMockImplementation()!
  let failSave!:(cause:Error)=>void
  apiMock.mockImplementation((path:string,init?:RequestInit)=>path==='/reading/books'&&init?.method==='POST'?new Promise((_,reject)=>{failSave=reject}):original(path,init))
  mount();fireEvent.click(await screen.findByRole('button',{name:'Записать свою книгу'}))
  const dialog=screen.getByRole('dialog');const form=within(dialog)
  fireEvent.change(form.getByLabelText('Название книги'),{target:{value:'Новая книга'}})
  fireEvent.click(form.getByText('Настроить чтение (необязательно)'))
  fireEvent.change(form.getByLabelText('Количество страниц'),{target:{value:'100'}})
  fireEvent.click(form.getByRole('button',{name:'Сохранить книгу'}))
  await waitFor(()=>expect(failSave).toBeTypeOf('function'))
  fireEvent(dialog,new Event('cancel',{bubbles:true,cancelable:true}))
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  failSave(new Error('Поздний отказ сервера'))
  await screen.findByText('Поздний отказ сервера')
  expect(within(screen.getByRole('dialog')).getByLabelText('Название книги')).toHaveValue('Новая книга')
})

test('a book outside the catalog can be saved by title alone',async()=>{
  const original=apiMock.getMockImplementation()!
  let saved:Record<string,unknown>|null=null
  apiMock.mockImplementation((path:string,init?:RequestInit)=>{
    if(path==='/reading/books'&&init?.method==='POST'){
      saved=JSON.parse(init.body as string)
      return Promise.resolve({...book,...saved,id:'manual'})
    }
    return original(path,init)
  })
  mount();fireEvent.click(await screen.findByRole('button',{name:'Записать свою книгу'}))
  const form=within(screen.getByRole('dialog'))
  fireEvent.change(form.getByLabelText('Название книги'),{target:{value:'Моя новая книга'}})
  fireEvent.click(form.getByRole('button',{name:'Сохранить книгу'}))
  await waitFor(()=>expect(saved).toMatchObject({title:'Моя новая книга',pages:0,status:'reading'}))
})

test('an inline reading save cannot close an existing note editor',async()=>{
  logs=[{id:'old',book_id:'one',date:'2026-10-09',page:null,chapter:'',text:'Предыдущая заметка',reflection:{},deleted:false}]
  const original=apiMock.getMockImplementation()!
  let finish!:(item:Record<string,unknown>)=>void
  apiMock.mockImplementation((path:string,init?:RequestInit)=>path==='/reading/books/one/logs'&&init?.method==='POST'?new Promise(resolve=>{finish=resolve}):original(path,init))
  mount();await screen.findByText('Предыдущая заметка',{selector:'p'})
  fireEvent.change(screen.getByLabelText('Свободная заметка'),{target:{value:'Новая заметка'}})
  fireEvent.click(screen.getByRole('button',{name:'Сохранить чтение'}))
  await waitFor(()=>expect(finish).toBeTypeOf('function'))
  fireEvent.click(screen.getByRole('button',{name:'Изменить заметку'}))
  fireEvent.change(within(screen.getByRole('dialog')).getByLabelText('Свободная заметка'),{target:{value:'Несохранённое дополнение'}})
  const item={...logs[0],id:'new',text:'Новая заметка'};logs.push(item);finish(item)
  await waitFor(()=>expect(screen.getByRole('status')).toHaveTextContent('Чтение сохранено'))
  expect(within(screen.getByRole('dialog')).getByLabelText('Свободная заметка')).toHaveValue('Несохранённое дополнение')
})
