import { memo, useMemo } from 'react'
import { formatSpecValue } from '../utils/format.js'

/* ── Data extraction helpers ──────────────────────────── */

function extractProducts(comparison) {
  if (!comparison) return []
  if (Array.isArray(comparison)) return comparison
  if (Array.isArray(comparison.products)) return comparison.products
  if (Array.isArray(comparison.comparison)) return comparison.comparison
  if (Array.isArray(comparison.items)) return comparison.items
  return []
}

function getSpecs(product) {
  return product?.specs || product?.features || {}
}

function getProductId(product, index) {
  return product.id || product.product_id || product.asin || product.name || index
}

/* ── Component ────────────────────────────────────────── */

function ComparisonTable({ comparison, products: productsProp, selectedProductId }) {
  const products = productsProp ?? extractProducts(comparison)

  // Collect every spec key across all products, preserving first-seen order.
  const specKeys = useMemo(() => {
    const keys = []
    products.forEach((product) => {
      Object.keys(getSpecs(product)).forEach((key) => {
        if (!keys.includes(key)) keys.push(key)
      })
    })
    return keys
  }, [products])

  if (products.length === 0 || specKeys.length === 0) return null

  return (
    <div className="comparison-table-wrap" role="region" aria-label="Product comparison">
      <table
        className="comparison-table"
        role="table"
        aria-label="Product feature comparison matrix"
      >
        <thead>
          <tr>
            <th scope="col">Product</th>
            {specKeys.map((key) => (
              <th scope="col" key={key}>
                {key.replace(/_/g, ' ')}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {products.map((product, index) => {
            const productId = getProductId(product, index)
            const isSelected =
              selectedProductId != null && String(productId) === String(selectedProductId)
            const specs = getSpecs(product)
            const productName = product.name || 'Unknown product'

            return (
              <tr key={productId} className={isSelected ? 'selected-row' : undefined}>
                <th scope="row">
                  <div className="product-cell">
                    <span className="product-link" title={productName}>
                      {productName}
                    </span>
                    {product.store && (
                      <span className="product-store">{product.store}</span>
                    )}
                  </div>
                </th>

                {specKeys.map((key) => (
                  <td key={key}>{formatSpecValue(specs[key])}</td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default memo(ComparisonTable)