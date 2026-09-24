import { useEffect } from 'react'
import { useLocalStorage } from './useLocalStorage.js'

/** 'light' | 'dark' | 'system', applied as <html data-theme>. */
export function useTheme() {
  const [theme, setTheme] = useLocalStorage('salesman:theme', 'system')

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
  }, [theme])

  const isDark =
    theme === 'dark' ||
    (theme === 'system' && typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches)

  return { theme, isDark, toggle: () => setTheme(isDark ? 'light' : 'dark') }
}
