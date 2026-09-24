import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../api.js', () => ({
  compareProducts: vi.fn(),
}))

import { compareProducts } from '../api.js'
import CandidateScores from './CandidateScores.jsx'

describe('CandidateScores', () => {
  it('renders nothing when there are no candidates', () => {
    const { container } = render(<CandidateScores candidates={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when every category is empty', () => {
    const { container } = render(<CandidateScores candidates={{ Mobile: [] }} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('lists each candidate with its match score', () => {
    render(
      <CandidateScores
        candidates={{
          Mobile: [
            { name: 'Pixel 9', price: 60000, _scores: { overall: 0.9 } },
            { name: 'Galaxy S', price: 65000, _scores: { overall: 0.6 } },
          ],
        }}
      />
    )
    expect(screen.getByText('Pixel 9')).toBeInTheDocument()
    expect(screen.getByText('Galaxy S')).toBeInTheDocument()
    expect(screen.getByText('90%')).toBeInTheDocument()
    expect(screen.getByText('60%')).toBeInTheDocument()
  })

  it('labels each category (by its real catalog name) only when there is more than one', () => {
    // Categories are data-driven now (any string the `products` table has,
    // e.g. "Mobile", "Refrigerator", "Air Conditioner") and already arrive
    // in human-readable form straight from the catalog, so the category
    // key itself is the label -- no MOBILE/LAPTOP/HEADPHONE translation
    // table needed.
    const { rerender } = render(
      <CandidateScores candidates={{ Mobile: [{ name: 'Pixel 9', _scores: { overall: 0.9 } }] }} />
    )
    expect(screen.queryByText('Mobile')).not.toBeInTheDocument()

    rerender(
      <CandidateScores
        candidates={{
          Mobile: [{ name: 'Pixel 9', _scores: { overall: 0.9 } }],
          Laptop: [{ name: 'Lenovo LOQ', _scores: { overall: 0.8 } }],
        }}
      />
    )
    expect(screen.getByText('Mobile')).toBeInTheDocument()
    expect(screen.getByText('Laptop')).toBeInTheDocument()
  })

  it('labels a brand-new catalog category (e.g. Refrigerator) the same way, with zero code changes', () => {
    render(
      <CandidateScores
        candidates={{
          Refrigerator: [{ name: 'Trein Cool 200', _scores: { overall: 0.9 } }],
          'Air Conditioner': [{ name: 'Trein Chill 1.5T', _scores: { overall: 0.7 } }],
        }}
      />
    )
    expect(screen.getByText('Refrigerator')).toBeInTheDocument()
    expect(screen.getByText('Air Conditioner')).toBeInTheDocument()
  })

  it('shows a Compare button only when a category has 2+ named candidates', () => {
    const { rerender } = render(
      <CandidateScores candidates={{ Mobile: [{ name: 'Pixel 9', _scores: { overall: 0.9 } }] }} />
    )
    expect(screen.queryByRole('button', { name: /compare/i })).not.toBeInTheDocument()

    rerender(
      <CandidateScores
        candidates={{
          Mobile: [
            { name: 'Pixel 9', _scores: { overall: 0.9 } },
            { name: 'Galaxy S', _scores: { overall: 0.6 } },
          ],
        }}
      />
    )
    expect(screen.getByRole('button', { name: /compare/i })).toBeInTheDocument()
  })

  it('fetches and renders a comparison when Compare is clicked, using the category as-is', async () => {
    // /api/compare takes the category exactly as the catalog has it (see
    // ENDPOINTS/endpoints.py's CompareRequest + TOOLS/product_tools.py's
    // case-insensitive lookup) -- no more translating it through a fixed
    // MOBILE -> 'phone' style map first.
    compareProducts.mockResolvedValue({
      category: 'Mobile',
      products: { 'Pixel 9': { price: 60000 }, 'Galaxy S': { price: 65000 } },
      differing_fields: ['price'],
      missing: [],
    })
    const user = userEvent.setup()
    render(
      <CandidateScores
        candidates={{
          Mobile: [
            { name: 'Pixel 9', _scores: { overall: 0.9 } },
            { name: 'Galaxy S', _scores: { overall: 0.6 } },
          ],
        }}
      />
    )

    await user.click(screen.getByRole('button', { name: /compare/i }))

    expect(compareProducts).toHaveBeenCalledWith('Mobile', ['Pixel 9', 'Galaxy S'])
    expect(await screen.findByText('₹60,000')).toBeInTheDocument()
  })
})
