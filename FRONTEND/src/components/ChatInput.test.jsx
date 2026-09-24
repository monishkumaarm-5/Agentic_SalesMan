import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ChatInput from './ChatInput.jsx'

describe('ChatInput', () => {
  it('submits the trimmed message on Enter and clears the box', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled={false} />)

    const textarea = screen.getByPlaceholderText(/ask about/i)
    await user.type(textarea, '  recommend a phone  ')
    await user.keyboard('{Enter}')

    expect(onSend).toHaveBeenCalledWith('recommend a phone')
    expect(textarea).toHaveValue('')
  })

  it('does not submit on Shift+Enter (newline instead)', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled={false} />)

    const textarea = screen.getByPlaceholderText(/ask about/i)
    await user.type(textarea, 'line one')
    await user.keyboard('{Shift>}{Enter}{/Shift}')

    expect(onSend).not.toHaveBeenCalled()
  })

  it('does not submit an empty/whitespace-only message', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatInput onSend={onSend} disabled={false} />)

    await user.type(screen.getByPlaceholderText(/ask about/i), '   ')
    await user.keyboard('{Enter}')

    expect(onSend).not.toHaveBeenCalled()
  })

  it('disables the textarea and button while disabled=true', () => {
    render(<ChatInput onSend={vi.fn()} disabled />)
    expect(screen.getByRole('textbox', { name: /chat message/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /send/i })).toBeDisabled()
  })
})
