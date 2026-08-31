import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ComparisonTable from './ComparisonTable.jsx'

describe('ComparisonTable', () => {
  it('renders nothing when there is no comparison', () => {
    const { container } = render(<ComparisonTable comparison={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing for a single product', () => {
    const { container } = render(
      <ComparisonTable comparison={{ products: { A: { price: 1 } }, differing_fields: [] }} />
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders one row per field and one column per product', () => {
    render(
      <ComparisonTable
        comparison={{
          category: 'laptop',
          products: {
            'Lenovo LOQ': { price: 72999, ram: '16GB' },
            'HP Pavilion': { price: 55000, ram: '8GB' },
          },
          differing_fields: ['price', 'ram'],
          missing: [],
        }}
      />
    )
    expect(screen.getByText('Lenovo LOQ')).toBeInTheDocument()
    expect(screen.getByText('HP Pavilion')).toBeInTheDocument()
    expect(screen.getByText('72999')).toBeInTheDocument()
    expect(screen.getByText('55000')).toBeInTheDocument()
  })

  it('marks differing fields', () => {
    const { container } = render(
      <ComparisonTable
        comparison={{
          products: { A: { price: 1 }, B: { price: 2 } },
          differing_fields: ['price'],
          missing: [],
        }}
      />
    )
    expect(container.querySelector('tr.differs')).toBeInTheDocument()
  })
})
