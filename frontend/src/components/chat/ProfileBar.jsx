import { profileChips } from '../../utils/format.js'

/** What the assistant has understood so far -- makes its memory visible. */
export default function ProfileBar({ profile }) {
  const chips = profileChips(profile)
  if (!chips.length) return null
  return (
    <div className="profile-bar" aria-label="What the assistant knows about your needs">
      <span className="profile-label">Looking for</span>
      {chips.map((c) => (
        <span key={c.key} className={`chip chip-${c.kind}`}>{c.label}</span>
      ))}
    </div>
  )
}
