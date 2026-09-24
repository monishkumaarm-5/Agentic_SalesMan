import { useState, useEffect, useCallback, memo, useMemo } from 'react'
import { formatINR, parseSpecNumber, splitSentences, mapsSearchUrl } from '../utils/format.js'
import { isTopPicksShape } from '../utils/scores.js'
import { SPEC_LABELS, evaluateSpec } from '../utils/specRules.js'

/* ─────────────────────────────────────────────────────────
   Product selector (tab-like switcher)
   ───────────────────────────────────────────────────────── */

const ProductSelector = memo(function ProductSelector({ picks, selectedRank, onSelect }) {
  // Generate a unique id prefix for ARIA tab/tabpanel pairing
  const panelId = 'picks-panel'

  return (
    <div className="product-selector" role="tablist" aria-label="Top picks options">
      {picks.map((pick, index) => {
        const isSelected = pick.rank === selectedRank
        return (
          <button
            type="button"
            key={pick.rank ?? pick.name}
            className={`product-option${isSelected ? ' active' : ''}`}
            onClick={() => onSelect(pick.rank)}
            role="tab"
            id={`tab-${pick.rank}`}
            aria-selected={isSelected}
            aria-controls={panelId}
            tabIndex={isSelected ? 0 : -1}
          >
            <div className="option-number">{String(index + 1).padStart(2, '0')}</div>
            <div className="option-name">{pick.name || 'Unknown product'}</div>
            <div className="option-price">{formatINR(pick.buy?.price) ?? 'Price unavailable'}</div>
            {pick.rank === 1 && <div className="option-status">Recommended</div>}
          </button>
        )
      })}
    </div>
  )
})

/* ─────────────────────────────────────────────────────────
   Hero section for the selected pick
   ───────────────────────────────────────────────────────── */

const RecommendedHero = memo(function RecommendedHero({ pick }) {
  const { price, mrp, discount_percentage: discount } = pick.buy || {}
  return (
    <section className="recommended" aria-label="Selected product details">
      <div className="recommended-top">
        <div>
          <span className="recommended-label">Selected product</span>
          <h2 className="product-title">{pick.name || 'Unknown product'}</h2>
        </div>
        <div className="product-price">
          <div className="price">{formatINR(price) ?? 'Price unavailable'}</div>
          {mrp != null && price != null && mrp > price && (
            <div className="mrp">
              <del>{formatINR(mrp)}</del>
            </div>
          )}
          {discount != null && <div className="discount">{discount}% OFF</div>}
        </div>
      </div>
    </section>
  )
})

/* ─────────────────────────────────────────────────────────
   "Why this" + specs grid
   ───────────────────────────────────────────────────────── */

const WhyAndFeatures = memo(function WhyAndFeatures({ pick }) {
  const specEntries = useMemo(
    () => Object.entries(pick.specs || {}).filter(([, v]) => v != null && v !== ''),
    [pick.specs],
  )

  return (
    <div className="info-grid">
      <section className="card">
        <h3 className="card-title">
          Why this {pick.name ? pick.name.split(' ')[0] : 'product'}?
        </h3>
        <p className="card-description">
          {pick.why_this || 'No verified reasoning available yet.'}
        </p>
      </section>

      <section className="card">
        <h3 className="card-title">Specifications</h3>
        {specEntries.length > 0 ? (
          <div className="spec-detail-grid" role="list">
            {specEntries.map(([key, value]) => {
              const { quality, tip } = evaluateSpec(key, value)
              return (
                <div
                  className={`spec-detail-row spec-${quality}`}
                  key={key}
                  title={tip || undefined}
                  role="listitem"
                >
                  <span className="spec-detail-label">{SPEC_LABELS[key] || key}</span>
                  <span className="spec-detail-value">
                    {quality === 'good' && <span className="spec-indicator good" aria-label="Good">✓</span>}
                    {quality === 'bad' && <span className="spec-indicator bad" aria-label="Weak">✗</span>}
                    {String(value)}
                  </span>
                  {tip && <span className="spec-detail-tip">{tip}</span>}
                </div>
              )
            })}
          </div>
        ) : (
          <p className="card-description">No verified specs listed yet.</p>
        )}
      </section>
    </div>
  )
})

/* ─────────────────────────────────────────────────────────
   "Why this suits you" section
   ───────────────────────────────────────────────────────── */

const SuitsYou = memo(function SuitsYou({ pick }) {
  const items = useMemo(() => splitSentences(pick.why_suits_you), [pick.why_suits_you])

  if (items.length === 0) return null

  return (
    <section className="card suits">
      <h3 className="card-title">Why this suits you</h3>
      {items.length === 1 ? (
        <p className="card-description">{items[0]}</p>
      ) : (
        <div className="suit-grid">
          {items.map((item, index) => (
            <div className="suit" key={index}>
              <span className="suit-number">{String(index + 1).padStart(2, '0')}</span>
              {item}
            </div>
          ))}
        </div>
      )}
    </section>
  )
})

