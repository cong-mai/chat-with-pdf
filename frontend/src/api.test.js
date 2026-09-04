import { afterEach, describe, expect, it, vi } from 'vitest'
import { askQuestion, deleteDocument, fetchMe, login, register } from './api.js'

function mockFetchOnce(body, { ok = true, status = 200 } = {}) {
  global.fetch = vi.fn().mockResolvedValue({
    ok,
    status,
    json: () => Promise.resolve(body),
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('login', () => {
  it('posts credentials as JSON and returns the parsed body', async () => {
    mockFetchOnce({ token: 'abc', user: { email: 'a@example.com', role: 'user' } })

    const data = await login('a@example.com', 'password123')

    expect(fetch).toHaveBeenCalledWith(
      '/api/auth/login',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'a@example.com', password: 'password123' }),
      }),
    )
    expect(data.token).toBe('abc')
  })

  it('throws an Error carrying the server message and status on failure', async () => {
    mockFetchOnce({ error: 'Invalid email or password.' }, { ok: false, status: 400 })

    await expect(register('a@example.com', 'bad')).rejects.toMatchObject({
      message: 'Invalid email or password.',
      status: 400,
    })
  })
})

describe('fetchMe', () => {
  it('sends a bearer Authorization header when a token is given', async () => {
    mockFetchOnce({ user: { email: 'a@example.com', role: 'user' } })

    await fetchMe('my-token')

    expect(fetch).toHaveBeenCalledWith(
      '/api/auth/me',
      expect.objectContaining({ headers: { Authorization: 'Bearer my-token' } }),
    )
  })

  it('sends no Authorization header when no token is given', async () => {
    mockFetchOnce({ user: null })

    await fetchMe(undefined)

    expect(fetch).toHaveBeenCalledWith('/api/auth/me', expect.objectContaining({ headers: {} }))
  })
})

describe('askQuestion', () => {
  it('sends the file id and message as JSON with auth', async () => {
    mockFetchOnce({ answer: 'The sky is blue.', sources: [] })

    await askQuestion('file123', 'What color is the sky?', 'tok')

    expect(fetch).toHaveBeenCalledWith(
      '/api/chat',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: 'Bearer tok' },
        body: JSON.stringify({ file_id: 'file123', message: 'What color is the sky?' }),
      }),
    )
  })
})

describe('deleteDocument', () => {
  it('sends a DELETE to the document-specific URL', async () => {
    mockFetchOnce({ deleted: 'file123' })

    await deleteDocument('file123', 'tok')

    expect(fetch).toHaveBeenCalledWith(
      '/api/documents/file123',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })
})

describe('error parsing', () => {
  it('falls back to a generic message when the error body has no error field', async () => {
    mockFetchOnce({}, { ok: false, status: 500 })

    await expect(login('a@example.com', 'x')).rejects.toMatchObject({
      message: 'Something went wrong.',
      status: 500,
    })
  })

  it('falls back to a generic message when the response body is not JSON', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new Error('not json')),
    })

    await expect(login('a@example.com', 'x')).rejects.toMatchObject({
      message: 'Something went wrong.',
      status: 500,
    })
  })
})
