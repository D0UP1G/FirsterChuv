import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, resetCsrfToken } from './client'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

function emptyResponse(status: number): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers(),
    json: vi.fn(),
  } as unknown as Response
}

describe('auth API client', () => {
  beforeEach(() => {
    resetCsrfToken()
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    resetCsrfToken()
    vi.unstubAllGlobals()
  })

  it('sends credentials and CSRF, then uses the rotated token for logout', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'csrf-before-login' }))
      .mockResolvedValueOnce(jsonResponse({
        id: 'user-1',
        displayName: 'Участник',
        role: 'participant',
        csrfToken: 'csrf-after-login',
      }))
      .mockResolvedValueOnce(emptyResponse(204))

    const user = await api.login({ email: 'player@example.test', password: 'secret-example' })
    await api.logout()

    expect(user).toEqual({ id: 'user-1', displayName: 'Участник', role: 'participant' })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    const [csrfUrl, csrfInit] = fetchMock.mock.calls[0]
    expect(csrfUrl).toBe('/api/v1/auth/csrf')
    expect(csrfInit?.credentials).toBe('include')
    expect(csrfInit?.cache).toBe('no-store')

    const [, loginInit] = fetchMock.mock.calls[1]
    expect(loginInit?.method).toBe('POST')
    expect(new Headers(loginInit?.headers).get('X-CSRFToken')).toBe('csrf-before-login')
    expect(JSON.parse(String(loginInit?.body))).toEqual({ email: 'player@example.test', password: 'secret-example' })

    const [, logoutInit] = fetchMock.mock.calls[2]
    expect(logoutInit?.method).toBe('POST')
    expect(new Headers(logoutInit?.headers).get('X-CSRFToken')).toBe('csrf-after-login')
  })

  it('registers without sending a client-selected role', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'csrf-register' }))
      .mockResolvedValueOnce(jsonResponse({ id: 'user-2', displayName: 'Новый игрок', role: 'participant' }, 201))

    const user = await api.register({
      displayName: 'Новый игрок',
      email: 'new@example.test',
      password: 'secret-example',
    })

    expect(user.role).toBe('participant')
    const [, requestInit] = fetchMock.mock.calls[1]
    expect(new Headers(requestInit?.headers).get('X-CSRFToken')).toBe('csrf-register')
    expect(JSON.parse(String(requestInit?.body))).toEqual({
      displayName: 'Новый игрок',
      email: 'new@example.test',
      password: 'secret-example',
    })
  })

  it('preserves the API error envelope and field details', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({
      error: { code: 'not_authenticated', message: 'Требуется вход.', fields: null },
      requestId: 'req-1',
    }, 401))

    await expect(api.me()).rejects.toMatchObject({
      status: 401,
      code: 'not_authenticated',
      requestId: 'req-1',
      message: 'Требуется вход.',
    } satisfies Partial<ApiError>)
  })
})
