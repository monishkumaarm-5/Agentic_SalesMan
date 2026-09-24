import { buildComparison } from '../../utils/compare.js'

export default function CompareTable({ products }) {
  if (!products || products.length < 2) return null
  const rows = buildComparison(products)
  return (
    <div className="compare-wrap" role="region" aria-label="Product comparison" tabIndex={0}>
      <table className="compare-table">
        <thead>
          <tr>
            <th scope="col"><span className="sr-only">Spec</span></th>
            {products.map((p) => (
              <th scope="col" key={p.name}>
                <span className="pc-brand">{p.brand}</span>
                <span className="compare-name">{p.name}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className={row.differs ? 'differs' : undefined}>
              <th scope="row">{row.label}</th>
              {row.cells.map((cell, i) => (
                <td key={products[i].name} className={cell.tone ? `tone-${cell.tone}` : undefined}>
                  {cell.text}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="compare-legend"><span className="dot best" /> better <span className="dot worst" /> weaker, relative to each other</p>
    </div>
  )
}
