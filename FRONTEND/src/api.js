/**
 * API client — single fetch helper with error handling.
 *
 * Improvements:
 *  - AbortController support for cancellable requests
 *  - Retry-friendly: callers can pass an AbortSignal
 *  - Explicit typing of each endpoint for discoverability
 */

// `||` rather than `??`: an empty build arg must fall back to the default too.
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
const API_KEY = import.meta.env.VITE_API_KEY

function buildHeaders() {
  const headers = { 'Content-Type': 'application/json' }
  if (API_KEY) headers['X-API-Key'] = API_KEY
  return headers
}

async function parseJsonSafely(response) {
  try {
    return await response.json()
  } catch {
    return null
  }
}

/**
 * Centralised fetch helper.
 *
 * @param {string} endpoint  Path relative to API_BASE
 * @param {RequestInit & { signal?: AbortSignal }} [options]
 * @returns {Promise<any>}
 */
async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`

  let response
  try {
    response = await fetch(url, {
      headers: buildHeaders(),
      ...options,
    })
  } catch (err) {
    // Network failure or aborted request
    if (err.name === 'AbortError') throw err
    throw new Error('Network error — please check your connection and try again.')
  }

  const data = await parseJsonSafely(response)

  if (!response.ok) {
    const message = data?.detail || `Request failed (${response.status})`
    throw new Error(message)
  }

  return data
}

/* ── Public API ───────────────────────────────────────── */

export async function sendMessage(question, threadId, signal) {
  return request('/chat', {
    method: 'POST',
    body: JSON.stringify({ question, thread_id: threadId }),
    signal,
  })
}

export async function fetchHistory(threadId, signal) {
  const data = await request(`/history/${encodeURIComponent(threadId)}`, { signal })
  return Array.isArray(data) ? data : []
}

export async function getCompanyInfo(signal) {
  return request('/company', { signal })
}

export async function getCategories(signal) {
  return request('/categories', { signal })
}

export async function compareProducts(category, productNames, signal) {
  return request('/compare', {
    method: 'POST',
    body: JSON.stringify({ category, product_names: productNames }),
    signal,
  })
}