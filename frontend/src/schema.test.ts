/// <reference types="vite/client" />
import html from '../index.html?raw'
import {describe,it,expect} from 'vitest'
describe('public application structured data',()=>{
 it('exposes one parseable JSON-LD graph before React runs',()=>{
  const document=new DOMParser().parseFromString(html,'text/html')
  const blocks=document.querySelectorAll('script[type="application/ld+json"]')
  expect(blocks).toHaveLength(1)
  const graph=JSON.parse(blocks[0].textContent!)
  expect(graph['@context']).toBe('https://schema.org')
  expect(graph['@graph'].map((node:{'@type':string})=>node['@type'])).toEqual(['WebSite','WebApplication'])
  for(const node of graph['@graph']){
   expect(node.name).toBe('Моя система')
   expect(node.url).toBe('https://moya-sistema.pages.dev/')
   expect(node.inLanguage).toBe('ru')
   expect(node['@id']).toMatch(/^https:\/\/moya-sistema\.pages\.dev\/#/)
  }
  expect(graph['@graph'][0].about['@id']).toBe(graph['@graph'][1]['@id'])
  expect(JSON.stringify(graph)).not.toMatch(/aggregateRating|ratingValue|offers|email|password|plan_id|user_id|SearchAction/)
 })
})
