import { describe, expect, it } from 'vitest'
import { card } from '../test/fixtures.js'
import { buildComparison } from './compare.js'
import { formatPrice, formatPriceShort, profileChips, specNumber } from './format.js'
import { starterPrompts } from './prompts.js'

describe('format', () => {
  it('formats prices', () => {
    expect(formatPrice(123456)).toBe('₹1,23,456')
    expect(formatPriceShort(30000)).toBe('₹30k')
    expect(formatPriceShort(120000)).toBe('₹1.2L')
    expect(specNumber('1TB')).toBe(1000)
  })

  it('describes the shopping profile', () => {
    const labels = profileChips({ categories: ['Mobile'], budget_max: 30000, must_haves: ['5G'], avoid_brands: ['Apple'], city: 'Chennai' })
      .map((c) => c.label)
    expect(labels).toEqual(['Mobile', 'Under ₹30k', '5G', 'No Apple', 'Chennai'])
  })
})

describe('buildComparison', () => {
  it('marks best and worst relative to the compared products', () => {
    const rows = buildComparison([
      card({ price: 20000, specs: [{ key: 'ram', label: 'RAM', value: '8GB' }] }),
      card({ name: 'B', price: 30000, specs: [{ key: 'ram', label: 'RAM', value: '12GB' }] }),
    ])
    const price = rows.find((r) => r.key === 'price')
    expect(price.cells.map((c) => c.tone)).toEqual(['best', 'worst'])
    const ram = rows.find((r) => r.key === 'ram')
    expect(ram.cells.map((c) => [c.text, c.tone])).toEqual([['8GB', 'worst'], ['12GB', 'best']])
    expect(rows.find((r) => r.key === 'brand').differs).toBe(false)
  })
})

describe('starterPrompts', () => {
  it('builds prompts from the live catalog', () => {
    const prompts = starterPrompts([
      { name: 'Mobile', product_count: 8, min_price: 10000, max_price: 50000 },
      { name: 'Laptop', product_count: 5, min_price: 30000, max_price: 90000 },
    ])
    expect(prompts).toEqual(['Best mobile under ₹30k', 'Help me choose a laptop'])
  })
})
