import { useCallback, useState } from 'react'

function read(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

/** useState that mirrors its value into localStorage (best effort). */
export function useLocalStorage(key, fallback) {
  const [value, setValue] = useState(() => read(key, fallback))

  const set = useCallback(
    (next) => {
      setValue((prev) => {
        const resolved = typeof next === 'function' ? next(prev) : next
        try {
          if (resolved === undefined) localStorage.removeItem(key)
          else localStorage.setItem(key, JSON.stringify(resolved))
        } catch {
          // storage full or unavailable -- keep working in memory
        }
        return resolved
      })
    },
    [key],
  )

  return [value, set]
}
