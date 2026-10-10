import { afterEach, describe, expect, it, vi } from 'vitest'
import { PUBLIC_POLL_INTERVAL_MS, resolveSpectatorTransport } from './transport'
import { ApiError } from '../api/client'
import { validatePublicBracket, validatePublicSnapshot } from './validation'

const matchId = '00000000-0000-4000-8000-000000000020'
const tournamentId = '00000000-0000-4000-8000-000000000010'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

function snapshot(lastEventId: number, overrides: Record<string, unknown> = {}) {
  const task = (label: string, status: string, attempts: number, lastVerdict: string | null) => ({
    problemId: `00000000-0000-4000-8000-0000000000${label === 'A' ? '40' : '41'}`, label, status, attempts, lastVerdict,
  })
  return {
    matchId,
    runId: '00000000-0000-4000-8000-000000000030',
    status: 'RUNNING',
    serverNow: '2026-10-10T01:00:00Z',
    elapsedMs: 60_000,
    remainingMs: 1_140_000,
    allowedDurationMs: 1_200_000,
    leaderUserId: '00000000-0000-4000-8000-000000000001',
    winnerUserId: null,
    lastEventId,
    scoringRule: { order: ['solved_desc', 'penalty_asc', 'last_accepted_asc'], wrongAttemptPenaltySec: 60, penalizedVerdicts: ['WA', 'TL', 'ML', 'RE'], finalTiePolicy: 'rematch' },
    players: [
      { userId: '00000000-0000-4000-8000-000000000001', displayName: 'Ира', solvedCount: 1, penaltyMs: 0, lastAcceptedElapsedMs: 30_000, tasks: [task('A', 'SOLVED', 1, 'OK'), task('B', 'NOT_STARTED', 0, null)] },
      { userId: '00000000-0000-4000-8000-000000000004', displayName: 'Олег', solvedCount: 0, penaltyMs: 60_000, lastAcceptedElapsedMs: null, tasks: [task('A', 'ATTEMPTED', 1, 'WA'), task('B', 'NOT_STARTED', 0, null)] },
    ],
    ...overrides,
  }
}

describe('spectator transport selection', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('refuses the tournament bracket without a match link because no public bracket endpoint exists', async () => {
    const transport = await resolveSpectatorTransport('')
    expect(transport.mode).toBe('http')
    await expect(transport.bracket(tournamentId)).rejects.toBeInstanceOf(ApiError)
  })

  it('reads the anonymous public snapshot from the real endpoint and passes strict validation', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(snapshot(7)))
    vi.stubGlobal('fetch', fetchMock)
    const transport = await resolveSpectatorTransport('')

    const read = validatePublicSnapshot(await transport.snapshot(matchId))

    expect(fetchMock.mock.calls[0][0]).toBe(`/api/v1/public/matches/${matchId}`)
    expect(read.lastEventId).toBe(7)
    expect(read.players.map((player) => player.displayName)).toEqual(['Ира', 'Олег'])
  })

  it('builds a one-match map from public snapshot fields only when a match link is opened', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(snapshot(7, { status: 'FINISHED', winnerUserId: '00000000-0000-4000-8000-000000000001' }))))
    const transport = await resolveSpectatorTransport('')

    const bracket = validatePublicBracket(await transport.bracket(tournamentId, matchId))

    expect(bracket.matches).toHaveLength(1)
    expect(bracket.matches[0]).toMatchObject({ id: matchId, status: 'FINISHED', winnerName: 'Ира', slots: [{ displayName: 'Ира' }, { displayName: 'Олег' }] })
    expect(JSON.stringify(bracket)).not.toMatch(/userId|email|source/)
  })

  it('shows the backend not-ready answer instead of inventing a snapshot', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ error: { code: 'public_snapshot_not_ready', message: 'Публичный снимок матча ещё не готов.', fields: null } }, 409)))
    const transport = await resolveSpectatorTransport('')

    await expect(transport.snapshot(matchId)).rejects.toMatchObject({ status: 409, code: 'public_snapshot_not_ready' })
  })

  it('polls the snapshot, opens once and asks for a resync only when the event cursor moves', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(snapshot(5)))
      .mockResolvedValueOnce(jsonResponse(snapshot(5)))
      .mockResolvedValueOnce(jsonResponse(snapshot(6)))
    vi.stubGlobal('fetch', fetchMock)
    const transport = await resolveSpectatorTransport('')
    const handlers = { onOpen: vi.fn(), onEvent: vi.fn(), onResync: vi.fn(), onError: vi.fn() }

    const stop = transport.subscribe(matchId, 5, handlers)
    await vi.advanceTimersByTimeAsync(0)
    expect(handlers.onOpen).toHaveBeenCalledOnce()
    expect(handlers.onResync).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(PUBLIC_POLL_INTERVAL_MS)
    expect(handlers.onResync).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(PUBLIC_POLL_INTERVAL_MS)
    expect(handlers.onResync).toHaveBeenCalledOnce()
    expect(handlers.onOpen).toHaveBeenCalledOnce()
    stop()
    await vi.advanceTimersByTimeAsync(PUBLIC_POLL_INTERVAL_MS * 3)
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('reports a polling failure once and stops polling so the page can reconnect', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ error: { code: 'public_snapshot_unavailable', message: 'Недоступно.', fields: null } }, 503))
    vi.stubGlobal('fetch', fetchMock)
    const transport = await resolveSpectatorTransport('')
    const handlers = { onOpen: vi.fn(), onEvent: vi.fn(), onResync: vi.fn(), onError: vi.fn() }

    transport.subscribe(matchId, 0, handlers)
    await vi.advanceTimersByTimeAsync(PUBLIC_POLL_INTERVAL_MS * 3)

    expect(handlers.onError).toHaveBeenCalledOnce()
    expect(handlers.onOpen).not.toHaveBeenCalled()
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('uses only the explicit development scenario in development builds', async () => {
    const transport = await resolveSpectatorTransport('?scenario=public-map')
    expect(transport.mode).toBe('development-scenario')
    await expect(transport.bracket(tournamentId)).resolves.toMatchObject({ title: 'Демонстрационный блиц · данные разработки' })
  })
})
