import ReactMarkdown from 'react-markdown'
import ProductCard from './ProductCard.jsx'
import CandidateScores from './CandidateScores.jsx'

function ConfidenceBadge({ confidence }) {
  if (confidence == null) return null
  const pct = Math.round(Math.max(0, Math.min(1, confidence)) * 100)
  const tier = pct >= 75 ? 'high' : pct >= 50 ? 'medium' : 'low'
  return (
    <div
      className={`confidence-badge confidence-${tier}`}
      title="How confident the exit evaluator was in this answer"
    >
      Confidence: {pct}%
    </div>
  )
}

function ChatMessage({ role, content, isError, product, candidates, confidence }) {
  const isUser = role === 'user'

  return (
    <div className={`message-row ${isUser ? 'from-user' : 'from-assistant'}`}>
      <div className={`avatar ${isUser ? 'user' : 'assistant'}`}>
        {isUser ? 'You' : 'AI'}
      </div>
      <div className={`bubble ${isError ? 'error' : ''}`}>
        {isUser ? <p>{content}</p> : <ReactMarkdown>{content}</ReactMarkdown>}
        {!isUser && !isError && (
          <>
            <ConfidenceBadge confidence={confidence} />
            <ProductCard product={product} />
            <CandidateScores candidates={candidates} />
          </>
        )}
      </div>
    </div>
  )
}

export default ChatMessage
