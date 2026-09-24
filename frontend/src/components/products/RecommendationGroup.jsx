import ProductCard from './ProductCard.jsx'

export default function RecommendationGroup({ group, showLabel, isSelected, onToggleCompare, onDetails }) {
  if (!group?.picks?.length) return null
  return (
    <section className="rec-group" aria-label={`${group.category} recommendations`}>
      {showLabel && <h3 className="rec-label">{group.category}</h3>}
      <div className="product-grid">
        {group.picks.map((p, i) => (
          <ProductCard
            key={p.name}
            product={p}
            featured={i === 0}
            selected={isSelected?.(p)}
            onToggleCompare={onToggleCompare}
            onDetails={onDetails}
          />
        ))}
      </div>
    </section>
  )
}
