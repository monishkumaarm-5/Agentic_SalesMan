import { MoonIcon, PlusIcon, SunIcon } from './Icons.jsx'

export default function Header({ company, isDark, onToggleTheme, onNewChat, canReset }) {
  const name = company?.name || 'Shopping Assistant'
  return (
    <header className="header">
      <div className="brand">
        <div className="brand-mark" aria-hidden="true">{name.slice(0, 1).toUpperCase()}</div>
        <div className="brand-text">
          <h1>{name}</h1>
          <p>{company?.tagline || 'AI shopping assistant'}</p>
        </div>
      </div>
      <div className="header-actions">
        <button
          type="button"
          className="icon-btn"
          onClick={onToggleTheme}
          aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
          title={isDark ? 'Light theme' : 'Dark theme'}
        >
          {isDark ? <SunIcon /> : <MoonIcon />}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onNewChat} disabled={!canReset}>
          <PlusIcon /> New chat
        </button>
      </div>
    </header>
  )
}