/* ─────────────────────────────────────────────────────────
   Buy card with online/offline links
   ───────────────────────────────────────────────────────── */

const BuyCard = memo(function BuyCard({ pick }) {
  const buy = pick.buy || {}
  const {
    price,
    mrp,
    units_available: units,
    in_stock: inStock,
    online_link: onlineLink,
    offline_availability: offline,
    offline_stores: offlineStores,
  } = buy
  const save = mrp != null && price != null && mrp > price ? mrp - price : null
  const stores = Array.isArray(offlineStores) ? offlineStores : []

  const availabilityParts = useMemo(() => {
    const parts = []
    if (units != null) parts.push(`${units} unit${units === 1 ? '' : 's'} available`)
    else if (inStock != null) parts.push(inStock ? 'In stock' : 'Out of stock')
    if (offline) parts.push(offline)
    return parts
  }, [units, inStock, offline])

  // The backend already matches the catalog's free-text offline-availability
  // column against our real store locations (see WORKFLOW/recommendations.py
  // _match_offline_stores) -- so each entry here is a SPECIFIC branch that
  // actually carries this product, with its own Maps link. Fall back to a
  // generic "<brand> showroom near me" search only when the catalog names a
  // retailer we don't have a matched location for (e.g. "Croma"), so there's
  // still something useful to click.
  const showroomQuery =
    stores.length === 0 &&
    offline &&
    offline.toLowerCase() !== 'not available in offline stores' &&
    pick.specs?.brand
      ? `${pick.specs.brand} showroom near me`
      : null

  return (
    <section className="buy" aria-label={`Buy ${pick.name || 'product'}`}>
      <div>
        <h3 className="buy-title">Buy this {pick.name || 'product'}</h3>
        <p className="buy-description">
          {pick.rank === 1
            ? 'Top recommended match based on your requirements.'
            : 'A strong alternative worth considering.'}
        </p>
        <div className="buy-details">
          <span className="buy-price">{formatINR(price) ?? 'Price unavailable'}</span>
          {mrp != null && price != null && mrp > price && (
            <span className="mrp"><del>{formatINR(mrp)}</del></span>
          )}
          {save != null && <span className="save">Save {formatINR(save)}</span>}
        </div>
        {availabilityParts.length > 0 && (
          <div className="availability">{availabilityParts.join(' · ')}</div>
        )}
      </div>
      <div className="buy-actions">
        {onlineLink ? (
          <a className="buy-button" href={onlineLink} target="_blank" rel="noopener noreferrer">
            Buy online
          </a>
        ) : (
          <span className="buy-button disabled" aria-disabled="true">
            Online link not available
          </span>
        )}
        {showroomQuery && (
          <a
            className="showroom-button"
            href={mapsSearchUrl(showroomQuery)}
            target="_blank"
            rel="noopener noreferrer"
          >
            See nearby offline showroom
          </a>
        )}
      </div>
      {stores.length > 0 && (
        <div className="offline-stores">
          <h4 className="offline-stores-title">Available at these stores</h4>
          <ul className="offline-stores-list">
            {stores.map((store) => (
              <li key={store.name} className="offline-store">
                <a
                  className="offline-store-link"
                  href={store.maps_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <span className="offline-store-name">{store.name}</span>
                  {store.city && <span className="offline-store-city"> · {store.city}</span>}
                </a>
                {store.address && <div className="offline-store-address">{store.address}</div>}
                {store.hours && <div className="offline-store-hours">{store.hours}</div>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
})

/* ─────────────────────────────────────────────────────────
   Side-by-side comparison table
   ───────────────────────────────────────────────────────── */

const COMPARISON_ROWS = [
  { key: 'price', label: 'Price', direction: 'lower', get: (p) => p.buy?.price, format: formatINR },
  { key: 'discount', label: 'Discount', direction: 'higher', get: (p) => p.buy?.discount_percentage ?? null, format: (v) => `${v}%` },
  { key: 'ram', label: 'RAM', direction: 'higher', get: (p) => parseSpecNumber(p.specs?.ram), display: (p) => p.specs?.ram },
  { key: 'storage', label: 'Storage', direction: 'higher', get: (p) => parseSpecNumber(p.specs?.storage), display: (p) => p.specs?.storage },
  { key: 'brand', label: 'Brand', direction: null, get: () => null, display: (p) => p.specs?.brand },
  { key: 'processor', label: 'Processor', direction: null, get: () => null, display: (p) => p.specs?.processor || p.specs?.type },
  { key: 'color', label: 'Color', direction: null, get: () => null, display: (p) => p.specs?.color },
]

const ComparisonSection = memo(function ComparisonSection({ picks, selectedRank, onSelect }) {
  if (!Array.isArray(picks) || picks.length < 2) return null

  const rows = COMPARISON_ROWS.filter((row) =>
    picks.some((pick) => (row.display ? row.display(pick) : row.get(pick)) != null),
  )
  if (rows.length === 0) return null

  const bestWorstByRow = {}
  rows.forEach((row) => {
    if (!row.direction) return
    const known = picks.map((p) => row.get(p)).filter((v) => v != null)
    if (known.length < 2) return
    const best = row.direction === 'lower' ? Math.min(...known) : Math.max(...known)
    const worst = row.direction === 'lower' ? Math.max(...known) : Math.min(...known)
    bestWorstByRow[row.key] = best === worst ? null : { best, worst }
  })

  return (
    <section aria-label="Product comparison">
      <div className="comparison-header">
        <h2>Compare top {picks.length} picks</h2>
        <p>Click a product to view its complete details above.</p>
      </div>
      <div className="comparison" role="region" aria-label="Comparison table">
        <table>
          <caption className="sr-only">Side-by-side comparison of the top {picks.length} picks</caption>
          <thead>
            <tr>
              <th scope="col">Product</th>
              {rows.map((row) => (
                <th scope="col" key={row.key}>{row.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {picks.map((pick) => (
              <tr key={pick.rank} className={pick.rank === selectedRank ? 'selected-row' : undefined}>
                <td>
                  <div className="product-cell">
                    <button type="button" className="product-link" onClick={() => onSelect(pick.rank)}>
                      {pick.name ?? `Pick ${pick.rank}`}
                    </button>
                    <span className="product-store">Click to view details</span>
                  </div>
                </td>
                {rows.map((row) => {
                  const numericValue = row.direction ? row.get(pick) : null
                  const raw = row.display ? row.display(pick) : row.get(pick)
                  const shown = row.format && numericValue != null ? row.format(numericValue) : raw ?? '—'
                  const bw = bestWorstByRow[row.key]

                  let cellClass = ''
                  if (bw && numericValue != null) {
                    if (numericValue === bw.best) cellClass = 'spec-best'
                    else if (numericValue === bw.worst) cellClass = 'spec-worse'
                  }

                  return <td key={row.key} className={cellClass || undefined}>{shown}</td>
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="comparison-legend" aria-hidden="true">
        <div className="legend-item"><span className="legend-box legend-best" /> Best specification</div>
        <div className="legend-item"><span className="legend-box legend-worse" /> Weaker specification</div>
      </div>
    </section>
  )
})

/* ─────────────────────────────────────────────────────────
   Category top picks (one category with its N products)
   ───────────────────────────────────────────────────────── */

function CategoryTopPicks({ picks, label, idPrefix }) {
  const [selectedRank, setSelectedRank] = useState(picks?.[0]?.rank ?? 1)

  // Sync selection when picks data changes
  useEffect(() => {
    if (Array.isArray(picks) && picks.length > 0) {
      if (!picks.some((p) => p.rank === selectedRank)) {
        setSelectedRank(picks[0].rank)
      }
    }
  }, [picks, selectedRank])

  const handleSelect = useCallback((rank) => setSelectedRank(rank), [])

  if (!Array.isArray(picks) || picks.length === 0) return null

  const selectedPick = picks.find((p) => p.rank === selectedRank) || picks[0]

  return (
    <section
      className="top-picks"
      id={`picks-${idPrefix}`}
      role="tabpanel"
      aria-label={label || 'Top picks'}
    >
      {label && <div className="top-picks-label">{label}</div>}

      {picks.length > 1 && (
        <ProductSelector picks={picks} selectedRank={selectedPick.rank} onSelect={handleSelect} />
      )}

      <RecommendedHero pick={selectedPick} />
      <WhyAndFeatures pick={selectedPick} />
      <SuitsYou pick={selectedPick} />
      <BuyCard pick={selectedPick} />
      <ComparisonSection picks={picks} selectedRank={selectedPick.rank} onSelect={handleSelect} />
    </section>
  )
}

/* ─────────────────────────────────────────────────────────
   Main panel — dispatches to single or multi-category
   ───────────────────────────────────────────────────────── */

function TopPicksPanel({ product }) {
  if (!product || typeof product !== 'object') return null

  if (isTopPicksShape(product)) {
    return <CategoryTopPicks picks={product.top_picks} idPrefix="single" />
  }

  const entries = Object.entries(product).filter(([, value]) => isTopPicksShape(value))
  if (entries.length === 0) return null

  return (
    <div className="top-picks-group">
      {entries.map(([category, value]) => (
        <CategoryTopPicks
          key={category}
          picks={value.top_picks}
          label={category}
          idPrefix={category}
        />
      ))}
    </div>
  )
}

export default memo(TopPicksPanel)