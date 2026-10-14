type Env = { BACKEND_ORIGIN: string }
type Context = { request: Request; env: Env }

export async function onRequest({ request, env }: Context): Promise<Response> {
  let backend: URL
  try { backend = new URL(env.BACKEND_ORIGIN) }
  catch { return new Response('Backend origin is not configured', { status: 503 }) }
  if (backend.protocol !== 'https:' || backend.pathname !== '/' || backend.search || backend.hash) {
    return new Response('Backend origin is invalid', { status: 503 })
  }
  const incoming = new URL(request.url)
  const target = new URL(incoming.pathname + incoming.search, backend)
  const headers = new Headers(request.headers)
  headers.delete('host')
  headers.delete('origin')
  headers.set('X-Forwarded-Host', incoming.host)
  headers.set('X-Forwarded-Proto', 'https')
  let upstream: Response
  try {
    upstream = await fetch(target, { method: request.method, headers, body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body, redirect: 'manual' })
  } catch {
    return new Response('Сервис временно недоступен. Повторите попытку.', { status: 503 })
  }
  const outgoing = new Headers(upstream.headers)
  outgoing.delete('set-cookie')
  const cookies = upstream.headers.getSetCookie?.() || []
  for (const cookie of cookies) outgoing.append('Set-Cookie', cookie)
  outgoing.set('Cache-Control', 'no-store')
  return new Response(upstream.body, { status: upstream.status, statusText: upstream.statusText, headers: outgoing })
}
