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

  it('sends bracket and match commands as CSRF-protected idempotent v1 requests', async () => {
    const fetchMock = vi.mocked(fetch)
    const bracket = { tournamentId: 'tournament-1', bracketSize: 2, rosterFrozenAt: '2026-10-09T17:00:00Z', matches: [] }
    const match = { matchId: 'match-1', status: 'READY' }
    fetchMock
      .mockResolvedValueOnce(jsonResponse(bracket))
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'csrf-match' }))
      .mockResolvedValueOnce(jsonResponse(bracket))
      .mockResolvedValueOnce(jsonResponse(bracket))
      .mockResolvedValueOnce(jsonResponse(match))
      .mockResolvedValueOnce(jsonResponse(match))
      .mockResolvedValueOnce(jsonResponse(match))

    await api.bracket('tournament-1')
    await api.generateBracket('tournament-1', 'command-generate-1')
    await api.saveFirstRoundPairings('tournament-1', [{ position: 0, leftUserId: 'player-1', rightUserId: 'player-2' }], 'Ручная жеребьёвка', 'command-pairs-1')
    await api.match('match-1')
    await api.readyMatch('match-1', 'command-ready-1')
    await api.matchAction('match-1', { name: 'pause', reason: 'Технический перерыв' }, 'command-pause-1')

    expect(fetchMock).toHaveBeenCalledTimes(7)
    const [generateUrl, generateInit] = fetchMock.mock.calls[2]
    expect(generateUrl).toBe('/api/v1/tournaments/tournament-1/bracket/generate')
    expect(generateInit?.method).toBe('POST')
    expect(new Headers(generateInit?.headers).get('X-CSRFToken')).toBe('csrf-match')
    expect(new Headers(generateInit?.headers).get('Idempotency-Key')).toBe('command-generate-1')
    expect(JSON.parse(String(generateInit?.body))).toEqual({ seedingMode: 'manual' })

    const [pairingsUrl, pairingsInit] = fetchMock.mock.calls[3]
    expect(pairingsUrl).toBe('/api/v1/tournaments/tournament-1/bracket/pairings')
    expect(pairingsInit?.method).toBe('PUT')
    expect(new Headers(pairingsInit?.headers).get('Idempotency-Key')).toBe('command-pairs-1')
    expect(JSON.parse(String(pairingsInit?.body))).toEqual({
      pairings: [{ position: 0, leftUserId: 'player-1', rightUserId: 'player-2' }],
      reason: 'Ручная жеребьёвка',
    })

    const [, readyInit] = fetchMock.mock.calls[5]
    expect(new Headers(readyInit?.headers).get('Idempotency-Key')).toBe('command-ready-1')
    const [pauseUrl, pauseInit] = fetchMock.mock.calls[6]
    expect(pauseUrl).toBe('/api/v1/matches/match-1/pause')
    expect(new Headers(pauseInit?.headers).get('Idempotency-Key')).toBe('command-pause-1')
    expect(JSON.parse(String(pauseInit?.body))).toEqual({ reason: 'Технический перерыв' })
  })

  it('loads and saves private drafts with revision fields and submits with a durable idempotency key', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ runId: 'run-1', problemId: 'problem-1', languageId: 'cpp20', source: 'int main() {}', revision: 2, updatedAt: '2026-10-09T17:00:00Z' }))
      .mockResolvedValueOnce(jsonResponse({ csrfToken: 'csrf-workspace' }))
      .mockResolvedValueOnce(jsonResponse({ runId: 'run-1', problemId: 'problem-1', languageId: 'cpp20', source: 'int main() { return 0; }', revision: 3, updatedAt: '2026-10-09T17:01:00Z' }))
      .mockResolvedValueOnce(jsonResponse({ submissionId: 'submission-1', runId: 'run-1', status: 'QUEUED', verdict: null, receivedAt: '2026-10-09T17:02:00Z', elapsedMs: 120000 }))

    const existing = await api.draft('match A', 'problem/1', 'run-1', 'cpp20')
    const saved = await api.saveDraft('match A', 'problem/1', 'cpp20', { runId: 'run-1', source: 'int main() { return 0; }', expectedRevision: existing.revision })
    const receipt = await api.submitSolution('match A', {
      runId: 'run-1', problemId: 'problem/1', languageId: 'cpp20', source: saved.source,
    }, 'retry-key-1')

    expect(existing.revision).toBe(2)
    expect(saved.revision).toBe(3)
    expect(receipt.submissionId).toBe('submission-1')
    expect(fetchMock).toHaveBeenCalledTimes(4)

    const [draftUrl, draftInit] = fetchMock.mock.calls[0]
    expect(draftUrl).toBe('/api/v1/matches/match%20A/problems/problem%2F1/draft?runId=run-1&languageId=cpp20')
    expect(draftInit?.method).toBeUndefined()
    expect(draftInit?.cache).toBe('no-store')

    const [saveUrl, saveInit] = fetchMock.mock.calls[2]
    expect(saveUrl).toBe('/api/v1/matches/match%20A/problems/problem%2F1/draft?languageId=cpp20')
    expect(saveInit?.method).toBe('PUT')
    expect(new Headers(saveInit?.headers).get('X-CSRFToken')).toBe('csrf-workspace')
    expect(JSON.parse(String(saveInit?.body))).toEqual({ runId: 'run-1', source: 'int main() { return 0; }', expectedRevision: 2 })

    const [submitUrl, submitInit] = fetchMock.mock.calls[3]
    expect(submitUrl).toBe('/api/v1/matches/match%20A/submissions')
    expect(submitInit?.method).toBe('POST')
    expect(new Headers(submitInit?.headers).get('X-CSRFToken')).toBe('csrf-workspace')
    expect(new Headers(submitInit?.headers).get('Idempotency-Key')).toBe('retry-key-1')
    expect(JSON.parse(String(submitInit?.body))).toEqual({
      runId: 'run-1', problemId: 'problem/1', languageId: 'cpp20', source: 'int main() { return 0; }',
    })
  })
})
