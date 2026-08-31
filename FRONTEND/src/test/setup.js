import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// jsdom doesn't implement scrollIntoView -- App.jsx calls it to keep the
// chat scrolled to the latest message. A no-op is all tests need.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

// Vitest doesn't auto-run React Testing Library's cleanup between tests
// unless `test.globals: true` is set (it isn't, deliberately, so test files
// import describe/it/expect explicitly) -- so do it here instead, once,
// for every test file.
afterEach(() => {
  cleanup()
})
