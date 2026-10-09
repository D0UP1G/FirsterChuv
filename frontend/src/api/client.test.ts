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

  it('creates and accepts real v1 invitations with CSRF and same-origin paths', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'csrf-admin' }))
      .mockResolvedValueOnce(jsonResponse({
        invite: { id: 'invite-1', tournamentId: 'tournament-1', expiresAt: null, maxUses: 2, uses: 0, revokedAt: null },
        token: 'synthetic-token-for-test',
        url: '/invites/synthetic-token-for-test',
      }, 201))
      .mockResolvedValueOnce(jsonResponse({
        tournament: { id: 'tournament-1', title: 'Тестовый турнир' },
        valid: true,
        expiresAt: null,
      }))
      .mockResolvedValueOnce(jsonResponse({ tournamentId: 'tournament-1', userId: 'player-1', joined: true }))

    const created = await api.createInvite('tournament-1', { maxUses: 2 })
    const preview = await api.previewInvite(created.token)
    const accepted = await api.acceptInvite(created.token)

    expect(created.url).toBe('/invites/synthetic-token-for-test')
    expect(preview.tournament.title).toBe('Тестовый турнир')
    expect(accepted.joined).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(4)

    const [createUrl, createInit] = fetchMock.mock.calls[1]
    expect(createUrl).toBe('/api/v1/tournaments/tournament-1/invites')
    expect(createInit?.method).toBe('POST')
    expect(new Headers(createInit?.headers).get('X-CSRFToken')).toBe('csrf-admin')
    expect(JSON.parse(String(createInit?.body))).toEqual({ maxUses: 2 })

    const [previewUrl, previewInit] = fetchMock.mock.calls[2]
    expect(previewUrl).toBe('/api/v1/invites/synthetic-token-for-test')
    expect(previewInit?.credentials).toBe('include')
    expect(previewInit?.cache).toBe('no-store')

    const [acceptUrl, acceptInit] = fetchMock.mock.calls[3]
    expect(acceptUrl).toBe('/api/v1/invites/synthetic-token-for-test/accept')
    expect(acceptInit?.method).toBe('POST')
    expect(new Headers(acceptInit?.headers).get('X-CSRFToken')).toBe('csrf-admin')
    expect(acceptInit?.body).toBeUndefined()
  })
})
