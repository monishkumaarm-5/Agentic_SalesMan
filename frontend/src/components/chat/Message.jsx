import { memo } from 'react'
import { RefreshIcon } from '../layout/Icons.jsx'
import CompareTable from '../products/CompareTable.jsx'
import ProductCard from '../products/ProductCard.jsx'
import RecommendationGroup from '../products/RecommendationGroup.jsx'
import Markdown from './Markdown.jsx'
import QuickReplies from './QuickReplies.jsx'

function Message({ message, isLatest, busy, onSend, onRetry, isSelected, onToggleCompare, onDetails }) {
  if (message.role === 'user') {
    return (
      <div className="message user">
        <div className="bubble">{message.content}</div>
      </div>
    )
  }

  const groups = message.recommendations || []
  return (
    <div className={`message assistant${message.error ? ' error' : ''}`}>
      <div className="avatar" aria-hidden="true">AI</div>
      <div className="assistant-body">
        <div className="bubble">
          {message.error ? (
            <>
              <p>{message.content}</p>
              {message.retry && (
                <button type="button" className="btn btn-ghost" onClick={() => onRetry(message.retry)} disabled={busy}>
                  <RefreshIcon width={15} height={15} /> Try again
                </button>
              )}
            </>
          ) : (
            <Markdown>{message.content}</Markdown>
          )}
        </div>

        {groups.map((group) => (
          <RecommendationGroup
            key={group.category}
            group={group}
            showLabel={groups.length > 1}
            isSelected={isSelected}
            onToggleCompare={onToggleCompare}
            onDetails={onDetails}
          />
        ))}

        {message.comparison?.length >= 2 && <CompareTable products={message.comparison} />}

        {message.products?.length > 0 && (
          <div className="product-grid">
            {message.products.map((p) => (
              <ProductCard key={p.name} product={p} selected={isSelected?.(p)}
                onToggleCompare={onToggleCompare} onDetails={onDetails} />
            ))}
          </div>
        )}

        {isLatest && <QuickReplies items={message.suggestions} onSend={onSend} disabled={busy} />}
      </div>
    </div>
  )
}

export default memo(Message)
