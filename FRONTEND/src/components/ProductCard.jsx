const CATEGORY_LABELS = {
  MOBILE: 'Phone',
  LAPTOP: 'Laptop',
  HEADPHONE: 'Headphone',
}

function isSingleProduct(product) {
  return (
    product &&
    typeof product === 'object' &&
    ('recommended_product' in product || 'reason' in product || 'key_features' in product || 'buy_link' in product)
  )
}

function SingleProductCard({ product, label }) {
  const { recommended_product: name, reason, key_features: features, buy_link: buyLink } = product

  return (
    <div className="product-card">
      {label && <div className="product-card-label">{label}</div>}
      {name && <div className="product-card-name">{name}</div>}
      {reason && <p className="product-card-reason">{reason}</p>}
      {Array.isArray(features) && features.length > 0 && (
        <ul className="product-card-features">
          {features.map((feature) => (
            <li key={feature}>{feature}</li>
          ))}
        </ul>
      )}
      {buyLink && (
        <a className="product-card-buy" href={buyLink} target="_blank" rel="noreferrer">
          Buy Now
        </a>
      )}
    </div>
  )
}

function ProductCard({ product }) {
  if (!product) return null

  if (isSingleProduct(product)) {
    return <SingleProductCard product={product} />
  }

  // Multi-category answer: product is a dict keyed by category, e.g.
  // { MOBILE: {...}, HEADPHONE: {...} }
  const entries = Object.entries(product).filter(([, value]) => isSingleProduct(value))
  if (entries.length === 0) return null

  return (
    <div className="product-card-group">
      {entries.map(([category, value]) => (
        <SingleProductCard key={category} product={value} label={CATEGORY_LABELS[category] ?? category} />
      ))}
    </div>
  )
}

export default ProductCard
