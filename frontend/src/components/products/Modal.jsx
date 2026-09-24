import { useEffect, useRef } from 'react'
import { XIcon } from '../layout/Icons.jsx'

export default function Modal({ title, onClose, children, wide = false }) {
  const panel = useRef(null)

  useEffect(() => {
    const previous = document.activeElement
    panel.current?.focus()
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.classList.add('no-scroll')
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.classList.remove('no-scroll')
      previous?.focus?.()
    }
  }, [onClose])

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={panel}
        className={`modal${wide ? ' modal-wide' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
      >
        <div className="modal-head">
          <h2>{title}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            <XIcon />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}
