import { afterEach, describe, expect, it, vi } from 'vitest'
import { sendMessage, fetchHistory, compareProducts } from './api.js'

function mockFetchOnce(status, body) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('sendMessage', () => {
  it('posts the question and thread_id, and returns the parsed response', async () => {
    mockFetchOnce(200, { answer: 'hi there', context: 'MOBILE', thread_id: 'abc', product: null })

    const result = await sendMessage('recommend a phone', 'abc')

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/chat',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ question: 'recommend a phone', thread_id: 'abc' }),
      })
    )
    expect(result.answer).toBe('hi there')
  })

  it('throws with the server-provided detail message on a non-2xx response', async () => {
    mockFetchOnce(500, { detail: 'boom' })
    await expect(sendMessage('hi', 'abc')).rejects.toThrow('boom')
  })

  it('throws a generic message when the error body has no detail field', async () => {
    mockFetchOnce(504, {})
    await expect(sendMessage('hi', 'abc')).rejects.toThrow('504')
  })

  it('does not send an X-API-Key header when VITE_API_KEY is unset', async () => {
    mockFetchOnce(200, { answer: 'hi', context: 'MOBILE', thread_id: 'abc' })
    await sendMessage('hi', 'abc')
    const headers = global.fetch.mock.calls[0][1].headers
    expect(headers['X-API-Key']).toBeUndefined()
  })
})

describe('fetchHistory', () => {
  it('GETs the history endpoint for the given thread id', async () => {
    mockFetchOnce(200, [{ role: 'user', content: 'hi' }])
    const result = await fetchHistory('abc')
    expect(global.fetch).toHaveBeenCalledWith('/api/history/abc', expect.any(Object))
    expect(result).toEqual([{ role: 'user', content: 'hi' }])
  })

  it('returns an empty array when the body is empty', async () => {
    mockFetchOnce(200, null)
    const result = await fetchHistory('abc')
    expect(result).toEqual([])
  })
})

describe('compareProducts', () => {
  it('posts the category and product names, and returns the comparison', async () => {
    const comparison = {
      category: 'laptop',
      products: { A: { price: 1 }, B: { price: 2 } },
      differing_fields: ['price'],
      missing: [],
    }
    mockFetchOnce(200, comparison)

    const result = await compareProducts('laptop', ['A', 'B'])

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/compare',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ category: 'laptop', product_names: ['A', 'B'] }),
      })
    )
    expect(result).toEqual(comparison)
  })

  it('throws with the server-provided detail message on a non-2xx response', async () => {
    mockFetchOnce(400, { detail: 'not enough products' })
    await expect(compareProducts('laptop', ['A'])).rejects.toThrow('not enough products')
  })
})
