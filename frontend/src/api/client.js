/**
 * Backend API client.
 *
 * `streamChat` talks to POST /api/chat/stream (server-sent events) so the
 * UI can show what the assistant is doing while it works.
 */

// `||` so an empty build arg still falls back to the same-origin default.
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const API_KEY = import.meta.env.VITE_API_KEY

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function headers(extra = {}) {
  const h = { 'Content-Type': 'application/json', ...extra }
  if (API_KEY) h['X-API-Key'] = API_KEY
  return h
}

async function errorFrom(response) {
  let detail
  try {
    detail = (await response.json())?.detail
  } catch {
    // not JSON
  }
  if (typeof detail !== 'string') {
    detail =
      response.status === 429
        ? "You're sending messages too quickly -- please wait a moment."
        : `Request failed (${response.status})`
  }
  return new ApiError(detail, response.status)
}

async function request(path, { signal, ...options } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, { headers: headers(), signal, ...options })
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw new ApiError("Can't reach the assistant right now. Check your connection and try again.", 0)
  }
  if (!response.ok) throw await errorFrom(response)
  try {
    return await response.json()
  } catch {
    return null
  }
}

/** Parses an SSE text buffer into complete events plus the leftover tail. */
export function parseSSE(buffer) {
  const events = []
  const blocks = buffer.split(/\r?\n\r?\n/)
  const rest = blocks.pop() ?? ''
  for (const block of blocks) {
    let event = 'message'
    const data = []
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith(':')) continue
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
    }
    if (!data.length) continue
    try {
      events.push({ event, data: JSON.parse(data.join('\n')) })
    } catch {
      // ignore malformed event
    }
  }
  return { events, rest }
}

/**
 * Sends a message and resolves with the final ChatResponse.
 * `onStatus({step, label})` is called as the assistant works.
 */
export async function streamChat(message, threadId, { onStatus, signal } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: headers({ Accept: 'text/event-stream' }),
      body: JSON.stringify({ message, thread_id: threadId }),
      signal,
    })
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw new ApiError("Can't reach the assistant right now. Check your connection and try again.", 0)
  }
  if (!response.ok) throw await errorFrom(response)
  if (!response.body) return sendMessage(message, threadId, signal)

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const { events, rest } = parseSSE(done ? `${buffer}\n\n` : buffer)
    buffer = rest
    for (const { event, data } of events) {
      if (event === 'status') onStatus?.(data)
      else if (event === 'final') return data
      else if (event === 'error') throw new ApiError(data.message || 'Something went wrong.', 500)
    }
    if (done) break
  }
  throw new ApiError('The connection closed before the answer arrived. Please try again.', 0)
}

export function sendMessage(message, threadId, signal) {
  return request('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, thread_id: threadId }),
    signal,
  })
}

export const getCompany = (signal) => request('/company', { signal })
export const getCategories = (signal) => request('/categories', { signal })
export const getHistory = (threadId, signal) =>
  request(`/threads/${encodeURIComponent(threadId)}/history`, { signal })
