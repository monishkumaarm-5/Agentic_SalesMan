import { useCallback, useMemo, memo } from 'react'
import ChatMessage from './components/ChatMessage.jsx'
import ChatInput from './components/ChatInput.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { useChat } from './hooks/useChat.js'
import { useScrollToBottom } from './hooks/useScrollToBottom.js'
import './App.css'

/* ── Suggested prompts ────────────────────────────────── */

const SUGGESTIONS = [
  'Recommend a laptop for coding under ₹1,20,000',
  'Best noise-cancelling headphones',
  'Which phone has the best camera?',
  'Suggest a refrigerator for a family of four',
  'What TV is best for gaming?',
]

/* ── Icon components (pure, memoised) ─────────────────── */

const ShoppingBagIcon = memo(function ShoppingBagIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <path d="M16 10a4 4 0 01-8 0" />
    </svg>
  )
})

const PlusIcon = memo(function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true" focusable="false">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  )
})

const SendIcon = memo(function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
})

/* ── Suggestion strip ─────────────────────────────────── */

const SuggestionStrip = memo(function SuggestionStrip({ onSend }) {
  return (
    <div className="suggestions" role="region" aria-label="Suggested prompts">
      {SUGGESTIONS.map((suggestion) => (
        <button key={suggestion} type="button" onClick={() => onSend(suggestion)}>
          {suggestion}
        </button>
      ))}
    </div>
  )
})

/* ── Typing indicator ─────────────────────────────────── */

const TypingIndicator = memo(function TypingIndicator() {
  return (
    <div className="message-row from-assistant" aria-live="polite" aria-label="Assistant is typing">
      <div className="avatar assistant" aria-hidden="true">AI</div>
      <div className="bubble typing">
        <span className="dot" />
        <span className="dot" />
        <span className="dot" />
      </div>
    </div>
  )
})

/* ── Brand footer ─────────────────────────────────────── */

const BrandFooter = memo(function BrandFooter({ companyInfo, uniqueCities }) {
  if (!companyInfo) return null

  return (
    <div className="brand-footer">
      <span className="brand-footer-name">{companyInfo.name}</span>
      {companyInfo.website && (
        <a
          className="brand-footer-link"
          href={companyInfo.website}
          target="_blank"
          rel="noopener noreferrer"
        >
          {companyInfo.website.replace(/^https?:\/\//, '')}
        </a>
      )}
      {Array.isArray(companyInfo.stores) && companyInfo.stores.length > 0 && (
        <span className="brand-footer-stores">
          {companyInfo.stores.length} store{companyInfo.stores.length === 1 ? '' : 's'} &middot; {uniqueCities}
        </span>
      )}
    </div>
  )
})

/* ── App ──────────────────────────────────────────────── */

function App() {
  const { messages, isSending, companyInfo, sendMessage, resetChat, companyName } = useChat()

  const bottomRef = useScrollToBottom([messages, isSending])

  const handleSend = useCallback(
    (question) => sendMessage(question),
    [sendMessage],
  )

  const uniqueCities = useMemo(() => {
    if (!Array.isArray(companyInfo?.stores)) return ''
    return [...new Set(companyInfo.stores.map((s) => s.city).filter(Boolean))].join(', ')
  }, [companyInfo])

  return (
    <div className="app-shell">
      {/* Skip link for keyboard users */}
      <a href="#chat-main" className="sr-only sr-only-focusable">
        Skip to chat
      </a>

      <header className="app-header">
        <div className="header-brand">
          <div className="header-logo">
            <ShoppingBagIcon />
          </div>
          <div className="header-text">
            <h1>{companyName}</h1>
            <p>{companyInfo?.tagline || 'AI Shopping Assistant'}</p>
          </div>
        </div>
        <div className="header-actions">
          <button
            type="button"
            className="reset-button"
            onClick={resetChat}
            aria-label="Start a new chat thread"
          >
            <PlusIcon />
            New chat
          </button>
        </div>
      </header>

      <ErrorBoundary>
        <main
          id="chat-main"
          className="chat-window"
          aria-label="Chat conversation history"
          tabIndex={0}
        >
          {messages.map((message) => (
            <ChatMessage key={message.id} {...message} />
          ))}

          {isSending && <TypingIndicator />}

          <div ref={bottomRef} />
        </main>
      </ErrorBoundary>

      {messages.length <= 1 && <SuggestionStrip onSend={handleSend} />}

      <footer className="app-footer">
        <ChatInput onSend={handleSend} disabled={isSending} SendIcon={SendIcon} />
        <BrandFooter companyInfo={companyInfo} uniqueCities={uniqueCities} />
      </footer>
    </div>
  )
}

export default App