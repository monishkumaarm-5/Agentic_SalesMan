import { useState, useCallback, useRef, useEffect } from 'react'
import { sendMessage as apiSendMessage, getCompanyInfo } from '../api.js'
import { useLocalStorage } from './useLocalStorage.js'

const STORAGE_KEY = 'agentic-salesman:chat-v1'
const DEFAULT_COMPANY_NAME = 'Trein'

function createId(prefix) {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const createThreadId = () => createId('thread')

// Globally unique (not a per-mount counter): messages restored from
// localStorage keep their ids, so a counter restarting at 1 after a reload
// would hand out duplicate React keys.
const newMessageId = (suffix) => `${createId('msg')}-${suffix}`

function buildWelcomeMessage(companyName) {
  return {
    id: 'welcome',
    role: 'assistant',
    content:
      `Welcome to **${companyName}**! I'm your AI shopping assistant. Tell me what you're looking for — ` +
      "**mobiles**, **laptops**, **TVs**, **appliances** and more — and I'll find the perfect match for you.",
  }
}

/**
 * Encapsulates all chat state: messages, thread id, company info,
 * sending status, and localStorage persistence.
 */
export function useChat() {
  const [stored, setStored, clearStored] = useLocalStorage(STORAGE_KEY, null)

  const [messages, setMessages] = useState(() =>
    stored?.messages ?? [buildWelcomeMessage(DEFAULT_COMPANY_NAME)],
  )
  const [threadId, setThreadId] = useState(() => stored?.threadId ?? createThreadId())
  const [companyInfo, setCompanyInfo] = useState(null)
  const [isSending, setIsSending] = useState(false)

  // In-flight request, so "New chat" can cancel it instead of letting its
  // reply land in the fresh conversation.
  const inFlight = useRef(null)
  useEffect(() => () => inFlight.current?.abort(), [])

  // Fetch company info once
  useEffect(() => {
    let cancelled = false
    getCompanyInfo()
      .then((info) => {
        if (cancelled || !info) return
        setCompanyInfo(info)
        // Update the welcome message with actual company name (only if still on initial state)
        setMessages((prev) =>
          !stored && prev.length === 1 && prev[0].id === 'welcome'
            ? [buildWelcomeMessage(info.name || DEFAULT_COMPANY_NAME)]
            : prev,
        )
      })
      .catch((error) => console.warn('[app] failed to load company info', error))
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Persist to localStorage whenever messages or threadId change
  useEffect(() => {
    setStored({ threadId, messages })
  }, [threadId, messages, setStored])

  const sendMessage = useCallback(
    async (question) => {
      if (inFlight.current) return // one turn at a time per conversation
      const controller = new AbortController()
      inFlight.current = controller

      const userMessage = { id: newMessageId('user'), role: 'user', content: question }
      setMessages((prev) => [...prev, userMessage])
      setIsSending(true)

      try {
        const result = await apiSendMessage(question, threadId, controller.signal)
        if (controller.signal.aborted) return
        if (result?.thread_id) setThreadId(result.thread_id)
        setMessages((prev) => [
          ...prev,
          {
            id: newMessageId('assistant'),
            role: 'assistant',
            content: result.answer,
            response_type: result.response_type || 'normal',
            product: result.product,
            candidates: result.candidates,
            confidence: result.confidence,
          },
        ])
      } catch (error) {
        if (controller.signal.aborted || error?.name === 'AbortError') return
        console.error('[app] send message failed', error)
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
        if (inFlight.current === controller) {
          inFlight.current = null
          setIsSending(false)
        }
      }
    },
    [threadId],
  )

  const resetChat = useCallback(() => {
    inFlight.current?.abort()
    inFlight.current = null
    setIsSending(false)
    clearStored()
    setMessages([buildWelcomeMessage(companyInfo?.name || DEFAULT_COMPANY_NAME)])
    setThreadId(createThreadId())
  }, [companyInfo, clearStored])

  return {
    messages,
    isSending,
    companyInfo,
    sendMessage,
    resetChat,
    companyName: companyInfo?.name || DEFAULT_COMPANY_NAME,
  }
}