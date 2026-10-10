import { afterEach, describe, expect, it, vi } from 'vitest'
import { PUBLIC_POLL_INTERVAL_MS, resolveSpectatorTransport } from './transport'
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

class FakeEventSource {
  static readonly CLOSED = 2
  static instances: FakeEventSource[] = []
  readonly url: string
  readyState = 0
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  private listeners = new Map<string, Array<(event: MessageEvent<string>) => void>>()

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener])
  }

  emit(type: string, data: unknown) {
    const event = { data: typeof data === 'string' ? data : JSON.stringify(data) } as MessageEvent<string>
    for (const listener of this.listeners.get(type) ?? []) listener(event)
  }

  close() {
    this.closed = true
    this.readyState = FakeEventSource.CLOSED
  }
}

function handlers() {
  return { onOpen: vi.fn(), onEvent: vi.fn(), onResync: vi.fn(), onError: vi.fn() }
}

describe('spectator transport selection', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    FakeEventSource.instances = []
  })

  it('reads the anonymous public bracket from the real endpoint and passes strict validation', async () => {
    const body = {
      tournamentId, title: 'Публичный турнир', bracketSize: 2,
      matches: [{
        id: matchId, key: 'r1-p1', roundIndex: 0, position: 0, status: 'RUNNING',
        slots: [{ displayName: 'Ира' }, { displayName: 'Олег' }], winnerName: null,
      }],
    }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(body))
    vi.stubGlobal('fetch', fetchMock)
    const transport = await resolveSpectatorTransport('')

    const bracket = validatePublicBracket(await transport.bracket(tournamentId))

    expect(transport.mode).toBe('http')
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/v1/public/tournaments/${tournamentId}/bracket`)
    expect(bracket.matches[0]).toMatchObject({ id: matchId, status: 'RUNNING' })
  })

  it('shows the backend answer when the bracket is not public or not generated', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ error: { code: 'not_found', message: 'Публичный объект не найден.', fields: null } }, 404)))
    const transport = await resolveSpectatorTransport('')

    await expect(transport.bracket(tournamentId)).rejects.toMatchObject({ status: 404, message: 'Публичный объект не найден.' })
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

  it('shows the backend not-ready answer instead of inventing a snapshot', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ error: { code: 'public_snapshot_not_ready', message: 'Публичный снимок матча ещё не готов.', fields: null } }, 409)))
    const transport = await resolveSpectatorTransport('')

    await expect(transport.snapshot(matchId)).rejects.toMatchObject({ status: 409, code: 'public_snapshot_not_ready' })
  })

  it('streams over SSE: opens, forwards score events and asks for a resync on request', async () => {
    vi.stubGlobal('EventSource', FakeEventSource)
    const transport = await resolveSpectatorTransport('')
    const handler = handlers()

    const stop = transport.subscribe(matchId, 5, handler)
    const source = FakeEventSource.instances[0]
    expect(source.url).toBe(`/api/v1/public/matches/${matchId}/events?lastEventId=5`)

    source.onopen?.()
    expect(handler.onOpen).toHaveBeenCalledOnce()

    const event = { eventId: 6, type: 'score.changed', matchId, runId: 'run', payload: { leaderUserId: null, players: [] } }
    source.emit('score.changed', event)
    expect(handler.onEvent).toHaveBeenCalledWith(event)

    source.emit('stream.resync_required', { type: 'stream.resync_required' })
    expect(handler.onResync).toHaveBeenCalledWith({ type: 'stream.resync_required' })

    source.emit('score.changed', 'not json')
    expect(handler.onResync).toHaveBeenCalledTimes(2)
    expect(handler.onEvent).toHaveBeenCalledTimes(1)

    stop()
    expect(source.closed).toBe(true)
  })

  it('treats a reconnecting stream as normal and reports only a closed stream as an error', async () => {
    vi.stubGlobal('EventSource', FakeEventSource)
    const transport = await resolveSpectatorTransport('')
    const handler = handlers()
    transport.subscribe(matchId, 0, handler)
    const source = FakeEventSource.instances[0]

    source.readyState = 0
    source.onerror?.()
    expect(handler.onError).not.toHaveBeenCalled()

    source.readyState = FakeEventSource.CLOSED
    source.onerror?.()
    expect(handler.onError).toHaveBeenCalledOnce()
  })

  it('falls back to polling in browsers without EventSource and resyncs only when the cursor moves', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(snapshot(5)))
      .mockResolvedValueOnce(jsonResponse(snapshot(5)))
      .mockResolvedValueOnce(jsonResponse(snapshot(6)))
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('EventSource', undefined)
    const transport = await resolveSpectatorTransport('')
    const handler = handlers()

    const stop = transport.subscribe(matchId, 5, handler)
    await vi.advanceTimersByTimeAsync(0)
    expect(handler.onOpen).toHaveBeenCalledOnce()
    expect(handler.onResync).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(PUBLIC_POLL_INTERVAL_MS)
    expect(handler.onResync).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(PUBLIC_POLL_INTERVAL_MS)
    expect(handler.onResync).toHaveBeenCalledOnce()
    stop()
    await vi.advanceTimersByTimeAsync(PUBLIC_POLL_INTERVAL_MS * 3)
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('reports a polling failure once and stops polling so the page can reconnect', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ error: { code: 'public_snapshot_unavailable', message: 'Недоступно.', fields: null } }, 503))
    vi.stubGlobal('fetch', fetchMock)
    vi.stubGlobal('EventSource', undefined)
    const transport = await resolveSpectatorTransport('')
    const handler = handlers()

    transport.subscribe(matchId, 0, handler)
    await vi.advanceTimersByTimeAsync(PUBLIC_POLL_INTERVAL_MS * 3)

    expect(handler.onError).toHaveBeenCalledOnce()
    expect(handler.onOpen).not.toHaveBeenCalled()
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('uses only the explicit development scenario in development builds', async () => {
    const transport = await resolveSpectatorTransport('?scenario=public-map')
    expect(transport.mode).toBe('development-scenario')
    await expect(transport.bracket(tournamentId)).resolves.toMatchObject({ title: 'Демонстрационный блиц · данные разработки' })
  })
})
