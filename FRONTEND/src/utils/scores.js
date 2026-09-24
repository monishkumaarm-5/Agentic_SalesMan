/**
 * Score & top-picks shape helpers.
 * Single source of truth — shared by ChatMessage, TopPicks and CandidateScores.
 */

/**
 * Convert a raw score (typically 0–1) into a clamped 0–100 integer percentage.
 * @param {number|null|undefined} value
 * @returns {number}
 */
export function getScorePercentage(value) {
  return Math.round(Math.max(0, Math.min(1, value ?? 0)) * 100)
}

/**
 * Map a score percentage to a qualitative tier used for styling.
 * Must match the four tiers App.css actually defines
 * (.score-bar-excellent/-strong/-good/-weak) -- returning anything else
 * (e.g. 'high'/'medium'/'low') silently drops all score-bar coloring.
 * @param {number} pct  0–100
 * @returns {'excellent'|'strong'|'good'|'weak'}
 */
export function getScoreTier(pct) {
  if (pct >= 85) return 'excellent'
  if (pct >= 70) return 'strong'
  if (pct >= 50) return 'good'
  return 'weak'
}

/**
 * Does this object look like a single category's top-picks payload?
 * i.e. `{ top_picks: [...] }` with at least one pick.
 * @param {*} value
 * @returns {boolean}
 */
export function isTopPicksShape(value) {
  return (
    value != null &&
    typeof value === 'object' &&
    Array.isArray(value.top_picks) &&
    value.top_picks.length > 0
  )
}

/**
 * Does this recommendation product contain any top picks, whether as a
 * single category shape or a multi-category map of them?
 * @param {*} product
 * @returns {boolean}
 */
export function hasTopPicks(product) {
  if (!product || typeof product !== 'object') return false
  if (isTopPicksShape(product)) return true
  return Object.values(product).some((value) => isTopPicksShape(value))
}
