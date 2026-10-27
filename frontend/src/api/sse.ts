/** Minimal fetch-stream parser for Server-Sent Events; chat transport is wired in phase 3. */
export type SseMessage = { event: string; data: string; id?: string }

export async function readSseStream(
  response: Response,
  onMessage: (message: SseMessage) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.ok) throw new Error(`SSE request failed with status ${response.status}`)
  if (!response.body) throw new Error('Streaming response body is unavailable')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventName = 'message'
  let eventId: string | undefined
  let dataLines: string[] = []
  const dispatch = () => {
    if (dataLines.length) onMessage({ event: eventName, data: dataLines.join('\n'), id: eventId })
    eventName = 'message'
    dataLines = []
  }
  try {
    while (true) {
      if (signal?.aborted) { await reader.cancel(); return }
      const { value, done } = await reader.read()
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n').replace(/\r/g, '\n')
      let boundary: number
      while ((boundary = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 1)
        if (line === '') { dispatch(); continue }
        if (line.startsWith(':')) continue
        const colon = line.indexOf(':')
        const field = colon < 0 ? line : line.slice(0, colon)
        const valueText = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '')
        if (field === 'event') eventName = valueText
        else if (field === 'data') dataLines.push(valueText)
        else if (field === 'id' && !valueText.includes('\0')) eventId = valueText
      }
      if (done) { dispatch(); return }
    }
  } finally {
    reader.releaseLock()
  }
}
