import { formatPriceShort } from './format.js'

function niceBudget(category) {
  const { min_price: lo, max_price: hi } = category
  if (lo == null || hi == null) return null
  const mid = (lo + hi) / 2
  const step = mid >= 100000 ? 10000 : mid >= 10000 ? 5000 : 1000
  return Math.max(step, Math.round(mid / step) * step)
}

/** Starter prompts built from whatever the catalog actually carries. */
export function starterPrompts(categories) {
  const top = [...categories].sort((a, b) => b.product_count - a.product_count).slice(0, 4)
  return top.map((c, i) => {
    const noun = c.name.toLowerCase()
    const budget = niceBudget(c)
    if (i % 3 === 0 && budget) return `Best ${noun} under ${formatPriceShort(budget)}`
    if (i % 3 === 1) return `Help me choose a ${noun}`
    return `Which ${noun} has the best reviews?`
  })
}
