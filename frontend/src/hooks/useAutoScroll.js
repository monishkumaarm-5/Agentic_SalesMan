import { useEffect, useRef } from 'react'

/** Keeps a scroll container pinned to the bottom when content grows,
 *  unless the user has scrolled up to read something. */
export function useAutoScroll(deps) {
  const ref = useRef(null)
  const pinned = useRef(true)

  useEffect(() => {
    const el = ref.current
    if (!el) return undefined
    const onScroll = () => {
      pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    const el = ref.current
    if (el && pinned.current) el.scrollTo?.({ top: el.scrollHeight, behavior: 'smooth' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return ref
}
