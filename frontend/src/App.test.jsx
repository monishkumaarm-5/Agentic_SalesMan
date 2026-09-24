import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { chatResponse } from './test/fixtures.js'

vi.mock('./api/client.js', () => ({
  streamChat: vi.fn(),
  getCompany: vi.fn().mockResolvedValue({ name: 'Trein', tagline: 'One store', cities: ['Chennai'] }),
  getCategories: vi.fn().mockResolvedValue([
    { name: 'Mobile', product_count: 8, min_price: 10000, max_price: 50000, brands: [] },
    { name: 'Laptop', product_count: 5, min_price: 30000, max_price: 90000, brands: [] },
  ]),
}))

import { streamChat } from './api/client.js'
import App from './App.jsx'

beforeEach(() => {
  streamChat.mockReset()
})

async function send(user, text) {
  await user.type(screen.getByRole('textbox', { name: 'Message' }), text)
  await user.keyboard('{Enter}')
}

describe('App', () => {
  it('welcomes with starters built from the live catalog', async () => {
    render(<App />)
    expect(await screen.findByRole('button', { name: 'Best mobile under ₹30k' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Laptop\s*5 products/ })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { level: 1, name: 'Trein' })).toBeInTheDocument()
  })

  it('shows live progress, then the answer with product cards, quick replies and profile', async () => {
    let finish
    streamChat.mockImplementation((_m, _t, { onStatus }) => {
      onStatus({ step: 'understand', label: 'Understanding what you need' })
      onStatus({ step: 'retrieve', label: 'Searching the catalog' })
      return new Promise((resolve) => { finish = resolve })
    })
    const user = userEvent.setup()
    render(<App />)
    await send(user, 'phone under 30k')

    expect(await screen.findByText('Searching the catalog…')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Stop generating' })).toBeInTheDocument()

    finish(chatResponse())
    expect(await screen.findByRole('heading', { name: 'Redmi Note 14' })).toBeInTheDocument()
    expect(screen.getByText(/is your best bet/)).toBeInTheDocument()
    expect(screen.getByText('Best match')).toBeInTheDocument()
    expect(screen.getByText('Under ₹30k')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Anything cheaper?' })).toBeInTheDocument()
  })

  it('sends a quick reply when clicked', async () => {
    streamChat.mockResolvedValue(chatResponse())
    const user = userEvent.setup()
    render(<App />)
    await send(user, 'phones')
    await user.click(await screen.findByRole('button', { name: 'Anything cheaper?' }))
    await waitFor(() => expect(streamChat).toHaveBeenCalledTimes(2))
    expect(streamChat.mock.calls[1][0]).toBe('Anything cheaper?')
    expect(streamChat.mock.calls[1][1]).toBe('thread-1') // continues the server's thread
  })

  it('compares selected products side by side', async () => {
    streamChat.mockResolvedValue(chatResponse())
    const user = userEvent.setup()
    render(<App />)
    await send(user, 'phones')
    const compareButtons = await screen.findAllByRole('button', { name: /Compare$/ })
    await user.click(compareButtons[0])
    await user.click(compareButtons[1])
    await user.click(screen.getByRole('button', { name: 'Compare 2' }))
    const dialog = screen.getByRole('dialog', { name: 'Compare products' })
    expect(within(dialog).getByText('₹18,999')).toHaveClass('tone-best')
  })

  it('opens product details', async () => {
    streamChat.mockResolvedValue(chatResponse())
    const user = userEvent.setup()
    render(<App />)
    await send(user, 'phones')
    await user.click((await screen.findAllByRole('button', { name: 'Details' }))[0])
    const dialog = screen.getByRole('dialog', { name: 'Redmi Note 14' })
    expect(within(dialog).getByText('Fits your budget with room to spare.')).toBeInTheDocument()
    expect(within(dialog).getByText('Near you')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows errors with a working retry', async () => {
    streamChat.mockRejectedValueOnce(new Error('Server is busy')).mockResolvedValueOnce(chatResponse())
    const user = userEvent.setup()
    render(<App />)
    await send(user, 'phones')
    await user.click(await screen.findByRole('button', { name: /Try again/ }))
    expect(await screen.findByRole('heading', { name: 'Redmi Note 14' })).toBeInTheDocument()
    expect(screen.queryByText('Server is busy')).not.toBeInTheDocument()
    expect(screen.getAllByText('phones')).toHaveLength(1)
  })

  it('persists the conversation and starts over on New chat', async () => {
    streamChat.mockResolvedValue(chatResponse({ answer: 'Saved answer', recommendations: [] }))
    const user = userEvent.setup()
    const { unmount } = render(<App />)
    await send(user, 'phones')
    await screen.findByText('Saved answer')
    unmount()

    render(<App />)
    expect(screen.getByText('Saved answer')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /New chat/ }))
    expect(screen.queryByText('Saved answer')).not.toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Best mobile under ₹30k' })).toBeInTheDocument()
  })
})
