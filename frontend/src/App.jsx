import { useCallback, useEffect, useState } from 'react'
import { getCategories, getCompany } from './api/client.js'
import Composer from './components/chat/Composer.jsx'
import Message from './components/chat/Message.jsx'
import ProfileBar from './components/chat/ProfileBar.jsx'
import StatusIndicator from './components/chat/StatusIndicator.jsx'
import Welcome from './components/chat/Welcome.jsx'
import ErrorBoundary from './components/layout/ErrorBoundary.jsx'
import Header from './components/layout/Header.jsx'
import CompareTable from './components/products/CompareTable.jsx'
import CompareTray from './components/products/CompareTray.jsx'
import Modal from './components/products/Modal.jsx'
import ProductDetails from './components/products/ProductDetails.jsx'
import { useAutoScroll } from './hooks/useAutoScroll.js'
import { useChat } from './hooks/useChat.js'
import { useTheme } from './hooks/useTheme.js'

const MAX_COMPARE = 4

export default function App() {
  const chat = useChat()
  const { isDark, toggle } = useTheme()
  const [company, setCompany] = useState(null)
  const [categories, setCategories] = useState([])
  const [details, setDetails] = useState(null)
  const [compareItems, setCompareItems] = useState([])
  const [comparing, setComparing] = useState(false)
  const scrollRef = useAutoScroll([chat.messages, chat.steps])

  useEffect(() => {
    const controller = new AbortController()
    getCompany(controller.signal).then(setCompany).catch(() => {})
    getCategories(controller.signal)
      .then((list) => Array.isArray(list) && setCategories(list))
      .catch(() => {})
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (company?.name) document.title = `${company.name} · Shopping Assistant`
  }, [company])

  const isSelected = useCallback((p) => compareItems.some((c) => c.name === p.name), [compareItems])
  const toggleCompare = useCallback((p) => {
    setCompareItems((items) =>
      items.some((c) => c.name === p.name)
        ? items.filter((c) => c.name !== p.name)
        : [...items, p].slice(-MAX_COMPARE),
    )
  }, [])

  const reset = () => {
    chat.reset()
    setCompareItems([])
  }

  const empty = chat.messages.length === 0
  const lastAssistant = chat.messages.findLast((m) => m.role === 'assistant')

  return (
    <div className="app">
      <Header
        company={company}
        isDark={isDark}
        onToggleTheme={toggle}
        onNewChat={reset}
        canReset={!empty || chat.isSending}
      />

      <main className="chat-scroll" ref={scrollRef}>
        <ErrorBoundary>
          <div className="chat-column">
            {empty ? (
              <Welcome company={company} categories={categories} onSend={chat.send} />
            ) : (
              <div className="messages" aria-live="polite">
                {chat.messages.map((m) => (
                  <Message
                    key={m.id}
                    message={m}
                    isLatest={m === lastAssistant && !chat.isSending}
                    busy={chat.isSending}
                    onSend={chat.send}
                    onRetry={chat.retry}
                    isSelected={isSelected}
                    onToggleCompare={toggleCompare}
                    onDetails={setDetails}
                  />
                ))}
                {chat.isSending && <StatusIndicator steps={chat.steps} />}
              </div>
            )}
          </div>
        </ErrorBoundary>
      </main>

      <footer className="dock">
        <div className="chat-column">
          <CompareTray
            items={compareItems}
            onRemove={toggleCompare}
            onClear={() => setCompareItems([])}
            onCompare={() => setComparing(true)}
          />
          <ProfileBar profile={chat.profile} />
          <Composer onSend={chat.send} onStop={chat.stop} isSending={chat.isSending} />
          <p className="disclaimer">
            Prices and stock come from our live catalog. The assistant can make mistakes -- check details before buying.
          </p>
        </div>
      </footer>

      {details && <ProductDetails product={details} onClose={() => setDetails(null)} />}
      {comparing && compareItems.length >= 2 && (
        <Modal title="Compare products" wide onClose={() => setComparing(false)}>
          <CompareTable products={compareItems} />
        </Modal>
      )}
    </div>
  )
}
