import { memo } from 'react'

/**
 * Inline SVG logo with emerald/champagne gradient.
 * Pure presentational — wrapped in React.memo.
 */
function Logo({ size = 42 }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 32 32"
      width={size}
      height={size}
      role="img"
      aria-label="Chat logo"
    >
      <defs>
        <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#6ee7b7" />
          <stop offset="45%" stopColor="#10b981" />
          <stop offset="100%" stopColor="#065f46" />
        </linearGradient>

        <linearGradient id="champagne" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#fff5db" />
          <stop offset="55%" stopColor="#f0d9a0" />
          <stop offset="100%" stopColor="#c9a266" />
        </linearGradient>

        <linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.40" />
          <stop offset="55%" stopColor="#ffffff" stopOpacity="0.06" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
        </linearGradient>

        <linearGradient id="caseTop" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.26" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0.08" />
        </linearGradient>

        <linearGradient id="caseBody" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0.02" />
        </linearGradient>

        <linearGradient id="handleGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.55" />
          <stop offset="50%" stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0.55" />
        </linearGradient>

        <linearGradient id="borderGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.60" />
          <stop offset="100%" stopColor="#ffffff" stopOpacity="0.10" />
        </linearGradient>

        <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="0.9" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        <clipPath id="tileClip">
          <rect x="0" y="0" width="32" height="32" rx="8" ry="8" />
        </clipPath>
      </defs>

      <g clipPath="url(#tileClip)">
        <rect x="0" y="0" width="32" height="32" fill="url(#bgGrad)" />
        <circle cx="6" cy="6" r="14" fill="#a7f3d0" opacity="0.45" style={{ filter: 'blur(6px)' }} />
        <circle cx="28" cy="28" r="12" fill="#f0d9a0" opacity="0.28" style={{ filter: 'blur(7px)' }} />
        <circle cx="26" cy="6" r="7" fill="#5eead4" opacity="0.22" style={{ filter: 'blur(5px)' }} />
        <rect x="0" y="0" width="32" height="18" fill="url(#sheen)" />
        <path d="M -4 14 L 36 0 L 36 6 L -4 20 Z" fill="#ffffff" opacity="0.07" />
      </g>

      <path
        d="M10 10.5 L7.5 13.5 V23.5 a2.2 2.2 0 0 0 2.2 2.2 h12.6 a2.2 2.2 0 0 0 2.2 -2.2 V13.5 L22 10.5 Z"
        fill="url(#caseBody)" stroke="url(#borderGrad)"
        strokeWidth="0.9" strokeLinejoin="round" strokeLinecap="round"
      />

      <path
        d="M10 10.5 L7.5 13.5 H24.5 L22 10.5 Z"
        fill="url(#caseTop)" stroke="url(#borderGrad)"
        strokeWidth="0.7" strokeLinejoin="round"
      />

      <path
        d="M13 10.5 V9.6 a1.6 1.6 0 0 1 1.6 -1.6 h2.8 a1.6 1.6 0 0 1 1.6 1.6 V10.5"
        fill="none" stroke="url(#handleGrad)"
        strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"
      />

      <line x1="7.5" y1="13.5" x2="24.5" y2="13.5" stroke="#ffffff" strokeOpacity="0.72" strokeWidth="0.9" strokeLinecap="round" />
      <line x1="8.2" y1="12.9" x2="23.8" y2="12.9" stroke="#ffffff" strokeOpacity="0.22" strokeWidth="0.6" strokeLinecap="round" />

      <rect x="14.6" y="12.6" width="2.8" height="1.8" rx="0.55" ry="0.55" fill="url(#champagne)" stroke="#ffffff" strokeOpacity="0.40" strokeWidth="0.4" />
      <circle cx="15.2" cy="13.3" r="0.35" fill="#ffffff" fillOpacity="0.9" />

      <path
        d="M14 18.2 a2.4 2.4 0 0 0 4 0"
        fill="none" stroke="url(#champagne)"
        strokeWidth="1.4" strokeLinecap="round" filter="url(#glow)"
      />

      <path d="M2.5 8 a6 6 0 0 1 5 -5.5" fill="none" stroke="#a7f3d0" strokeOpacity="0.60" strokeWidth="0.9" strokeLinecap="round" />
      <path d="M29.5 24 a6 6 0 0 1 -5 5.5" fill="none" stroke="#f0d9a0" strokeOpacity="0.30" strokeWidth="0.8" strokeLinecap="round" />
    </svg>
  )
}

export default memo(Logo)