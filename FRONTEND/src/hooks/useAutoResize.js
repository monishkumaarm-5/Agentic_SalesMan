import { useCallback } from 'react'

/**
 * Returns an onChange helper that auto-resizes the event's <textarea> up
 * to `maxHeight`, after which it scrolls.
 *
 * Usage:
 *   const resize = useAutoResize(120)
 *   <textarea onChange={(e) => { setValue(e.target.value); resize(e) }} />
 *
 * @param {number} maxHeight  Maximum pixel height before scrolling kicks in
 * @returns {(e: React.ChangeEvent<HTMLTextAreaElement>) => void}
 */
export function useAutoResize(maxHeight = 120) {
  return useCallback(
    (event) => {
      const el = event.currentTarget ?? event.target
      if (!el) return
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
    },
    [maxHeight],
  )
}
