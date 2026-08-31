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
    const { container } = render(<CandidateScores candidates={{ MOBILE: [] }} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('lists each candidate with its match score', () => {
    render(
      <CandidateScores
        candidates={{
          MOBILE: [
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

  it('labels each category only when there is more than one', () => {
    const { rerender } = render(
      <CandidateScores candidates={{ MOBILE: [{ name: 'Pixel 9', _scores: { overall: 0.9 } }] }} />
    )
    expect(screen.queryByText('Phone')).not.toBeInTheDocument()

    rerender(
      <CandidateScores
        candidates={{
          MOBILE: [{ name: 'Pixel 9', _scores: { overall: 0.9 } }],
          LAPTOP: [{ name: 'Lenovo LOQ', _scores: { overall: 0.8 } }],
        }}
      />
    )
    expect(screen.getByText('Phone')).toBeInTheDocument()
    expect(screen.getByText('Laptop')).toBeInTheDocument()
  })

  it('shows a Compare button only when a category has 2+ named candidates', () => {
    const { rerender } = render(
      <CandidateScores candidates={{ MOBILE: [{ name: 'Pixel 9', _scores: { overall: 0.9 } }] }} />
    )
    expect(screen.queryByRole('button', { name: /compare/i })).not.toBeInTheDocument()

    rerender(
      <CandidateScores
        candidates={{
          MOBILE: [
            { name: 'Pixel 9', _scores: { overall: 0.9 } },
            { name: 'Galaxy S', _scores: { overall: 0.6 } },
          ],
        }}
      />
    )
    expect(screen.getByRole('button', { name: /compare/i })).toBeInTheDocument()
  })

  it('fetches and renders a comparison when Compare is clicked', async () => {
    compareProducts.mockResolvedValue({
      category: 'phone',
      products: { 'Pixel 9': { price: 60000 }, 'Galaxy S': { price: 65000 } },
      differing_fields: ['price'],
      missing: [],
    })
    const user = userEvent.setup()
    render(
      <CandidateScores
        candidates={{
          MOBILE: [
            { name: 'Pixel 9', _scores: { overall: 0.9 } },
            { name: 'Galaxy S', _scores: { overall: 0.6 } },
          ],
        }}
      />
    )

    await user.click(screen.getByRole('button', { name: /compare/i }))

    expect(compareProducts).toHaveBeenCalledWith('phone', ['Pixel 9', 'Galaxy S'])
    expect(await screen.findByText('60000')).toBeInTheDocument()
  })
})
