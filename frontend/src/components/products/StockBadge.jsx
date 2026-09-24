export default function StockBadge({ product }) {
  const { in_stock: inStock, units_available: units } = product
  if (inStock == null) return null
  if (!inStock) return <span className="badge badge-danger">Out of stock</span>
  if (units != null && units <= 5) return <span className="badge badge-warn">Only {units} left</span>
  return <span className="badge badge-success">In stock</span>
}
