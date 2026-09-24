import { useState, useCallback } from 'react'

/**
 * Persist state in localStorage with automatic JSON serialisation.
 *
 * Falls back gracefully when storage is unavailable (private browsing,
 * quota exceeded, etc.).
 *
 * @template T
 * @param {string}  key           localStorage key
 * @param {T}       initialValue  default when nothing is stored
 * @returns {[T, (value: T | ((prev: T) => T)) => void, () => void]}
 */
export function useLocalStorage(key, initialValue) {
  const [storedValue, setStoredValue] = useState(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw ? JSON.parse(raw) : initialValue
    } catch {
      return initialValue
    }
  })

  const setValue = useCallback(
    (value) => {
      setStoredValue((prev) => {
        const next = typeof value === 'function' ? value(prev) : value
        try {
          localStorage.setItem(key, JSON.stringify(next))
        } catch {
          // storage full or disabled — state still updates in memory
        }
        return next
      })
    },
    [key],
  )

  const removeValue = useCallback(() => {
    try {
      localStorage.removeItem(key)
    } catch {
      // ignore
    }
    setStoredValue(initialValue)
  }, [key, initialValue])

  return [storedValue, setValue, removeValue]
}