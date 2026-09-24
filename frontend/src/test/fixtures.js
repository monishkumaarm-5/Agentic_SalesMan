export const card = (overrides = {}) => ({
  rank: 1,
  name: 'Redmi Note 14',
  brand: 'Xiaomi',
  category: 'Mobile',
  price: 18999,
  mrp: 21999,
  discount_percent: 14,
  currency: 'INR',
  rating: 4.1,
  units_available: 55,
  in_stock: true,
  online_link: 'https://shop.example/redmi',
  stores: [{ name: 'Trein T Nagar', city: 'Chennai', address: '123 Usman Road', nearby: true, maps_url: 'https://maps' }],
  description: 'Fast charging and AMOLED',
  specs: [
    { key: 'ram', label: 'RAM', value: '8GB' },
    { key: 'storage', label: 'Storage', value: '256GB' },
  ],
  headline: 'Best value AMOLED phone',
  why: 'Fits your budget with room to spare.',
  key_features: ['AMOLED display'],
  fit_reasons: ['Within your ₹30,000 budget'],
  match: { overall: 0.82, components: { relevance: 0.9, budget: 1 } },
  ...overrides,
})

export const chatResponse = (overrides = {}) => ({
  thread_id: 'thread-1',
  answer: 'The **Redmi Note 14** is your best bet.',
  response_type: 'recommendation',
  recommendations: [
    {
      category: 'Mobile',
      picks: [
        card(),
        card({ name: 'Galaxy M35 5G', brand: 'Samsung', price: 21999, rating: 4.3, specs: [
          { key: 'ram', label: 'RAM', value: '8GB' },
          { key: 'storage', label: 'Storage', value: '128GB' },
        ], match: { overall: 0.7, components: {} } }),
      ],
    },
  ],
  products: [],
  comparison: [],
  suggestions: ['Compare the top two', 'Anything cheaper?'],
  profile: { categories: ['Mobile'], budget_max: 30000 },
  confidence: 0.82,
  ...overrides,
})
