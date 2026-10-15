import {render,screen,cleanup} from '@testing-library/react'
import {afterEach,test,expect} from 'vitest'
import {Pronunciation} from './Pronunciation'
afterEach(cleanup)
test('missing speech support is explicit and does not pretend audio exists',()=>{render(<Pronunciation text="Әңгіме" language="kk"/>);expect(screen.getByRole('button',{name:'Произнести слово'})).toBeDisabled();expect(screen.getByRole('status')).toHaveTextContent('На этом устройстве нет голоса для этого языка')})
