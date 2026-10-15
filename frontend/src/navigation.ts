export function legacyDestination(pathname:string,search:string,hash:string):string|null {
 const paths:Record<string,string>={'/education':'/books','/education/reading':'/books','/education/java':'/profession/java','/education/go':'/profession/go'}
 const target=paths[pathname] || (pathname==='/profession' && new URLSearchParams(search).has('plan') ? '/profession/backend' : null)
 return target ? target+search+hash : null
}
