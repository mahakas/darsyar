/** Authenticated API client: access tokens stay in memory; refresh stays HttpOnly. */
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
let accessToken: string | null = null
let refreshInFlight: Promise<boolean> | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function clearAccessToken(): void {
  accessToken = null
}

export function getAccessToken(): string | null {
  return accessToken
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const prefix = `${name}=`
  const item = document.cookie.split(';').map((part) => part.trim()).find((part) => part.startsWith(prefix))
  if (!item) return null
  try {
    return decodeURIComponent(item.slice(prefix.length))
  } catch {
    return item.slice(prefix.length)
  }
}

/** Restore/rotate the in-memory access token using the HttpOnly refresh cookie. */
export async function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const csrfToken = readCookie('darsyar_csrf')
      if (!csrfToken) {
        clearAccessToken()
        return false
      }
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { Accept: 'application/json', 'X-CSRF-Token': csrfToken },
      })
      if (response.status === 409) {
        // ADR-046: concurrent refresh conflict is retryable, not a logout signal.
        throw new ApiError(409, 'refresh_conflict_retry', 'The session is being refreshed. Retry shortly.')
      }
      if (!response.ok) {
        clearAccessToken()
        return false
      }
      const payload = await response.json() as { access_token?: string }
      if (!payload.access_token) {
        clearAccessToken()
        return false
      }
      setAccessToken(payload.access_token)
      return true
    })().finally(() => {
      refreshInFlight = null
    })
  }
  return refreshInFlight
}

async function readApiError(response: Response): Promise<ApiError> {
  let payload: { code?: string; message?: string; request_id?: string } = {}
  try {
    payload = await response.json() as typeof payload
  } catch {
    // Some gateways may return an empty or non-JSON error response.
  }
  return new ApiError(
    response.status,
    payload.code || 'http_error',
    payload.message || 'Request failed',
    payload.request_id,
  )
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const url = `${API_BASE}${normalizedPath}`
  const isAuthRoute = normalizedPath.startsWith('/auth/')
  const send = async (allowRefresh: boolean): Promise<T> => {
    const headers = new Headers(init.headers)
    headers.set('Accept', 'application/json')
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
    else headers.delete('Authorization')

    const response = await fetch(url, {
      ...init,
      credentials: init.credentials ?? 'include',
      headers,
      signal: init.signal,
    })
    if (response.status === 401 && allowRefresh && !isAuthRoute) {
      if (await refreshSession()) return send(false)
    }
    if (!response.ok) throw await readApiError(response)
    if (response.status === 204) return undefined as T
    return await response.json() as T
  }
  return send(true)
}
