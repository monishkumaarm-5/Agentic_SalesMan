/**
 * Shared formatting utilities.
 * Single source of truth — no duplicates across components.
 */

/**
 * Format a numeric value as Indian Rupee string.
 * @param {number|string|null} value
 * @returns {string|null}
 */
export function formatINR(value) {
  if (value == null) return null
  const number = Number(value)
  if (Number.isNaN(number)) return null
  return `₹${Math.round(number).toLocaleString('en-IN')}`
}

/**
 * Parse a spec value (e.g. "8 GB", "1 TB", "5,000 mAh") into a number.
 * Understands TB → multiply by 1000.
 * @param {*} value
 * @returns {number|null}
 */
export function parseSpecNumber(value) {
  if (value == null) return null
  if (typeof value === 'number') return Number.isNaN(value) ? null : value
  const text = String(value).trim()
  if (!text) return null
  const match = text.match(/[\d,]+(?:\.\d+)?/)
  if (!match) return null
  let number = parseFloat(match[0].replace(/,/g, ''))
  if (text.toLowerCase().includes('tb')) number *= 1000
  return Number.isNaN(number) ? null : number
}

/**
 * Split a paragraph into individual sentences for display as a list.
 * @param {string} text
 * @returns {string[]}
 */
export function splitSentences(text) {
  if (!text) return []
  return text
    .split(/(?<=[.!?])\s+(?=[A-Z0-9])/)
    .map((s) => s.trim())
    .filter(Boolean)
}

/**
 * Format a spec value for table display.
 * Handles null, boolean, arrays, objects, and primitives.
 * @param {*} value
 * @returns {string}
 */
export function formatSpecValue(value) {
  if (value === undefined || value === null || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') {
    try {
      return Object.entries(value)
        .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
        .join(', ')
    } catch {
      return '—'
    }
  }
  return String(value)
}

/**
 * Build a Google Maps search URL.
 * @param {string} query
 * @returns {string}
 */
export function mapsSearchUrl(query) {
  return `https://www.google.com/maps/search/${encodeURIComponent(query)}`
}