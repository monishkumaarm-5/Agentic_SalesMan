import { useState, useCallback, memo } from 'react'
import { compareProducts } from '../api.js'
import ComparisonTable from './ComparisonTable.jsx'
import { formatINR } from '../utils/format.js'
import { getScorePercentage, getScoreTier } from '../utils/scores.js'

/* ── Score bar ────────────────────────────────────────── */

const ScoreBar = memo(function ScoreBar({ value }) {
  const pct = getScorePercentage(value)
  const tier = getScoreTier(pct)

  return (
    <div
      className={`score-bar score-bar-${tier}`}
      role="meter"
      aria-label={`Product match score: ${pct}%`}
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <span className="score-bar-tag">Match</span>
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="score-bar-label">{pct}%</span>
    </div>
  )
})

/* ── Category candidates ──────────────────────────────── */

function CategoryCandidates({ category, candidates, label }) {
  const [comparison, setComparison] = useState(null)
  const [comparing, setComparing] = useState(false)
  const [error, setError] = useState(null)

  if (!Array.isArray(candidates) || candidates.length === 0) return null

  const named = candidates.filter((c) => c?.name)
  const canCompare = named.length >= 2 && Boolean(category)

  const handleCompare = async () => {
    if (!canCompare || comparing) return
    setComparing(true)
    setError(null)

    try {
      const names = named.slice(0, 2).map((c) => c.name)
      const result = await compareProducts(category, names)
      setComparison(result)
    } catch (err) {
      console.error('[candidate-scores] comparison failed', err)
      setError(err?.message || 'Unable to compare these products right now.')
    } finally {
      setComparing(false)
    }
  }

  return (
    <div className="candidate-list" role="region" aria-label={label || 'Candidate products'}>
      {label && <div className="candidate-list-label">{label}</div>}

      <ul>
        {candidates.map((candidate, index) => {
          const score = candidate?._scores?.overall
          const price = candidate?.price
          const name = candidate?.name || 'Unknown product'

          return (
            <li key={candidate?.name ? `${candidate.name}-${index}` : index} className="candidate-row">
              <div className="candidate-product">
                <span className="candidate-name" title={name}>{name}</span>
                {price != null && (
                  <span className="candidate-price">{formatINR(price)}</span>
                )}
              </div>
              <ScoreBar value={score} />
            </li>
          )
        })}
      </ul>

      {canCompare && !comparison && (
        <button
          type="button"
          className="compare-button"
          onClick={handleCompare}
          disabled={comparing}
          aria-busy={comparing}
        >
          {comparing ? (
            <>
              <span className="spinner-icon" aria-hidden="true" /> Comparing…
            </>
          ) : (
            'Compare top matches'
          )}
        </button>
      )}

      {error && (
        <p className="compare-error" role="alert">
          {error}
        </p>
      )}

      {comparison && <ComparisonTable comparison={comparison} />}
    </div>
  )
}

/* ── Main export ──────────────────────────────────────── */

function CandidateScores({ candidates }) {
  if (!candidates || typeof candidates !== 'object') return null

  const entries = Object.entries(candidates).filter(
    ([, list]) => Array.isArray(list) && list.length > 0,
  )

  if (entries.length === 0) return null

  const totalMatches = entries.reduce((total, [, list]) => total + list.length, 0)

  return (
    <details className="candidate-scores">
      <summary>
        <span>Why these picks</span>
        <span className="candidate-count">{totalMatches} matches</span>
      </summary>

      <div className="candidate-scores-content">
        {entries.map(([category, list]) => (
          <CategoryCandidates
            key={category}
            category={category}
            candidates={list}
            label={entries.length > 1 ? category : null}
          />
        ))}
      </div>
    </details>
  )
}

export default memo(CandidateScores)