/** API wrapper foundation. Refresh/session logic is implemented in the auth phase. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId?: string
  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
  }
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
let accessTokenReader: (() => string | null) | undefined

/** Register an in-memory access-token source. Do not use localStorage. */
export function setAccessTokenReader(reader: (() => string | null) | undefined): void {
  accessTokenReader = reader
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  const token = accessTokenReader?.()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_BASE}${path.startsWith('/') ? path : `/${path}`}`, {
    ...init,
    headers,
    signal: init.signal,
  })
  if (!response.ok) {
    let payload: { code?: string; message?: string; request_id?: string } = {}
    try { payload = await response.json() as typeof payload } catch { /* response may not be JSON */ }
    throw new ApiError(response.status, payload.code || 'http_error', payload.message || 'Request failed', payload.request_id)
  }
  if (response.status === 204) return undefined as T
  return await response.json() as T
}
