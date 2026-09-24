import { CompareIcon, XIcon } from '../layout/Icons.jsx'

export default function CompareTray({ items, onRemove, onClear, onCompare }) {
  if (!items.length) return null
  return (
    <div className="compare-tray" role="region" aria-label="Products selected for comparison">
      <div className="tray-items">
        {items.map((p) => (
          <span key={p.name} className="chip chip-tray">
            {p.name}
            <button type="button" onClick={() => onRemove(p)} aria-label={`Remove ${p.name}`}><XIcon width={12} height={12} /></button>
          </span>
        ))}
      </div>
      <div className="tray-actions">
        <button type="button" className="btn btn-ghost" onClick={onClear}>Clear</button>
        <button type="button" className="btn btn-primary" onClick={onCompare} disabled={items.length < 2}>
          <CompareIcon width={16} height={16} /> Compare {items.length}
        </button>
      </div>
    </div>
  )
}
