import { useRef, useState } from 'react'
import { SendIcon, StopIcon } from '../layout/Icons.jsx'

export default function Composer({ onSend, onStop, isSending, placeholder }) {
  const [value, setValue] = useState('')
  const ref = useRef(null)

  const resize = (el) => {
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  const submit = (event) => {
    event?.preventDefault()
    const text = value.trim()
    if (!text || isSending) return
    onSend(text)
    setValue('')
    if (ref.current) ref.current.style.height = 'auto'
  }

  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        ref={ref}
        rows={1}
        value={value}
        placeholder={placeholder || 'Ask about any product…'}
        aria-label="Message"
        maxLength={4000}
        onChange={(e) => {
          setValue(e.target.value)
          resize(e.currentTarget)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) submit(e)
        }}
      />
      {isSending ? (
        <button type="button" className="send-btn stop" onClick={onStop} aria-label="Stop generating">
          <StopIcon />
        </button>
      ) : (
        <button type="submit" className="send-btn" disabled={!value.trim()} aria-label="Send message">
          <SendIcon />
        </button>
      )}
    </form>
  )
}
