import { percent } from '../../utils/format.js'

export default function MatchMeter({ value, size = 44 }) {
  const pct = percent(value)
  if (pct == null) return null
  const r = (size - 6) / 2
  const c = 2 * Math.PI * r
  const tone = pct >= 75 ? 'high' : pct >= 55 ? 'mid' : 'low'
  return (
    <div className={`match-meter match-${tone}`} title="How well this matches what you asked for" style={{ width: size, height: size }}>
      <svg width={size} height={size} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} className="match-track" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          className="match-fill"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct / 100)}
        />
      </svg>
      <span className="match-value" aria-label={`${pct}% match`}>{pct}%</span>
    </div>
  )
}
