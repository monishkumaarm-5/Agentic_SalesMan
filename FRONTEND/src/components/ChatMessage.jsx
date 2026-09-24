import { memo, lazy, Suspense, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import { hasTopPicks } from '../utils/scores.js'

// Lazy-load heavy sub-components — they contain large rule sets and tables
const TopPicksPanel = lazy(() => import('./TopPicks.jsx'))
const CandidateScores = lazy(() => import('./CandidateScores.jsx'))

/* ── Confidence badge ─────────────────────────────────── */

const CONFIDENCE_TIERS = { high: 75, medium: 50 }

function tierFor(pct) {
  if (pct >= CONFIDENCE_TIERS.high) return 'high'
  if (pct >= CONFIDENCE_TIERS.medium) return 'medium'
  return 'low'
}

const ConfidenceBadge = memo(function ConfidenceBadge({ confidence }) {
  if (confidence == null) return null

  const pct = Math.round(Math.max(0, Math.min(1, Number(confidence))) * 100)
  const tier = tierFor(pct)

  return (
    <div
      className={`confidence-badge confidence-${tier}`}
      title="Evaluator match confidence level"
      aria-label={`Confidence level: ${pct}%`}
    >
      Confidence: {pct}%
    </div>
  )
})

/* ── Recommendation content ───────────────────────────── */

function RecommendationContent({ confidence, content, product, candidates, showTopPicks }) {
  return (
    <Suspense fallback={<p className="loading-text">Loading details…</p>}>
      <ConfidenceBadge confidence={confidence} />
      {!showTopPicks && content && <ReactMarkdown>{content}</ReactMarkdown>}
      <TopPicksPanel product={product} />
      <CandidateScores candidates={candidates} />
    </Suspense>
  )
}

/* ── Chat message ─────────────────────────────────────── */

function ChatMessage({
  role,
  content,
  isError = false,
  response_type,
  product,
  candidates,
  confidence,
}) {
  const isUser = role === 'user'
  const isRecommendation = !isUser && response_type === 'recommendation' && !isError
  const showTopPicks = isRecommendation && hasTopPicks(product)

  const bubbleClass = `bubble${isError ? ' error' : ''}`

  // Descriptive label for screen readers
  const ariaLabel = useMemo(() => {
    if (isUser) return 'Your message'
    if (isError) return 'Error message'
    return 'Assistant response'
  }, [isUser, isError])

  return (
    <div
      className={`message-row ${isUser ? 'from-user' : 'from-assistant'}`}
      role="article"
      aria-label={ariaLabel}
    >
      <div className={`avatar ${isUser ? 'user' : 'assistant'}`} aria-hidden="true">
        {isUser ? 'You' : 'AI'}
      </div>

      <div className={bubbleClass}>
        {isUser ? (
          <p>{content}</p>
        ) : isRecommendation ? (
          <RecommendationContent
            confidence={confidence}
            content={content}
            product={product}
            candidates={candidates}
            showTopPicks={showTopPicks}
          />
        ) : (
          <ReactMarkdown>
            {content || (isError ? 'Something went wrong.' : '')}
          </ReactMarkdown>
        )}
      </div>
    </div>
  )
}

export default memo(ChatMessage)