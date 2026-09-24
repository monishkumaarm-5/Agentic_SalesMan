import { memo } from 'react'
import { formatPrice } from '../../utils/format.js'
import { CheckIcon, CompareIcon, ExternalIcon } from '../layout/Icons.jsx'
import MatchMeter from './MatchMeter.jsx'
import Rating from './Rating.jsx'
import StockBadge from './StockBadge.jsx'

function ProductCard({ product, featured = false, selected = false, onToggleCompare, onDetails }) {
  const specs = (product.specs || []).slice(0, 3)
  const reasons = (product.fit_reasons || []).slice(0, 3)
  return (
    <article className={`product-card${featured ? ' featured' : ''}${selected ? ' selected' : ''}`}>
      {featured && <div className="ribbon">Best match</div>}

      <div className="pc-top">
        <div className="pc-title">
          <span className="pc-brand">{product.brand}</span>
          <h3>{product.name}</h3>
        </div>
        <MatchMeter value={product.match?.overall} />
      </div>

      {product.headline && <p className="pc-headline">{product.headline}</p>}

      <div className="pc-price">
        <span className="price">{formatPrice(product.price, product.currency) ?? 'Price on request'}</span>
        {product.mrp && <del className="mrp">{formatPrice(product.mrp, product.currency)}</del>}
        {product.discount_percent ? <span className="badge badge-accent">{product.discount_percent}% off</span> : null}
      </div>

      <div className="pc-meta">
        <Rating value={product.rating} />
        <StockBadge product={product} />
      </div>

      {specs.length > 0 && (
        <ul className="spec-chips" aria-label="Key specs">
          {specs.map((s) => (
            <li key={s.key}><span>{s.label}</span>{s.value}</li>
          ))}
        </ul>
      )}

      {reasons.length > 0 && (
        <ul className="fit-list" aria-label="Why it fits">
          {reasons.map((r) => (
            <li key={r}><CheckIcon width={14} height={14} /> {r}</li>
          ))}
        </ul>
      )}

      <div className="pc-actions">
        <button type="button" className="btn btn-secondary" onClick={() => onDetails?.(product)}>
          Details
        </button>
        {onToggleCompare && (
          <button
            type="button"
            className={`btn btn-ghost${selected ? ' active' : ''}`}
            aria-pressed={selected}
            onClick={() => onToggleCompare(product)}
          >
            <CompareIcon width={16} height={16} /> {selected ? 'Added' : 'Compare'}
          </button>
        )}
        {product.online_link && (
          <a className="btn btn-primary" href={product.online_link} target="_blank" rel="noopener noreferrer">
            Buy <ExternalIcon width={14} height={14} />
          </a>
        )}
      </div>
    </article>
  )
}

export default memo(ProductCard)
