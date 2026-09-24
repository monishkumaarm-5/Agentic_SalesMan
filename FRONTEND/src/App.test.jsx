import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('./api.js', () => ({
  sendMessage: vi.fn(),
  getCompanyInfo: vi.fn().mockResolvedValue(null),
}))

import { sendMessage } from './api.js'
import App from './App.jsx'

beforeEach(() => {
  localStorage.clear()
  sendMessage.mockReset()
})

afterEach(() => {
  localStorage.clear()
})

describe('App', () => {
  it('shows the welcome message on first load', () => {
    render(<App />)
    expect(screen.getByText(/Trein shopping assistant/i)).toBeInTheDocument()
  })

  it('sends a message and renders the assistant reply', async () => {
    sendMessage.mockResolvedValue({
      answer: 'Here is a great phone',
      context: 'MOBILE',
      thread_id: 'thread-1',
      product: null,
    })
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByPlaceholderText(/ask about/i), 'recommend a phone')
    await user.keyboard('{Enter}')

    expect(await screen.findByText('Here is a great phone')).toBeInTheDocument()
    expect(screen.getByText('recommend a phone')).toBeInTheDocument()
  })

  it('shows an error bubble when the backend call fails', async () => {
    sendMessage.mockRejectedValue(new Error('backend is down'))
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByPlaceholderText(/ask about/i), 'recommend a phone')
    await user.keyboard('{Enter}')

    expect(await screen.findByText(/backend is down/i)).toBeInTheDocument()
  })

  it('persists messages to localStorage and restores them on remount', async () => {
    sendMessage.mockResolvedValue({
      answer: 'Here is a great phone',
      context: 'MOBILE',
      thread_id: 'thread-1',
      product: null,
    })
    const user = userEvent.setup()
    const { unmount } = render(<App />)

    await user.type(screen.getByPlaceholderText(/ask about/i), 'recommend a phone')
    await user.keyboard('{Enter}')
    await screen.findByText('Here is a great phone')

    unmount()

    render(<App />)
    expect(screen.getByText('recommend a phone')).toBeInTheDocument()
    expect(screen.getByText('Here is a great phone')).toBeInTheDocument()
  })

  it('clears history and starts a new thread on "New conversation"', async () => {
    sendMessage.mockResolvedValue({
      answer: 'Here is a great phone',
      context: 'MOBILE',
      thread_id: 'thread-1',
      product: null,
    })
    const user = userEvent.setup()
    render(<App />)

    await user.type(screen.getByPlaceholderText(/ask about/i), 'recommend a phone')
    await user.keyboard('{Enter}')
    await screen.findByText('Here is a great phone')

    await user.click(screen.getByRole('button', { name: /new conversation/i }))

    expect(screen.queryByText('recommend a phone')).not.toBeInTheDocument()
    await waitFor(() => {
      expect(localStorage.getItem('agentic-salesman:chat-v1')).not.toContain('recommend a phone')
    })
  })
})
