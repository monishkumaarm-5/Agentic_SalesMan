// Renders the result of POST /api/compare (see api.js's compareProducts) --
// a plain spec-by-spec table, with rows the backend flagged as differing
// (comparison.differing_fields) visually highlighted.
function ComparisonTable({ comparison }) {
  if (!comparison || !comparison.products) return null

  const names = Object.keys(comparison.products)
  if (names.length < 2) return null

  const fields = Array.from(
    new Set(names.flatMap((name) => Object.keys(comparison.products[name] || {})))
  )
    .filter((field) => field !== 'name')
    .sort()
  const differing = new Set(comparison.differing_fields || [])

  return (
    <div className="comparison-table-wrap">
      <table className="comparison-table">
        <thead>
          <tr>
            <th>Spec</th>
            {names.map((name) => (
              <th key={name}>{name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => (
            <tr key={field} className={differing.has(field) ? 'differs' : ''}>
              <td>{field}</td>
              {names.map((name) => (
                <td key={name}>{String(comparison.products[name]?.[field] ?? '—')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default ComparisonTable
