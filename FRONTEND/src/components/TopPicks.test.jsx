import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TopPicksPanel from './TopPicks.jsx'

function pick(overrides = {}) {
  return {
    rank: 1,
    name: 'HP Pavilion 15',
    specs: { brand: 'HP', ram: '16GB', storage: '512GB', processor: 'Ryzen 7' },
    scores: { overall: 0.9 },
    buy: {
      price: 69990,
      currency: 'INR',
      mrp: null,
      discount_percentage: null,
      units_available: null,
      in_stock: null,
      online_link: null,
      offline_availability: null,
    },
    why_this: 'Great performance for the price.',
    key_features: ['Ryzen 7', '16GB RAM'],
    why_suits_you: 'Matches your budget and use case.',
    ...overrides,
  }
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

describe('TopPicksPanel', () => {
  it('renders nothing when product is null', () => {
    const { container } = render(<TopPicksPanel product={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when there is no top_picks shape anywhere in product', () => {
    const { container } = render(<TopPicksPanel product={{ foo: 'bar' }} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the why-this, key-features, why-suits-you and buy-now cards for a pick', () => {
    render(<TopPicksPanel product={{ top_picks: [pick()] }} />)
    expect(screen.getByText('#1')).toBeInTheDocument()
    expect(screen.getByText('HP Pavilion 15')).toBeInTheDocument()
    expect(screen.getByText('Why this HP Pavilion 15?')).toBeInTheDocument()
    expect(screen.getByText('Great performance for the price.')).toBeInTheDocument()
    expect(screen.getByText('Why this suits you')).toBeInTheDocument()
    expect(screen.getByText('Matches your budget and use case.')).toBeInTheDocument()
    expect(screen.getByText('Ryzen 7')).toBeInTheDocument()
    expect(screen.getByText('16GB RAM')).toBeInTheDocument()
    expect(screen.getByText('₹69,990')).toBeInTheDocument()
  })

  it('shows a discount badge and struck-through MRP when the catalog has one', () => {
    render(
      <TopPicksPanel
        product={{ top_picks: [pick({ buy: { ...pick().buy, price: 69990, mrp: 99990, discount_percentage: 30 } })] }}
      />
    )
    expect(screen.getByText('₹99,990')).toBeInTheDocument()
    expect(screen.getByText('30% off')).toBeInTheDocument()
  })

  it('falls back to "Not available"/"Not tracked" when the catalog does not track a buy field', () => {
    render(<TopPicksPanel product={{ top_picks: [pick()] }} />)
    // "Not tracked" appears twice: units available, and stock status.
    expect(screen.getAllByText('Not tracked')).toHaveLength(2)
    expect(screen.getByText('Not available')).toBeInTheDocument() // offline availability
    expect(screen.getByText('Online link not available')).toBeInTheDocument()
  })

  it('shows an in-stock / out-of-stock badge based on buy.in_stock', () => {
    const { rerender } = render(
      <TopPicksPanel product={{ top_picks: [pick({ buy: { ...pick().buy, in_stock: true, units_available: 4 } })] }} />
    )
    expect(screen.getByText('In stock')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()

    rerender(
      <TopPicksPanel product={{ top_picks: [pick({ buy: { ...pick().buy, in_stock: false, units_available: 0 } })] }} />
    )
    expect(screen.getByText('Out of stock')).toBeInTheDocument()
  })

  it('links the online store when the catalog has a link', () => {
    render(
      <TopPicksPanel
        product={{ top_picks: [pick({ buy: { ...pick().buy, online_link: 'https://shop.example.com/x' } })] }}
      />
    )
    expect(screen.getByRole('link', { name: /buy online/i })).toHaveAttribute(
      'href',
      'https://shop.example.com/x'
    )
  })

  it('does not render a comparison table for a single pick', () => {
    const { container } = render(<TopPicksPanel product={{ top_picks: [pick()] }} />)
    expect(container.querySelector('.top-picks-comparison')).not.toBeInTheDocument()
  })

  it('renders a comparison table for all picks with the best value green and worst red', () => {
    const cheaperMoreRam = pick({
      rank: 1,
      name: 'Cheap & Powerful',
      specs: { ram: '16GB', storage: '512GB' },
      buy: { ...pick().buy, price: 50000 },
    })
    const pricierLessRam = pick({
      rank: 2,
      name: 'Pricier & Weaker',
      specs: { ram: '8GB', storage: '256GB' },
      buy: { ...pick().buy, price: 80000 },
    })
    const { container } = render(
      <TopPicksPanel product={{ top_picks: [cheaperMoreRam, pricierLessRam] }} />
    )

    const table = container.querySelector('.top-picks-comparison')
    expect(table).toBeInTheDocument()
    expect(within(table).getByText('Cheap & Powerful')).toBeInTheDocument()
    expect(within(table).getByText('Pricier & Weaker')).toBeInTheDocument()

    const bestCells = container.querySelectorAll('.best-cell')
    const worstCells = container.querySelectorAll('.worst-cell')
    expect(bestCells.length).toBeGreaterThan(0)
    expect(worstCells.length).toBeGreaterThan(0)

    // Price: 50000 is lower (better) so it should be a best-cell, not worst.
    const priceRow = screen.getByText('Price').closest('tr')
    expect(priceRow.querySelector('.best-cell')).toHaveTextContent('₹50,000')
    expect(priceRow.querySelector('.worst-cell')).toHaveTextContent('₹80,000')
  })

  it('scrolls to a pick\'s own cards when its comparison header is clicked', async () => {
    const user = userEvent.setup()
    const picks = [pick({ rank: 1, name: 'A' }), pick({ rank: 2, name: 'B' })]
    render(<TopPicksPanel product={{ top_picks: picks }} />)

    await user.click(screen.getByRole('button', { name: 'A' }))
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
  })

  it('renders one labeled section per category for a multi-category product', () => {
    render(
      <TopPicksPanel
        product={{
          Mobile: { top_picks: [pick({ name: 'Pixel 9' })] },
          Laptop: { top_picks: [pick({ name: 'HP Pavilion 15' })] },
        }}
      />
    )
    expect(screen.getByText('Mobile')).toBeInTheDocument()
    expect(screen.getByText('Laptop')).toBeInTheDocument()
    expect(screen.getByText('Pixel 9')).toBeInTheDocument()
    expect(screen.getByText('HP Pavilion 15')).toBeInTheDocument()
  })

  it('renders a brand-new catalog category (e.g. Refrigerator) the same way', () => {
    // No CATEGORY_LABELS entry needed for a category the code has never
    // heard of -- it renders using its own catalog name as the label.
    render(
      <TopPicksPanel
        product={{
          Refrigerator: { top_picks: [pick({ name: 'Trein Cool 200' })] },
          'Air Conditioner': { top_picks: [pick({ name: 'Trein Chill 1.5T' })] },
        }}
      />
    )
    expect(screen.getByText('Refrigerator')).toBeInTheDocument()
    expect(screen.getByText('Air Conditioner')).toBeInTheDocument()
  })
})
