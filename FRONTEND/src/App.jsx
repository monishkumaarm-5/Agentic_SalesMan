import { useEffect, useRef, useState } from 'react'
import ChatMessage from './components/ChatMessage.jsx'
import ChatInput from './components/ChatInput.jsx'
import { sendMessage } from './api.js'
import './App.css'

const WELCOME_MESSAGE = {
  id: 'welcome',
  role: 'assistant',
  content:
    "Hi! I'm your Agentic SalesMan assistant. Ask me about **phones**, **laptops** or **headphones** and I'll recommend the best match.",
}

const SUGGESTIONS = [
  'Recommend a laptop for coding under $1500',
  'Best noise-cancelling headphones',
  'Which phone has the best camera?',
]

const STORAGE_KEY = 'agentic-salesman:chat-v1'

function createThreadId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `thread-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function loadStoredChat() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (!parsed || !Array.isArray(parsed.messages) || !parsed.threadId) return null
    return parsed
  } catch {
    // Private browsing, storage disabled, corrupted value, etc. -- just
    // start fresh rather than breaking the app.
    return null
  }
}

function saveStoredChat(threadId, messages) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ threadId, messages }))
  } catch {
    // Storage full/unavailable -- the chat still works, it just won't
    // survive a refresh this time.
  }
}

function clearStoredChat() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // ignore
  }
}

function App() {
  // Lazy initializers (the () => ... form) run exactly once, on the first
  // render, which is what makes it safe to read localStorage here rather
  // than via a ref/effect.
  const [messages, setMessages] = useState(() => loadStoredChat()?.messages ?? [WELCOME_MESSAGE])
  const [threadId, setThreadId] = useState(() => loadStoredChat()?.threadId ?? createThreadId())
  const [isSending, setIsSending] = useState(false)
  const bottomRef = useRef(null)
  const nextMessageId = useRef(0)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isSending])

  useEffect(() => {
    saveStoredChat(threadId, messages)
  }, [threadId, messages])

  const newMessageId = (suffix) => `${(nextMessageId.current += 1)}-${suffix}`

  const handleSend = async (question) => {
    const userMessage = { id: newMessageId('user'), role: 'user', content: question }
    setMessages((prev) => [...prev, userMessage])
    setIsSending(true)

    try {
      const result = await sendMessage(question, threadId)
      setThreadId(result.thread_id)
      setMessages((prev) => [
        ...prev,
        {
          id: newMessageId('assistant'),
          role: 'assistant',
          content: result.answer,
          product: result.product,
          candidates: result.candidates,
          confidence: result.confidence,
        },
      ])
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: newMessageId('error'),
          role: 'assistant',
          content: `Something went wrong: ${error.message}`,
          isError: true,
        },
      ])
    } finally {
      setIsSending(false)
    }
  }

  const handleReset = () => {
    clearStoredChat()
    setMessages([WELCOME_MESSAGE])
    setThreadId(createThreadId())
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Agentic SalesMan</h1>
          <p>Your multi-agent shopping assistant for phones, laptops &amp; headphones</p>
        </div>
        <button type="button" className="reset-button" onClick={handleReset}>
          New conversation
        </button>
      </header>

      <main className="chat-window">
        {messages.map((message) => (
          <ChatMessage key={message.id} {...message} />
        ))}
        {isSending && (
          <div className="message-row from-assistant">
            <div className="avatar assistant">AI</div>
            <div className="bubble typing">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </main>

      {messages.length <= 1 && (
        <div className="suggestions">
          {SUGGESTIONS.map((suggestion) => (
            <button key={suggestion} type="button" onClick={() => handleSend(suggestion)}>
              {suggestion}
            </button>
          ))}
        </div>
      )}

      <footer className="app-footer">
        <ChatInput onSend={handleSend} disabled={isSending} />
      </footer>
    </div>
  )
}

export default App
