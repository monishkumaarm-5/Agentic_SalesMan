import { useCallback } from 'react'

/**
 * Returns an onChange handler that auto-resizes a <textarea> up to `maxHeight`.
 *
 * Usage:
 *   const handleChange = useAutoResize(textareaRef, 120)
 *   <textarea ref={textareaRef} onChange={handleChange} />
 *
 * @param {React.RefObject<HTMLTextAreaElement>} ref
 * @param {number} maxHeight  Maximum pixel height before scrolling kicks in
 * @returns {(e: React.ChangeEvent<HTMLTextAreaElement>) => void}
 */
export function useAutoResize(ref, maxHeight = 120) {
  return useCallback(
    (event) => {
      const el = ref.current ?? event.target
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
    },
    [ref, maxHeight],
  )
}