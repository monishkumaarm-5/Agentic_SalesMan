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
    expect(screen.getByText('₹72,999')).toBeInTheDocument()
    expect(screen.getByText('₹55,000')).toBeInTheDocument()
  })

  it('hides the internal id field and gives friendly labels', () => {
    render(
      <ComparisonTable
        comparison={{
          products: {
            A: { price: 1000, brand: 'Acme' },
            B: { price: 2000, brand: 'Zeta' },
          },
          differing_fields: ['price', 'brand'],
          missing: [],
        }}
      />
    )
    expect(screen.getByText('Price')).toBeInTheDocument()
    expect(screen.getByText('Brand')).toBeInTheDocument()
    expect(screen.queryByText('id')).not.toBeInTheDocument()
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

  it('hides internal bookkeeping columns and formats prices', () => {
    render(
      <ComparisonTable
        comparison={{
          products: {
            A: { id: 1, name: 'A', price: 1000, mrp: null, ingestion_status: 'complete' },
            B: { id: 2, name: 'B', price: 2000, mrp: 2500, ingestion_status: 'complete' },
          },
          differing_fields: ['price', 'mrp'],
          missing: ['C'],
        }}
      />
    )
    expect(screen.queryByText('complete')).not.toBeInTheDocument()
    expect(screen.getByText('₹2,500')).toBeInTheDocument()
    expect(screen.getByText(/Not found in the catalog: C/)).toBeInTheDocument()
  })
})
