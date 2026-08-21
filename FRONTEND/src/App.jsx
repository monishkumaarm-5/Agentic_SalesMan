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

function createThreadId() {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `thread-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function App() {
  const [messages, setMessages] = useState([WELCOME_MESSAGE])
  const [threadId, setThreadId] = useState(createThreadId)
  const [isSending, setIsSending] = useState(false)
  const bottomRef = useRef(null)
  const nextMessageId = useRef(0)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isSending])

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
        { id: newMessageId('assistant'), role: 'assistant', content: result.answer },
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
