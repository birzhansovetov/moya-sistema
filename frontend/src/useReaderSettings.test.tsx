import {renderHook,act} from '@testing-library/react'
import {it,expect} from 'vitest'
import {useReaderSettings} from './useReaderSettings'
it('persists validated reader settings across readers',()=>{localStorage.clear();const first=renderHook(()=>useReaderSettings());act(()=>first.result.current.update({theme:'dark',fontSize:22,lineHeight:2}));first.unmount();const next=renderHook(()=>useReaderSettings());expect(next.result.current.settings).toEqual({theme:'dark',fontSize:22,lineHeight:2})})
