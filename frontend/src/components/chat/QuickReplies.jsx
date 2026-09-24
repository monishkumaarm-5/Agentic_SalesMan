export default function QuickReplies({ items, onSend, disabled }) {
  if (!items?.length) return null
  return (
    <div className="quick-replies" role="group" aria-label="Suggested replies">
      {items.map((text) => (
        <button key={text} type="button" className="chip chip-action" onClick={() => onSend(text)} disabled={disabled}>
          {text}
        </button>
      ))}
    </div>
  )
}
