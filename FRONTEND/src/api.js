// Base URL for the FastAPI backend. In dev, Vite proxies "/api" straight to
// the backend (see vite.config.js), so the default of "/api" works with no
// extra setup. For a separately hosted backend, set VITE_API_BASE_URL to a
// full URL (e.g. https://api.example.com/api) at build time.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

// Only needed if the backend has API_KEY set (see config.dummy.py). Unset
// by default, matching the backend's own "open unless configured" default.
const API_KEY = import.meta.env.VITE_API_KEY

function buildHeaders() {
  const headers = { 'Content-Type': 'application/json' }
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY
  }
  return headers
}

async function parseJsonSafely(response) {
  try {
    return await response.json()
  } catch {
    return null
  }
}

export async function sendMessage(question, threadId) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ question, thread_id: threadId }),
  })

  const data = await parseJsonSafely(response)

  if (!response.ok) {
    const message = data?.detail || `Request failed with status ${response.status}`
    throw new Error(message)
  }

  return data
}

export async function fetchHistory(threadId) {
  const response = await fetch(`${API_BASE}/history/${encodeURIComponent(threadId)}`, {
    headers: buildHeaders(),
  })
  const data = await parseJsonSafely(response)
  if (!response.ok) {
    const message = data?.detail || `Request failed with status ${response.status}`
    throw new Error(message)
  }
  return data ?? []
}

// Deterministic, LLM-free product comparison (POST /api/compare) -- backs
// the "Compare top matches" action under a candidate list (see
// components/CandidateScores.jsx). category is the backend's table key
// ('phone' | 'laptop' | 'headphone'), not the MOBILE/LAPTOP/HEADPHONE label
// used elsewhere in the UI.
export async function compareProducts(category, productNames) {
  const response = await fetch(`${API_BASE}/compare`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ category, product_names: productNames }),
  })
  const data = await parseJsonSafely(response)
  if (!response.ok) {
    const message = data?.detail || `Request failed with status ${response.status}`
    throw new Error(message)
  }
  return data
}
