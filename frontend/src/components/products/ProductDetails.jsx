import { formatPrice, percent } from '../../utils/format.js'
import { CheckIcon, ExternalIcon, MapPinIcon } from '../layout/Icons.jsx'
import Modal from './Modal.jsx'
import Rating from './Rating.jsx'
import StockBadge from './StockBadge.jsx'

const COMPONENT_LABELS = {
  relevance: 'Relevance to your request',
  budget: 'Fits your budget',
  features: 'Has what you asked for',
  rating: 'Customer rating',
  brand: 'Brand preference',
  availability: 'Availability',
}

export default function ProductDetails({ product, onClose }) {
  const components = Object.entries(product.match?.components || {})
  return (
    <Modal title={product.name} onClose={onClose}>
      <div className="details">
        <div className="details-head">
          <div>
            <p className="pc-brand">{product.brand} · {product.category}</p>
            <div className="pc-price">
              <span className="price large">{formatPrice(product.price, product.currency) ?? 'Price on request'}</span>
              {product.mrp && <del className="mrp">{formatPrice(product.mrp, product.currency)}</del>}
              {product.discount_percent ? <span className="badge badge-accent">{product.discount_percent}% off</span> : null}
            </div>
            <div className="pc-meta"><Rating value={product.rating} /><StockBadge product={product} /></div>
          </div>
          {product.online_link && (
            <a className="btn btn-primary" href={product.online_link} target="_blank" rel="noopener noreferrer">
              Buy online <ExternalIcon width={14} height={14} />
            </a>
          )}
        </div>

        {(product.why || product.description) && (
          <section>
            <h3>{product.why ? 'Why it suits you' : 'About'}</h3>
            <p>{product.why || product.description}</p>
            {product.why && product.description && <p className="muted">{product.description}</p>}
          </section>
        )}

        {product.key_features?.length > 0 && (
          <section>
            <h3>Highlights</h3>
            <ul className="fit-list">
              {product.key_features.map((f) => <li key={f}><CheckIcon width={14} height={14} /> {f}</li>)}
            </ul>
          </section>
        )}

        {product.specs?.length > 0 && (
          <section>
            <h3>Specifications</h3>
            <dl className="spec-table">
              {product.specs.map((s) => (
                <div key={s.key}><dt>{s.label}</dt><dd>{s.value}</dd></div>
              ))}
            </dl>
          </section>
        )}

        {components.length > 0 && (
          <section>
            <h3>How well it matches <span className="muted">· {percent(product.match.overall)}% overall</span></h3>
            <ul className="score-bars">
              {components.map(([key, value]) => (
                <li key={key}>
                  <span>{COMPONENT_LABELS[key] || key}</span>
                  <div className="bar"><div style={{ width: `${percent(value)}%` }} /></div>
                  <b>{percent(value)}%</b>
                </li>
              ))}
            </ul>
          </section>
        )}

        {(product.stores?.length > 0 || product.offline_availability) && (
          <section>
            <h3>See it in store</h3>
            {product.stores?.length > 0 ? (
              <ul className="store-list">
                {product.stores.map((s) => (
                  <li key={s.name}>
                    <MapPinIcon width={16} height={16} />
                    <div>
                      <b>{s.name}</b>{s.nearby && <span className="badge badge-success">Near you</span>}
                      <p className="muted">{s.address}{s.hours ? ` · ${s.hours}` : ''}</p>
                      {s.maps_url && <a href={s.maps_url} target="_blank" rel="noopener noreferrer">Directions</a>}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">{product.offline_availability}</p>
            )}
          </section>
        )}
      </div>
    </Modal>
  )
}
