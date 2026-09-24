import { memo, useMemo } from 'react'
import { formatINR, formatSpecValue } from '../utils/format.js'
import { SPEC_LABELS } from '../utils/specRules.js'

/* ── Field presentation ───────────────────────────────── */

// Columns the backend may return (POST /api/compare hands back each
// product's full catalog row) that mean nothing to a shopper.
const HIDDEN_FIELDS = new Set([
  'id',
  'name',
  'attributes',
  'created_at',
  'updated_at',
  'ingestion_status',
  'ingestion_missing_fields',
  'customer_feedback',
  'description',
])

const EXTRA_LABELS = {
  price: 'Price',
  mrp: 'MRP',
  category: 'Category',
  rating: 'Rating',
  units_available: 'Units available',
  online_link: 'Online link',
  offline_availability: 'Offline availability',
}

const CURRENCY_FIELDS = new Set(['price', 'mrp'])

// Most useful rows first; everything else follows alphabetically.
const FIELD_ORDER = ['price', 'mrp', 'brand', 'rating']

function labelFor(field) {
  return EXTRA_LABELS[field] || SPEC_LABELS[field] || field.replace(/_/g, ' ')
}

function formatCell(field, value) {
  if (CURRENCY_FIELDS.has(field)) return formatINR(value) ?? '—'
  return formatSpecValue(value)
}

function orderFields(fields) {
  return [...fields].sort((a, b) => {
    const ia = FIELD_ORDER.indexOf(a)
    const ib = FIELD_ORDER.indexOf(b)
    if (ia !== -1 || ib !== -1) return (ia === -1 ? Infinity : ia) - (ib === -1 ? Infinity : ib)
    return a.localeCompare(b)
  })
}

/* ── Component ────────────────────────────────────────── */

/**
 * Renders the result of POST /api/compare:
 *   { category, products: { [name]: row }, differing_fields: [...], missing: [...] }
 * as a spec-by-spec table (one column per product), with the rows the
 * backend flagged as differing highlighted.
 */
function ComparisonTable({ comparison }) {
  const products = comparison?.products
  const names = useMemo(
    () => (products && typeof products === 'object' ? Object.keys(products) : []),
    [products],
  )

  const fields = useMemo(() => {
    const all = new Set(names.flatMap((name) => Object.keys(products[name] || {})))
    return orderFields([...all].filter((field) => !HIDDEN_FIELDS.has(field)))
  }, [names, products])

  if (names.length < 2 || fields.length === 0) return null

  const differing = new Set(comparison.differing_fields || [])
  const missing = Array.isArray(comparison.missing) ? comparison.missing : []

  return (
    <div className="comparison-table-wrap" role="region" aria-label="Product comparison">
      <table className="comparison-table">
        <caption className="sr-only">Side-by-side comparison of {names.join(', ')}</caption>
        <thead>
          <tr>
            <th scope="col">Spec</th>
            {names.map((name) => (
              <th scope="col" key={name}>{name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => (
            <tr key={field} className={differing.has(field) ? 'differs' : undefined}>
              <th scope="row">{labelFor(field)}</th>
              {names.map((name) => (
                <td key={name}>{formatCell(field, products[name]?.[field])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {missing.length > 0 && (
        <p className="comparison-missing">Not found in the catalog: {missing.join(', ')}</p>
      )}
    </div>
  )
}

export default memo(ComparisonTable)
