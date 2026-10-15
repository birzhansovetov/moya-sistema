import {test,expect} from 'vitest'
import {legacyDestination} from './navigation'
test.each([
 ['/education/go','?plan=p&lesson=l','#study-lesson','/profession/go?plan=p&lesson=l#study-lesson'],
 ['/education/reading','?book=b','','/books?book=b'],
 ['/education','','','/books'],
 ['/profession','?plan=p','','/profession/backend?plan=p'],
 ['/profession','','',null],['/unknown','','',null],
])('preserves saved destinations %s',(path,search,hash,expected)=>expect(legacyDestination(path,search,hash)).toBe(expected))
