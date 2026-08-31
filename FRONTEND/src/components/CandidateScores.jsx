import { useState } from 'react'
import { compareProducts } from '../api.js'
import ComparisonTable from './ComparisonTable.jsx'

const CATEGORY_LABELS = { MOBILE: 'Phone', LAPTOP: 'Laptop', HEADPHONE: 'Headphone' }

// Maps the graph's category keys to TOOLS/product_tools.py's table keys --
// see DATABASE/SQL_CONNECTOR.py's TABLES dict on the backend.
const CATEGORY_TO_TOOL_KEY = { MOBILE: 'phone', LAPTOP: 'laptop', HEADPHONE: 'headphone' }

function ScoreBar({ value }) {
  const pct = Math.round(Math.max(0, Math.min(1, value ?? 0)) * 100)
  return (
    <div className="score-bar" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="score-bar-label">{pct}%</span>
    </div>
  )
}

function CategoryCandidates({ category, candidates, label }) {
  const [comparison, setComparison] = useState(null)
  const [comparing, setComparing] = useState(false)
  const [error, setError] = useState(null)

  const named = candidates.filter((c) => c.name)
  const canCompare = named.length >= 2 && CATEGORY_TO_TOOL_KEY[category]

  const handleCompare = async () => {
    setComparing(true)
    setError(null)
    try {
      const names = named.slice(0, 2).map((c) => c.name)
      const result = await compareProducts(CATEGORY_TO_TOOL_KEY[category], names)
      setComparison(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setComparing(false)
    }
  }

  return (
    <div className="candidate-list">
      {label && <div className="candidate-list-label">{label}</div>}
      <ul>
        {candidates.map((candidate, index) => (
          <li key={candidate.name ?? index} className="candidate-row">
            <span className="candidate-name">{candidate.name ?? 'Unknown product'}</span>
            {candidate.price != null && <span className="candidate-price">₹{candidate.price}</span>}
            <ScoreBar value={candidate._scores?.overall} />
          </li>
        ))}
      </ul>
      {canCompare && !comparison && (
        <button type="button" className="compare-button" onClick={handleCompare} disabled={comparing}>
          {comparing ? 'Comparing…' : 'Compare top matches'}
        </button>
      )}
      {error && <p className="compare-error">{error}</p>}
      {comparison && <ComparisonTable comparison={comparison} />}
    </div>
  )
}

// Renders the scored retrieval shortlist (ChatResponse.candidates, see
// WORKFLOW/scoring.py on the backend) behind a native <details> disclosure,
// so the answer above stays uncluttered but "why did it pick this?" is one
// click away.
function CandidateScores({ candidates }) {
  if (!candidates || typeof candidates !== 'object') return null

  const entries = Object.entries(candidates).filter(
    ([, list]) => Array.isArray(list) && list.length > 0
  )
  if (entries.length === 0) return null

  return (
    <details className="candidate-scores">
      <summary>Why these picks</summary>
      {entries.map(([category, list]) => (
        <CategoryCandidates
          key={category}
          category={category}
          candidates={list}
          label={entries.length > 1 ? (CATEGORY_LABELS[category] ?? category) : null}
        />
      ))}
    </details>
  )
}

export default CandidateScores
