import {render,screen,fireEvent,waitFor} from '@testing-library/react'
import {vi,it,expect} from 'vitest'
import {StudyHelp} from './StudyHelp'
vi.mock('../api',()=>({api:vi.fn()}))
import {api} from '../api'
it('labels cloud output and never offers to send private answers to it',async()=>{
 vi.mocked(api).mockResolvedValue({request_id:'qa',source:'cloud_ai',stage:'next_step',text:'Проверьте этап подготовки.',next_stage_token:'token',allow_local_answer:false})
 render(<StudyHelp planId="p" lessonId="l" questionIndex={0} attemptId="a" answerText="PRIVATE"/> )
 fireEvent.click(screen.getByRole('button',{name:'Объяснить иначе'}))
 await waitFor(()=>expect(screen.getByText('Объяснение ИИ · Gemini')).toBeInTheDocument())
 expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
 expect(JSON.stringify(vi.mocked(api).mock.calls)).not.toContain('PRIVATE')
})
