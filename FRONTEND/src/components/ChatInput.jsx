import { memo, useRef, useState, useCallback } from 'react'
import { useAutoResize } from '../hooks/useAutoResize.js'

/**
 * Chat input with auto-resizing textarea and keyboard submit.
 *
 * Improvements:
 *  - Wrapped in React.memo (pure — only re-renders when props change)
 *  - useAutoResize extracted to a reusable hook
 *  - useCallback on handlers to keep stable references
 *  - Better focus management: returns focus after send
 */
function ChatInput({ onSend, disabled = false, SendIcon }) {
  const [value, setValue] = useState('')
  const textareaRef = useRef(null)
  const resizeTextarea = useAutoResize(textareaRef, 120)

  const resetHeight = useCallback(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }, [])

  const handleSubmit = useCallback(
    (event) => {
      event.preventDefault()
      const trimmed = value.trim()
      if (!trimmed || disabled) return

      onSend(trimmed)
      setValue('')
      resetHeight()

      // Return focus to textarea after sending
      requestAnimationFrame(() => textareaRef.current?.focus())
    },
    [value, disabled, onSend, resetHeight],
  )

  const handleKeyDown = useCallback(
    (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault()
        handleSubmit(event)
      }
    },
    [handleSubmit],
  )

  const handleChange = useCallback(
    (event) => {
      setValue(event.target.value)
      resizeTextarea(event)
    },
    [resizeTextarea],
  )

  const isActionDisabled = disabled || !value.trim()

  return (
    <form className="chat-input" onSubmit={handleSubmit} role="search">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? 'Assistant is thinking…' : 'Ask about any product...'}
        rows={1}
        disabled={disabled}
        aria-label="Chat message"
      />

      <button
        type="submit"
        disabled={isActionDisabled}
        aria-disabled={isActionDisabled}
        aria-label="Send message"
      >
        {SendIcon ? <SendIcon /> : 'Send'}
      </button>
    </form>
  )
}

export default memo(ChatInput)