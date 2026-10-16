import {it,expect} from 'vitest'
import {legacyDestination} from './navigation'
it('preserves old mixed-case and trailing-slash deep links',()=>{expect(legacyDestination('/Education/Go/','?plan=p&lesson=l','#study-lesson')).toBe('/profession/go?plan=p&lesson=l#study-lesson')})
