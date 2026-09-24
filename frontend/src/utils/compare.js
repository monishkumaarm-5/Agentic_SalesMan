import { formatPrice, specNumber } from './format.js'

/**
 * Rows for a side-by-side comparison of product cards. Numeric rows mark
 * the best and worst value *relative to the products being compared*
 * (no fixed "8GB is good" thresholds): lower is better for price, higher
 * for everything else.
 */
export function buildComparison(products) {
  const rows = [
    {
      key: 'price',
      label: 'Price',
      values: products.map((p) => p.price),
      display: (v, p) => formatPrice(v, p.currency) ?? '—',
      better: 'lower',
    },
    { key: 'rating', label: 'Rating', values: products.map((p) => p.rating), display: (v) => (v ? `${v} ★` : '—'), better: 'higher' },
    {
      key: 'match',
      label: 'Match for you',
      values: products.map((p) => (p.match?.overall != null ? Math.round(p.match.overall * 100) : null)),
      display: (v) => (v != null ? `${v}%` : '—'),
      better: 'higher',
    },
    { key: 'brand', label: 'Brand', values: products.map((p) => p.brand), display: (v) => v ?? '—' },
  ]

  const specKeys = []
  const labels = {}
  for (const p of products) {
    for (const s of p.specs || []) {
      if (!specKeys.includes(s.key)) {
        specKeys.push(s.key)
        labels[s.key] = s.label
      }
    }
  }
  for (const key of specKeys) {
    const raw = products.map((p) => (p.specs || []).find((s) => s.key === key)?.value ?? null)
    const numbers = raw.map(specNumber)
    const numeric = numbers.filter((n) => n != null).length >= 2 && raw.every((v, i) => v == null || numbers[i] != null)
    rows.push({
      key,
      label: labels[key],
      values: numeric ? numbers : raw,
      display: (_, __, i) => raw[i] ?? '—',
      better: numeric ? 'higher' : undefined,
    })
  }

  return rows
    .filter((row) => row.values.some((v) => v != null))
    .map((row) => {
      const known = row.values.filter((v) => typeof v === 'number')
      let best = null
      let worst = null
      if (row.better && known.length >= 2 && Math.min(...known) !== Math.max(...known)) {
        best = row.better === 'lower' ? Math.min(...known) : Math.max(...known)
        worst = row.better === 'lower' ? Math.max(...known) : Math.min(...known)
      }
      const differs = new Set(row.values.map((v) => String(v ?? ''))).size > 1
      return {
        key: row.key,
        label: row.label,
        differs,
        cells: row.values.map((v, i) => ({
          text: row.display(v, products[i], i),
          tone: v != null && v === best ? 'best' : v != null && v === worst ? 'worst' : null,
        })),
      }
    })
}
