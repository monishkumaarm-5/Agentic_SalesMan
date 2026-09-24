import { afterEach, describe, expect, it, vi } from 'vitest'
import { parseSSE, streamChat } from './client.js'

function sseResponse(chunks, init = {}) {
  const encoder = new TextEncoder()
  const body = new ReadableStream({
    start(controller) {
      chunks.forEach((c) => controller.enqueue(encoder.encode(c)))
      controller.close()
    },
  })
  return { ok: true, status: 200, body, ...init }
}

afterEach(() => vi.restoreAllMocks())

describe('parseSSE', () => {
  it('splits complete events and keeps the partial tail', () => {
    const { events, rest } = parseSSE('event: status\ndata: {"step":"a"}\n\n: ping\n\nevent: final\ndata: {"x"')
    expect(events).toEqual([{ event: 'status', data: { step: 'a' } }])
    expect(rest).toBe('event: final\ndata: {"x"')
  })
})

describe('streamChat', () => {
  it('reports status events and resolves with the final response, across chunk boundaries', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      sseResponse([
        'event: start\ndata: {"thread_id":"t"}\n\nevent: status\ndata: {"step":"understand","label":"Understanding"}\n\neve',
        'nt: final\ndata: {"answer":"hi","thread_id":"t"}\n\n',
      ]),
    )
    const onStatus = vi.fn()
    const result = await streamChat('hello', 't', { onStatus })
    expect(result).toEqual({ answer: 'hi', thread_id: 't' })
    expect(onStatus).toHaveBeenCalledWith({ step: 'understand', label: 'Understanding' })
    const [url, init] = global.fetch.mock.calls[0]
    expect(url).toBe('/api/chat/stream')
    expect(JSON.parse(init.body)).toEqual({ message: 'hello', thread_id: 't' })
  })

  it('throws the server error event message', async () => {
    global.fetch = vi.fn().mockResolvedValue(sseResponse(['event: error\ndata: {"message":"busy"}\n\n']))
    await expect(streamChat('x', 't')).rejects.toThrow('busy')
  })

  it('throws the HTTP detail for non-2xx responses', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ detail: 'Invalid key' }) })
    await expect(streamChat('x', 't')).rejects.toThrow('Invalid key')
  })

  it('gives a friendly message when the network is down', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(streamChat('x', 't')).rejects.toThrow(/Can't reach/)
  })
})
