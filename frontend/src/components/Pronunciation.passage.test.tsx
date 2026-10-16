import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {afterEach,test,expect,vi} from 'vitest'
import {Pronunciation} from './Pronunciation'
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
test('a passage has an explicit listen action using its own language and can be stopped',()=>{
 const speak=vi.fn(),cancel=vi.fn();vi.stubGlobal('speechSynthesis',{getVoices:()=>[{lang:'ko-KR',name:'Korean'}],addEventListener:vi.fn(),removeEventListener:vi.fn(),speak,cancel});vi.stubGlobal('SpeechSynthesisUtterance',class{constructor(public text:string){}})
 render(<Pronunciation text="아이는 우유를 마셔요." language="ko" label="Прослушать текст"/>)
 fireEvent.click(screen.getByRole('button',{name:'Прослушать текст'}))
 expect(speak.mock.calls[0][0]).toMatchObject({text:'아이는 우유를 마셔요.',lang:'ko-KR'})
 fireEvent.click(screen.getByRole('button',{name:'Остановить'}));expect(cancel).toHaveBeenCalledTimes(2)
})
