/* Small inline icon set (stroke icons, 24px grid). */
const base = {
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
  focusable: false,
}

function Svg({ children, ...props }) {
  return <svg {...base} {...props}>{children}</svg>
}

export function SendIcon(props) {
  return <Svg {...props}><><path d="M22 2 11 13" /><path d="M22 2 15 22l-4-9-9-4z" /></></Svg>
}
export function StopIcon(props) {
  return <Svg {...props}><rect x="6" y="6" width="12" height="12" rx="2" /></Svg>
}
export function PlusIcon(props) {
  return <Svg {...props}><><path d="M12 5v14" /><path d="M5 12h14" /></></Svg>
}
export function SunIcon(props) {
  return <Svg {...props}><><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></></Svg>
}
export function MoonIcon(props) {
  return <Svg {...props}><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></Svg>
}
export function CheckIcon(props) {
  return <Svg {...props}><path d="M20 6 9 17l-5-5" /></Svg>
}
export function XIcon(props) {
  return <Svg {...props}><><path d="M18 6 6 18" /><path d="m6 6 12 12" /></></Svg>
}
export function StarIcon(props) {
  return <Svg {...props}><path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z" /></Svg>
}
export function MapPinIcon(props) {
  return <Svg {...props}><><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 0 1 16 0z" /><circle cx="12" cy="10" r="3" /></></Svg>
}
export function ExternalIcon(props) {
  return <Svg {...props}><><path d="M15 3h6v6" /><path d="M10 14 21 3" /><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /></></Svg>
}
export function CompareIcon(props) {
  return <Svg {...props}><><path d="M9 3v18" /><path d="M15 3v18" /><rect x="3" y="3" width="18" height="18" rx="2" /></></Svg>
}
export function RefreshIcon(props) {
  return <Svg {...props}><><path d="M21 12a9 9 0 1 1-3-6.7L21 8" /><path d="M21 3v5h-5" /></></Svg>
}
export function SparkIcon(props) {
  return <Svg {...props}><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" /></Svg>
}
export function BagIcon(props) {
  return <Svg {...props}><><path d="M6 7h12l-1 13H7z" /><path d="M9 7a3 3 0 0 1 6 0" /></></Svg>
}
