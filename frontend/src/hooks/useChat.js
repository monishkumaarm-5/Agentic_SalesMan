import { useCallback, useEffect, useRef, useState } from 'react'
import { streamChat } from '../api/client.js'
import { createId } from '../utils/format.js'
import { useLocalStorage } from './useLocalStorage.js'

const STORAGE_KEY = 'salesman:chat-v3'
const EMPTY = { threadId: null, messages: [], profile: {} }

/**
 * All conversation state: messages, the thread id, live progress while
 * the assistant works, and the shopping profile it has built up.
 */
export function useChat() {
  const [saved, setSaved] = useLocalStorage(STORAGE_KEY, EMPTY)
  const [messages, setMessages] = useState(() => saved?.messages ?? [])
  const [threadId, setThreadId] = useState(() => saved?.threadId ?? createId('thread'))
  const [profile, setProfile] = useState(() => saved?.profile ?? {})
  const [steps, setSteps] = useState([])
  const [isSending, setIsSending] = useState(false)
  const inFlight = useRef(null)

  useEffect(() => {
    setSaved({ threadId, messages: messages.filter((m) => !m.error), profile })
  }, [threadId, messages, profile, setSaved])

  useEffect(() => () => inFlight.current?.abort(), [])

  const send = useCallback(
    async (text) => {
      const message = text.trim()
      if (!message || inFlight.current) return
      const controller = new AbortController()
      inFlight.current = controller

      setMessages((prev) => [...prev.filter((m) => !m.error), { id: createId('msg'), role: 'user', content: message }])
      setSteps([])
      setIsSending(true)

      try {
        const result = await streamChat(message, threadId, {
          signal: controller.signal,
          onStatus: (status) =>
            setSteps((prev) => (prev.some((s) => s.step === status.step) ? prev : [...prev, status])),
        })
        if (controller.signal.aborted) return
        if (result.thread_id && result.thread_id !== threadId) setThreadId(result.thread_id)
        if (result.profile) setProfile(result.profile)
        setMessages((prev) => [
          ...prev,
          {
            id: createId('msg'),
            role: 'assistant',
            content: result.answer,
            type: result.response_type,
            recommendations: result.recommendations,
            products: result.products,
            comparison: result.comparison,
            suggestions: result.suggestions,
            confidence: result.confidence,
          },
        ])
      } catch (error) {
        if (controller.signal.aborted || error?.name === 'AbortError') return
        setMessages((prev) => [
          ...prev,
          { id: createId('msg'), role: 'assistant', error: true, content: error.message, retry: message },
        ])
      } finally {
        if (inFlight.current === controller) {
          inFlight.current = null
          setIsSending(false)
          setSteps([])
        }
      }
    },
    [threadId],
  )

  const stop = useCallback(() => {
    inFlight.current?.abort()
    inFlight.current = null
    setIsSending(false)
    setSteps([])
  }, [])

  const retry = useCallback(
    (message) => {
      setMessages((prev) => {
        // drop the error bubble and the user message it belongs to
        const i = prev.findLastIndex((m) => m.role === 'user' && m.content === message)
        return i === -1 ? prev.filter((m) => !m.error) : prev.slice(0, i)
      })
      setTimeout(() => send(message), 0)
    },
    [send],
  )

  const reset = useCallback(() => {
    stop()
    setMessages([])
    setProfile({})
    setThreadId(createId('thread'))
  }, [stop])

  return { messages, threadId, profile, steps, isSending, send, stop, retry, reset }
}
