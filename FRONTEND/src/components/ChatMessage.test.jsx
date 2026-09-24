import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChatMessage from './ChatMessage.jsx'

function pick(overrides = {}) {
  return {
    rank: 1,
    name: 'iPhone 14',
    specs: { brand: 'Apple' },
    scores: { overall: 0.9 },
    buy: {
      price: 60000,
      currency: 'INR',
      mrp: null,
      discount_percentage: null,
      units_available: null,
      in_stock: null,
      online_link: 'https://example.com',
      offline_availability: null,
    },
    why_this: 'Great value',
    key_features: ['A15 chip'],
    why_suits_you: 'Fits your budget',
    ...overrides,
  }
}

describe('ChatMessage', () => {
  it('renders a user message as plain text', () => {
    render(<ChatMessage role="user" content="recommend a phone" />)
    expect(screen.getByText('recommend a phone')).toBeInTheDocument()
  })

  it('renders an assistant message as Markdown', () => {
    render(<ChatMessage role="assistant" content="# Recommended Phone" />)
    expect(screen.getByRole('heading', { name: 'Recommended Phone' })).toBeInTheDocument()
  })

  it('applies the error style and does not render top-pick cards for error messages', () => {
    const { container } = render(
      <ChatMessage
        role="assistant"
        content="Something went wrong"
        isError
        product={{ top_picks: [pick()] }}
      />
    )
    expect(container.querySelector('.bubble.error')).toBeInTheDocument()
    expect(container.querySelector('.top-pick')).not.toBeInTheDocument()
  })

  it('renders the answer text AND the top-pick cards for a recommendation', async () => {
    render(
      <ChatMessage
        role="assistant"
        response_type="recommendation"
        content="Here you go"
        product={{ top_picks: [pick()] }}
      />
    )
    // The pitch itself must not be hidden behind the cards.
    expect(screen.getByText('Here you go')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'iPhone 14' })).toBeInTheDocument()
    expect(screen.getByText('Great value')).toBeInTheDocument()
    expect(screen.getByText('Fits your budget')).toBeInTheDocument()
    expect(screen.getByText('A15 chip')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /buy online/i })).toHaveAttribute(
      'href',
      'https://example.com'
    )
  })

  it('renders one set of cards per category for a multi-category product', async () => {
    render(
      <ChatMessage
        role="assistant"
        response_type="recommendation"
        content="Here you go"
        product={{
          MOBILE: { top_picks: [pick({ name: 'iPhone 14' })] },
          HEADPHONE: { top_picks: [pick({ name: 'SoundMax 200', why_this: 'Great sound' })] },
        }}
      />
    )
    expect(await screen.findByRole('heading', { name: 'iPhone 14' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'SoundMax 200' })).toBeInTheDocument()
  })

  it('does not render product cards for a non-recommendation reply', () => {
    const { container } = render(
      <ChatMessage role="assistant" response_type="clarification" content="What is your budget?" product={{ top_picks: [pick()] }} />
    )
    expect(screen.getByText('What is your budget?')).toBeInTheDocument()
    expect(container.querySelector('.top-picks')).not.toBeInTheDocument()
  })

  it('renders nothing extra when product is null', () => {
    const { container } = render(<ChatMessage role="assistant" content="hi" product={null} />)
    expect(container.querySelector('.top-pick')).not.toBeInTheDocument()
  })

  it('renders a confidence badge when confidence is present', () => {
    render(<ChatMessage role="assistant" response_type="recommendation" content="hi" confidence={0.82} />)
    expect(screen.getByText('Confidence: 82%')).toBeInTheDocument()
  })

  it('renders no confidence badge when confidence is null', () => {
    render(<ChatMessage role="assistant" content="hi" confidence={null} />)
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument()
  })

  it('does not render a confidence badge for user messages even if confidence is set', () => {
    render(<ChatMessage role="user" content="hi" confidence={0.82} />)
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument()
  })

  it('renders the candidate scores disclosure when candidates are present', async () => {
    render(
      <ChatMessage
        role="assistant"
        response_type="recommendation"
        content="hi"
        candidates={{ MOBILE: [{ name: 'Pixel 9', _scores: { overall: 0.9 } }] }}
      />
    )
    expect(await screen.findByText('Why these picks')).toBeInTheDocument()
  })
})
