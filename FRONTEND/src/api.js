// Base URL for the FastAPI backend. In dev, Vite proxies "/api" straight to
// the backend (see vite.config.js), so the default of "/api" works with no
// extra setup. For a separately hosted backend, set VITE_API_BASE_URL to a
// full URL (e.g. https://api.example.com/api) at build time.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

export async function sendMessage(question, threadId) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, thread_id: threadId }),
  })

  let data = null
  try {
    data = await response.json()
  } catch {
    // response had no JSON body -- data stays null
  }

  if (!response.ok) {
    const message = data?.detail || `Request failed with status ${response.status}`
    throw new Error(message)
  }

  return data
}
