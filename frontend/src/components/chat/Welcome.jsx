import { formatPriceShort } from '../../utils/format.js'
import { starterPrompts } from '../../utils/prompts.js'
import { SparkIcon } from '../layout/Icons.jsx'

export default function Welcome({ company, categories, onSend }) {
  const name = company?.name || 'our store'
  const prompts = categories.length ? starterPrompts(categories) : ['What do you sell?', 'Help me find a gift']
  return (
    <section className="welcome" aria-labelledby="welcome-title">
      <div className="welcome-badge"><SparkIcon width={14} height={14} /> AI shopping assistant</div>
      <h2 id="welcome-title">
        Find the right product at <span className="gradient-text">{name}</span>
      </h2>
      <p className="welcome-sub">
        Tell me what you need in your own words -- budget, how you'll use it, must-have features. I'll ask
        only what matters and show honest picks from our real catalog.
      </p>

      <div className="starter-grid">
        {prompts.map((prompt) => (
          <button key={prompt} type="button" className="starter" onClick={() => onSend(prompt)}>
            {prompt}
          </button>
        ))}
      </div>

      {categories.length > 0 && (
        <div className="category-section">
          <h3>Browse by category</h3>
          <div className="category-grid">
            {categories.map((c) => (
              <button
                key={c.name}
                type="button"
                className="category-tile"
                onClick={() => onSend(`I'm looking for a ${c.name.toLowerCase()}`)}
              >
                <span className="category-name">{c.name}</span>
                <span className="category-meta">
                  {c.product_count} products
                  {c.min_price != null && ` · from ${formatPriceShort(c.min_price)}`}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {company?.cities?.length > 0 && (
        <p className="welcome-foot">
          Showrooms in {company.cities.join(', ')} · {company.website?.replace(/^https?:\/\//, '')}
        </p>
      )}
    </section>
  )
}
