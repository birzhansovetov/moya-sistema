import {describe,it,expect} from 'vitest'
import {sectionForPath} from './assistantSections'
describe('assistant route coverage',()=>{
 it('maps all routes including five languages and auth',()=>{
  for(const path of ['/','/sections','/education','/education/java','/education/go','/profession','/health','/health/sport','/health/nutrition','/health/calories','/finance','/personal','/education/reading','/tasks','/calendar','/profile','/onboarding','/login','/register','/verify-email','/reset-password','/forgot-password','/languages',...['english','kazakh','korean','turkish','spanish'].map(x=>'/languages/'+x)])expect(sectionForPath(path)).not.toBeNull()
  expect(sectionForPath('/languages/kazakh')).toBe('kazakh')
  expect(sectionForPath('/unknown')).toBeNull()
 })
})
