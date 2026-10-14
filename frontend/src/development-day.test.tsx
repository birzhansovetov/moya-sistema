import {render,screen} from '@testing-library/react'
import {QueryClient,QueryClientProvider} from '@tanstack/react-query'
import {MemoryRouter} from 'react-router-dom'
import {vi} from 'vitest'
import {DevelopmentDay} from './components/DevelopmentDay'
vi.mock('./auth',()=>({useAuth:()=>({user:{id:'one'}})}))
vi.mock('./api',()=>({api:async()=>({items:[{id:'book',title:'Читаемая книга',status:'reading',current_page:10,next_page:25,pages:100,deleted:false}],total:1,limit:100,offset:0})}))
test('daily personal and reading links preserve the selected date and original record',async()=>{
 render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><DevelopmentDay date="2026-10-09" personalItems={[{id:'event',title:'Встреча с другом',date:'2026-10-09',kind:'event',completed:false}]}/></MemoryRouter></QueryClientProvider>)
 expect(screen.getByRole('link',{name:/Встреча с другом/})).toHaveAttribute('href','/personal?entry=event&date=2026-10-09')
 expect(await screen.findByRole('link',{name:/Читаемая книга/})).toHaveAttribute('href','/education/reading?book=book&date=2026-10-09')
 expect(screen.getByText(/страницы 11–25/)).toBeInTheDocument()
})
