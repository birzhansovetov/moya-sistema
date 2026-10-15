export type ExplainFormat='default'|'simple'|'example'|'steps'|'brief'
export type NextAction={id:string;label:string;kind:'route'|'local';to?:string;handler?:string}
const routes=new Set(['/','/sections','/education','/education/java','/education/go','/profession','/languages','/languages/english','/languages/kazakh','/languages/korean','/languages/turkish','/languages/spanish','/health','/health/sport','/health/nutrition','/health/calories','/finance','/education/reading','/personal','/tasks','/calendar','/profile','/onboarding','/login'])
export function isAssistantRoute(to:string|undefined):to is string{return !!to&&routes.has(to.split('#')[0])&&(!to.includes('#')||/^#(?:recipe-[a-zA-Z0-9_-]+|sport-library)$/.test(to.slice(to.indexOf('#'))))}
