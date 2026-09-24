const INR = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })

export function formatPrice(value, currency = 'INR') {
  if (value == null || Number.isNaN(Number(value))) return null
  if (currency === 'INR') return INR.format(Number(value))
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 0 }).format(Number(value))
  } catch {
    return `${currency} ${Math.round(Number(value)).toLocaleString()}`
  }
}

/** Compact price for chips: 30000 -> "₹30k", 120000 -> "₹1.2L". */
export function formatPriceShort(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  if (n >= 100000) return `₹${+(n / 100000).toFixed(1)}L`
  if (n >= 1000) return `₹${+(n / 1000).toFixed(n % 1000 ? 1 : 0)}k`
  return `₹${n}`
}

/** First number in a spec value ("16GB" -> 16, "1TB" -> 1000). */
export function specNumber(value) {
  if (value == null) return null
  if (typeof value === 'number') return value
  const match = String(value).match(/-?\d[\d,]*(?:\.\d+)?/)
  if (!match) return null
  let n = parseFloat(match[0].replace(/,/g, ''))
  if (/\d\s*tb\b/i.test(String(value))) n *= 1000
  return Number.isNaN(n) ? null : n
}

export function percent(value) {
  if (value == null) return null
  return Math.round(Math.max(0, Math.min(1, Number(value))) * 100)
}

export const createId = (prefix = 'id') =>
  typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`

/** Human labels for the shopping profile the assistant has built up. */
export function profileChips(profile) {
  if (!profile) return []
  const chips = []
  for (const c of profile.categories || []) chips.push({ key: `c-${c}`, label: c, kind: 'category' })
  const { budget_min: lo, budget_max: hi } = profile
  if (lo && hi) chips.push({ key: 'budget', label: `${formatPriceShort(lo)} – ${formatPriceShort(hi)}`, kind: 'budget' })
  else if (hi) chips.push({ key: 'budget', label: `Under ${formatPriceShort(hi)}`, kind: 'budget' })
  else if (lo) chips.push({ key: 'budget', label: `From ${formatPriceShort(lo)}`, kind: 'budget' })
  for (const u of profile.use_cases || []) chips.push({ key: `u-${u}`, label: u, kind: 'use' })
  for (const m of profile.must_haves || []) chips.push({ key: `m-${m}`, label: m, kind: 'feature' })
  for (const b of profile.preferred_brands || []) chips.push({ key: `b-${b}`, label: b, kind: 'brand' })
  for (const b of profile.avoid_brands || []) chips.push({ key: `x-${b}`, label: `No ${b}`, kind: 'avoid' })
  if (profile.city) chips.push({ key: 'city', label: profile.city, kind: 'city' })
  return chips
}
