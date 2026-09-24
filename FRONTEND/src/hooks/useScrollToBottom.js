import { useEffect, useRef } from 'react'

/**
 * Returns a ref to attach to a sentinel element at the bottom of a
 * scrollable container. Scrolls into view whenever any dependency changes.
 *
 * @param {any[]} deps  Values that trigger a scroll when they change
 * @returns {React.RefObject<HTMLElement>}
 */
export function useScrollToBottom(deps) {
  const ref = useRef(null)

  useEffect(() => {
    ref.current?.scrollIntoView({ behavior: 'smooth' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return ref
}