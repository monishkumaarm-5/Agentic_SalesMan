import { CheckIcon } from '../layout/Icons.jsx'

export default function StatusIndicator({ steps }) {
  const current = steps.at(-1)
  return (
    <div className="message assistant" aria-live="polite">
      <div className="avatar" aria-hidden="true">AI</div>
      <div className="status-card">
        <div className="status-current">
          <span className="typing" aria-hidden="true"><i /><i /><i /></span>
          <span>{current ? `${current.label}…` : 'Thinking…'}</span>
        </div>
        {steps.length > 1 && (
          <ol className="status-steps">
            {steps.slice(0, -1).map((s) => (
              <li key={s.step}><CheckIcon width={14} height={14} /> {s.label}</li>
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}
