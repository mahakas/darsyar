import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearAccessToken, getAccessToken, refreshSession, setAccessToken } from './client'

function setCookies(cookie: string): void {
  Object.defineProperty(globalThis, 'document', {
    configurable: true,
    value: { cookie },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  clearAccessToken()
})

describe('refreshSession', () => {
  it('retries a concurrent 409 instead of reporting a logout', async () => {
    setCookies('darsyar_csrf=csrf-token')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 409 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ access_token: 'fresh-token' }), { status: 200 }),
      )
    vi.stubGlobal('fetch', fetchMock)
    setAccessToken('stale-token')

    await expect(refreshSession()).resolves.toBe(true)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(getAccessToken()).toBe('fresh-token')
  })

  it('clears the access token when the CSRF cookie is missing', async () => {
    setCookies('')
    setAccessToken('stale-token')

    await expect(refreshSession()).resolves.toBe(false)
    expect(getAccessToken()).toBeNull()
  })
})
