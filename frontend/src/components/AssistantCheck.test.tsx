import {render,screen,fireEvent} from '@testing-library/react'
import {it,expect,vi} from 'vitest'
import {AssistantCheck} from './AssistantCheck'
const api=vi.fn()
vi.mock('../api',()=>({api:(...args:unknown[])=>api(...args)}))
it('submits only issued token and option, never a completion request',async()=>{
 api.mockResolvedValueOnce({available:true,token:'issued',question:{prompt:'Выберите понятие',chapter_title:'Глава',options:[{id:'a',label:'Вариант A'},{id:'b',label:'Вариант B'}]}}).mockResolvedValueOnce({correct:true,explanation:'Разбор'})
 render(<AssistantCheck section="java" material={{kind:'lesson',id:'java:java-01',version:'v2'}}/>)
 fireEvent.click(screen.getByRole('button',{name:'Открыть вопрос'}))
 fireEvent.click(await screen.findByLabelText('Вариант A'))
 expect(screen.queryByText('Разбор')).not.toBeInTheDocument()
 fireEvent.click(screen.getByRole('button',{name:'Проверить'}))
 expect(await screen.findByText('Верно')).toBeInTheDocument()
 expect(JSON.parse(api.mock.calls[1][1].body)).toEqual({token:'issued',option_id:'a'})
 expect(api.mock.calls.map(c=>c[0])).toEqual(['/assistant/checks/issue','/assistant/checks/answer'])
})
