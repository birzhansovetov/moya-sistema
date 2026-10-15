import {render,screen,fireEvent,waitFor} from '@testing-library/react'
import {describe,it,expect,vi,beforeEach} from 'vitest'
import {MemoryRouter} from 'react-router-dom'
import {AssistantProvider,SectionAssistant} from './SectionAssistant'
vi.mock('../auth',()=>({useAuth:()=>({user:{id:'test'}})}))
const api=vi.fn()
vi.mock('../api',()=>({api:(...args:unknown[])=>api(...args)}))
function setup(){return render(<MemoryRouter><AssistantProvider><SectionAssistant section="finance"/></AssistantProvider></MemoryRouter>)}
beforeEach(()=>{api.mockReset();api.mockResolvedValue({topics:[{id:'finance-1',label:'Как начать учёт?'}],materials:[]})})
describe('section assistant',()=>{
 it('sends only predefined IDs and labels real source',async()=>{
  setup();fireEvent.click(screen.getByRole('button',{name:'Помощник'}));await screen.findByRole('button',{name:'Как начать учёт?'})
  api.mockResolvedValueOnce({request_id:'one',source:'cloud_ai',text:'Отмечайте операции.',material:null,links:[],notice:null})
  fireEvent.click(screen.getByRole('button',{name:'Как начать учёт?'}))
  expect(await screen.findByText('Объяснение ИИ · Gemini')).toBeInTheDocument()
  expect(JSON.parse(api.mock.calls[1][1].body)).toEqual({section:'finance',topic_id:'finance-1',material:null})
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:'Закрыть'}))
  await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
 })
 it('labels authored fallback honestly',async()=>{
  setup();fireEvent.click(screen.getByRole('button',{name:'Помощник'}));await screen.findByRole('button',{name:'Как начать учёт?'})
  api.mockResolvedValueOnce({request_id:null,source:'authored',text:'Готовый ответ.',material:null,links:[],notice:null})
  fireEvent.click(screen.getByRole('button',{name:'Как начать учёт?'}))
  expect(await screen.findByText('Готовая подсказка')).toBeInTheDocument()
 })
})

it('ignores an answer after route navigation and restores focus on Escape',async()=>{
 const {useNavigate}=await import('react-router-dom')
 function Navigation(){const navigate=useNavigate();return <button onClick={()=>navigate('/finance')}>Сменить раздел</button>}
 render(<MemoryRouter initialEntries={['/health/sport']}><AssistantProvider><SectionAssistant section="sport"/><Navigation/></AssistantProvider></MemoryRouter>)
 const trigger=screen.getByRole('button',{name:'Помощник'});trigger.focus();fireEvent.click(trigger)
 await screen.findByRole('button',{name:'Как начать учёт?'})
 let resolve!:(value:unknown)=>void
 api.mockImplementationOnce(()=>new Promise(r=>{resolve=r}))
 fireEvent.click(screen.getByRole('button',{name:'Как начать учёт?'}))
 fireEvent.click(screen.getByRole('button',{name:'Сменить раздел'}))
 resolve({source:'cloud_ai',text:'УСТАРЕВШИЙ ОТВЕТ',request_id:null,material:null,links:[],notice:null})
 await waitFor(()=>expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
 expect(screen.queryByText('УСТАРЕВШИЙ ОТВЕТ')).not.toBeInTheDocument()
 fireEvent.click(trigger);await screen.findByRole('dialog');fireEvent.keyDown(screen.getByRole('dialog'),{key:'Escape'})
 await waitFor(()=>expect(trigger).toHaveFocus())
})
