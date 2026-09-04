import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AuthPanel from './AuthPanel.jsx'
import * as api from '../api.js'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AuthPanel', () => {
  it('logs in with the entered credentials and reports the session up', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'login').mockResolvedValue({
      token: 'tok123',
      user: { email: 'a@example.com', role: 'user' },
    })
    const onAuthenticated = vi.fn()

    render(<AuthPanel onAuthenticated={onAuthenticated} />)

    await user.type(screen.getByLabelText('Email'), 'a@example.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    await waitFor(() => {
      expect(api.login).toHaveBeenCalledWith('a@example.com', 'password123')
    })
    expect(onAuthenticated).toHaveBeenCalledWith('tok123', { email: 'a@example.com', role: 'user' })
  })

  it('shows the server error message and does not report a session on failure', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'login').mockRejectedValue(Object.assign(new Error('Invalid email or password.')))
    const onAuthenticated = vi.fn()

    render(<AuthPanel onAuthenticated={onAuthenticated} />)

    await user.type(screen.getByLabelText('Email'), 'a@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrongpass')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.')
    expect(onAuthenticated).not.toHaveBeenCalled()
  })

  it('switches to the register form and calls register instead of login', async () => {
    const user = userEvent.setup()
    vi.spyOn(api, 'register').mockResolvedValue({
      token: 'tok456',
      user: { email: 'new@example.com', role: 'user' },
    })
    const onAuthenticated = vi.fn()

    render(<AuthPanel onAuthenticated={onAuthenticated} />)

    await user.click(screen.getByText('Need an account? Create one'))
    expect(screen.getByRole('heading', { name: 'Create an account' })).toBeInTheDocument()

    await user.type(screen.getByLabelText('Email'), 'new@example.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    await waitFor(() => {
      expect(api.register).toHaveBeenCalledWith('new@example.com', 'password123')
    })
    expect(onAuthenticated).toHaveBeenCalledWith('tok456', {
      email: 'new@example.com',
      role: 'user',
    })
  })
})
