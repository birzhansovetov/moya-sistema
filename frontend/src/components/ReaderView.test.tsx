import {render,screen,fireEvent,cleanup} from '@testing-library/react'
import {test,expect,afterEach,vi} from 'vitest'
import {ReaderView} from './ReaderView'
afterEach(cleanup)
test('reader isolates reading, closes with Escape and restores app state',()=>{const close=vi.fn();const view=render(<ReaderView title="Әңгімелер" onClose={close}><p>Книга</p></ReaderView>);expect(document.documentElement).toHaveAttribute('data-reading','true');expect(screen.getByRole('dialog',{name:'Әңгімелер'})).toBeInTheDocument();fireEvent.keyDown(screen.getByRole('dialog'),{key:'Escape'});expect(close).toHaveBeenCalledTimes(1);view.unmount();expect(document.documentElement).not.toHaveAttribute('data-reading')})
