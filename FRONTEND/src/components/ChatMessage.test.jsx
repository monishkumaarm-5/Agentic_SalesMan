import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChatMessage from './ChatMessage.jsx'

describe('ChatMessage', () => {
  it('renders a user message as plain text', () => {
    render(<ChatMessage role="user" content="recommend a phone" />)
    expect(screen.getByText('recommend a phone')).toBeInTheDocument()
  })

  it('renders an assistant message as Markdown', () => {
    render(<ChatMessage role="assistant" content="# Recommended Phone" />)
    expect(screen.getByRole('heading', { name: 'Recommended Phone' })).toBeInTheDocument()
  })

  it('applies the error style and does not render a product card for error messages', () => {
    const { container } = render(
      <ChatMessage role="assistant" content="Something went wrong" isError product={{ recommended_product: 'X' }} />
    )
    expect(container.querySelector('.bubble.error')).toBeInTheDocument()
    expect(container.querySelector('.product-card')).not.toBeInTheDocument()
  })

  it('renders a product card for a single-category product', () => {
    render(
      <ChatMessage
        role="assistant"
        content="Here you go"
        product={{ recommended_product: 'iPhone 14', reason: 'Great value', key_features: ['A15 chip'], buy_link: 'https://example.com' }}
      />
    )
    expect(screen.getByText('iPhone 14')).toBeInTheDocument()
    expect(screen.getByText('Great value')).toBeInTheDocument()
    expect(screen.getByText('A15 chip')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /buy now/i })).toHaveAttribute('href', 'https://example.com')
  })

  it('renders one card per category for a multi-category product', () => {
    render(
      <ChatMessage
        role="assistant"
        content="Here you go"
        product={{
          MOBILE: { recommended_product: 'iPhone 14' },
          HEADPHONE: { recommended_product: 'SoundMax 200' },
        }}
      />
    )
    expect(screen.getByText('iPhone 14')).toBeInTheDocument()
    expect(screen.getByText('SoundMax 200')).toBeInTheDocument()
  })

  it('renders nothing extra when product is null', () => {
    const { container } = render(<ChatMessage role="assistant" content="hi" product={null} />)
    expect(container.querySelector('.product-card')).not.toBeInTheDocument()
  })

  it('renders a confidence badge when confidence is present', () => {
    render(<ChatMessage role="assistant" content="hi" confidence={0.82} />)
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

  it('renders the candidate scores disclosure when candidates are present', () => {
    render(
      <ChatMessage
        role="assistant"
        content="hi"
        candidates={{ MOBILE: [{ name: 'Pixel 9', _scores: { overall: 0.9 } }] }}
      />
    )
    expect(screen.getByText('Why these picks')).toBeInTheDocument()
  })
})
