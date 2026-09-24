/**
 * Spec-quality evaluation rules.
 * Centralised so TopPicks and any future component share the same logic.
 */

export const SPEC_LABELS = Object.freeze({
  brand: 'Brand',
  processor: 'Processor',
  ram: 'RAM',
  storage: 'Storage',
  color: 'Color',
  type: 'Type',
  quality: 'Sound quality',
  capacity: 'Capacity',
  star_rating: 'Energy rating',
  screen_size: 'Screen size',
  resolution: 'Resolution',
  display: 'Display',
  battery: 'Battery',
  battery_life: 'Battery life',
  camera: 'Camera',
  connectivity: 'Connectivity',
  power: 'Power',
  speed_settings: 'Speed settings',
  spin_speed: 'Spin speed',
  jars: 'Jars',
  defrost: 'Defrost',
  inverter: 'Inverter',
  smart_features: 'Smart features',
  noise_cancellation: 'Noise cancellation',
  water_resistance: 'Water resistance',
})

/* ── helper parsers ────────────────────────────────────── */

function parseFirstInt(v) {
  if (v == null) return null
  const m = String(v).match(/(\d+)/)
  return m ? parseInt(m[1], 10) : null
}

function parseFirstFloat(v) {
  if (v == null) return null
  const m = String(v).match(/(\d+\.?\d*)/)
  return m ? parseFloat(m[1]) : null
}

function lowerStr(v) {
  return v != null ? String(v).toLowerCase() : ''
}

/* ── rules ─────────────────────────────────────────────── */

export const SPEC_QUALITY_RULES = Object.freeze({
  ram: {
    parse: parseFirstInt,
    good: (n) => n >= 8,
    bad: (n) => n <= 4,
    goodLabel: '8 GB+ is great for multitasking',
    badLabel: '4 GB or less may feel sluggish',
  },
  storage: {
    parse(v) {
      if (v == null) return null
      const s = String(v).toLowerCase()
      const m = s.match(/(\d+)/)
      if (!m) return null
      let n = parseInt(m[1], 10)
      if (s.includes('tb')) n *= 1024
      return n
    },
    good: (n) => n >= 256,
    bad: (n) => n <= 64,
    goodLabel: '256 GB+ gives plenty of room',
    badLabel: '64 GB or less fills up fast',
  },
  battery: {
    parse: parseFirstInt,
    good: (n) => n >= 5000,
    bad: (n) => n < 4000,
    goodLabel: '5000 mAh+ lasts all day',
    badLabel: 'Under 4000 mAh may need midday charging',
  },
  battery_life: {
    parse: parseFirstInt,
    good: (n) => n >= 8,
    bad: (n) => n < 5,
    goodLabel: '8+ hours is excellent',
    badLabel: 'Under 5 hours is short',
  },
  rating: {
    parse(v) {
      const n = parseFloat(v)
      return Number.isNaN(n) ? null : n
    },
    good: (n) => n >= 4.3,
    bad: (n) => n < 3.5,
    goodLabel: 'Highly rated by buyers',
    badLabel: 'Below-average user rating',
  },
  star_rating: {
    parse: parseFirstInt,
    good: (n) => n >= 4,
    bad: (n) => n <= 2,
    goodLabel: '4+ star energy rating saves power',
    badLabel: '2 star or less — higher running cost',
  },
  noise_cancellation: {
    parse: lowerStr,
    good: (s) => s.includes('yes') || s.includes('active') || s.includes('anc'),
    bad: (s) => s.includes('no') || s === 'none',
    goodLabel: 'Active noise cancellation included',
    badLabel: 'No noise cancellation',
  },
  water_resistance: {
    parse: lowerStr,
    good: (s) => s.includes('yes') || s.includes('ip6') || s.includes('ip5') || s.includes('ipx'),
    bad: (s) => s.includes('no') || s === 'none',
    goodLabel: 'Water/dust resistant',
    badLabel: 'Not water resistant',
  },
  inverter: {
    parse: lowerStr,
    good: (s) => s.includes('yes') || s.includes('inverter') || s.includes('digital'),
    bad: (s) => s.includes('no') || s === 'none',
    goodLabel: 'Inverter compressor — efficient & quiet',
    badLabel: 'Non-inverter — higher power use',
  },
  capacity: {
    parse: parseFirstInt,
    good: (n) => n >= 250,
    bad: (n) => n < 180,
    goodLabel: '250 L+ suits a family well',
    badLabel: 'Under 180 L may be tight for a family',
  },
  screen_size: {
    parse: parseFirstFloat,
    good: (n) => n >= 15,
    bad: (n) => n < 13,
    goodLabel: 'Large screen for productivity',
    badLabel: 'Compact screen — less workspace',
  },
  resolution: {
    parse(v) {
      if (v == null) return null
      const s = String(v).toLowerCase()
      if (s.includes('4k') || s.includes('2160') || s.includes('uhd')) return 4
      if (s.includes('2k') || s.includes('1440') || s.includes('qhd')) return 3
      if (s.includes('1080') || s.includes('fhd') || s.includes('full hd')) return 2
      if (s.includes('720') || s.includes('hd')) return 1
      return null
    },
    good: (n) => n >= 2,
    bad: (n) => n <= 1,
    goodLabel: 'Full HD or better — sharp visuals',
    badLabel: 'HD only — may look soft on large screens',
  },
})

/**
 * Evaluate a single spec against quality rules.
 * @param {string} key   Spec key (e.g. 'ram')
 * @param {*}      value Raw spec value
 * @returns {{ quality: 'good'|'bad'|'neutral', tip: string|null }}
 */
export function evaluateSpec(key, value) {
  const rule = SPEC_QUALITY_RULES[key]
  if (!rule) return { quality: 'neutral', tip: null }
  const parsed = rule.parse(value)
  if (parsed == null) return { quality: 'neutral', tip: null }
  if (rule.good(parsed)) return { quality: 'good', tip: rule.goodLabel }
  if (rule.bad(parsed)) return { quality: 'bad', tip: rule.badLabel }
  return { quality: 'neutral', tip: null }
}