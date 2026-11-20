import { afterEach, expect, it, vi } from 'vitest'
import { setAccessToken } from './client'
import { streamChat } from './chat'

function setCookies(cookie: string): void {
  Object.defineProperty(globalThis, 'document', {
    configurable: true,
    value: { cookie },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  setAccessToken(null)
})

it('refreshes the access token after a 401 before streaming', async () => {
  setCookies('darsyar_csrf=csrf-token')
  setAccessToken('expired-token')
  const sse = 'id:1\nevent:done\ndata:{"status":"completed"}\n\n'
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(new Response(null, { status: 401 }))
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ access_token: 'fresh-token' }), { status: 200 }),
    )
    .mockResolvedValueOnce(new Response(sse, { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  let terminal: string | undefined
  await streamChat('hello', null, 'client-request-123456', {
    onDone: (status) => {
      terminal = status
    },
  })

  expect(fetchMock).toHaveBeenCalledTimes(3)
  const authHeaders = fetchMock.mock.calls.map((call) => (call[1] as RequestInit).headers)
  expect((authHeaders[0] as Headers).get('authorization')).toBe('Bearer expired-token')
  expect((authHeaders[2] as Headers).get('authorization')).toBe('Bearer fresh-token')
  expect(terminal).toBe('completed')
})

it('replays from Last-Event-ID and exposes sources/snapshots after a disconnect', async () => {
  const first = 'id:1\nevent:ack\ndata:{"conversation_id":"c1","message_id":"m1"}\n\n'
    + 'id:2\nevent:delta\ndata:{"content":"partial"}\n\n'
  const second = 'id:3\nevent:sources\ndata:{"citations":["[کتاب: ریاضی]"]}\n\n'
    + 'id:4\nevent:snapshot\ndata:{"content":"partial complete"}\n\n'
    + 'id:5\nevent:done\ndata:{"status":"completed"}\n\n'
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(first, { status: 200 }))
    .mockResolvedValueOnce(new Response(second, { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)

  const sources: string[] = []
  const snapshots: string[] = []
  let terminal: string | undefined
  await streamChat('hello', null, 'client-request-123456', {
    onSources: (citations) => { sources.push(...citations) },
    onSnapshot: (text) => { snapshots.push(text) },
    onDone: (status) => { terminal = status },
  })

  expect(fetchMock).toHaveBeenCalledTimes(2)
  const replayHeaders = (fetchMock.mock.calls[1][1] as RequestInit).headers as Headers
  expect(replayHeaders.get('last-event-id')).toBe('2')
  expect(sources).toEqual(['[کتاب: ریاضی]'])
  expect(snapshots).toEqual(['partial complete'])
  expect(terminal).toBe('completed')
})
