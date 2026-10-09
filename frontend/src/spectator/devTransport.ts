import type { PublicBracketSnapshot, PublicMatchEvent, PublicMatchSnapshot, PublicScoreChangedEvent } from './types'
import type { PublicStreamHandlers, SpectatorTransport } from './transport'

const tournamentId = '00000000-0000-4000-8000-000000000010'
const matchId = '00000000-0000-4000-8000-000000000020'
const runId = '00000000-0000-4000-8000-000000000030'
const iraId = '00000000-0000-4000-8000-000000000001'
const olegId = '00000000-0000-4000-8000-000000000004'
const problemIds = [
  '00000000-0000-4000-8000-000000000040',
  '00000000-0000-4000-8000-000000000041',
  '00000000-0000-4000-8000-000000000042',
  '00000000-0000-4000-8000-000000000043',
]

const publicBracket: PublicBracketSnapshot = {
  tournamentId,
  title: 'Демонстрационный блиц · данные разработки',
  bracketSize: 4,
  matches: [
    { id: matchId, key: 'r1-p1', roundIndex: 0, position: 0, status: 'RUNNING', slots: [{ displayName: 'Ира' }, { displayName: 'Олег' }], winnerName: null },
    { id: '00000000-0000-4000-8000-000000000021', key: 'r1-p2', roundIndex: 0, position: 1, status: 'READY', slots: [{ displayName: 'Дима' }, { displayName: 'Лена' }], winnerName: null },
    { id: '00000000-0000-4000-8000-000000000022', key: 'r2-p1', roundIndex: 1, position: 0, status: 'WAITING', slots: [{ displayName: null }, { displayName: null }], winnerName: null },
  ],
}

function player(userId: string, displayName: string, solvedProblem: string, penaltyMs: number) {
  return {
    userId,
    displayName,
    solvedCount: solvedProblem ? 1 : 0,
    penaltyMs,
    lastAcceptedElapsedMs: solvedProblem ? 120_000 : null,
    tasks: problemIds.map((problemId, index) => {
      const label = String.fromCharCode(65 + index)
      const isSolved = problemId === solvedProblem
      const isAttempted = displayName === 'Ира' && label === 'A'
      return {
        problemId,
        label,
        status: isSolved ? 'SOLVED' as const : isAttempted ? 'ATTEMPTED' as const : 'NOT_STARTED' as const,
        attempts: isSolved ? 1 : isAttempted ? 2 : 0,
        lastVerdict: isSolved ? 'OK' as const : isAttempted ? 'WA' as const : null,
      }
    }),
  }
}

const initialSnapshot: PublicMatchSnapshot = {
  matchId,
  runId,
  status: 'RUNNING',
  serverNow: '2026-10-09T18:00:00Z',
  elapsedMs: 180_000,
  remainingMs: 1_020_000,
  allowedDurationMs: 1_200_000,
  leaderUserId: iraId,
  winnerUserId: null,
  lastEventId: 42,
  scoringRule: {
    order: ['solved_desc', 'penalty_asc', 'last_accepted_asc'],
    wrongAttemptPenaltySec: 60,
    penalizedVerdicts: ['WA', 'TL', 'ML', 'RE'],
    finalTiePolicy: 'rematch',
  },
  players: [player(iraId, 'Ира', problemIds[2] ?? '', 120_000), player(olegId, 'Олег', problemIds[0] ?? '', 150_000)],
}

function clone<T>(value: T): T {
  return structuredClone(value)
}

function scoreEvent(eventId: number): PublicScoreChangedEvent {
  const players = clone(initialSnapshot.players)
  const ira = players[0]
  const oleg = players[1]
  if (ira) {
    ira.penaltyMs = 180_000
    ira.tasks[0] = { problemId: problemIds[0] ?? '', label: 'A', status: 'ATTEMPTED', attempts: 3, lastVerdict: 'TL' }
  }
  if (oleg) {
    oleg.solvedCount = 2
    oleg.penaltyMs = 210_000
    oleg.lastAcceptedElapsedMs = 240_000
    oleg.tasks[1] = { problemId: problemIds[1] ?? '', label: 'B', status: 'SOLVED', attempts: 1, lastVerdict: 'OK' }
  }
  return {
    eventId,
    type: 'score.changed',
    matchId,
    runId,
    payload: { leaderUserId: olegId, players },
  }
}

export function createDevSpectatorTransport(options: { disconnectOnce?: boolean; resyncOnce?: boolean } = {}): SpectatorTransport {
  let currentSnapshot = clone(initialSnapshot)
  let disconnectSent = false
  let resyncSent = false

  return {
    mode: 'development-scenario',
    async bracket(id) {
      if (id !== tournamentId) throw new Error('В dev-сценарии нет такой публичной сетки.')
      return clone(publicBracket)
    },
    async snapshot(id) {
      if (id !== matchId) throw new Error('В dev-сценарии нет такого публичного матча.')
      return clone(currentSnapshot)
    },
    subscribe(id: string, afterEventId: number, handlers: PublicStreamHandlers) {
      if (id !== matchId) {
        handlers.onError()
        return () => undefined
      }
      if (options.resyncOnce && !resyncSent) {
        resyncSent = true
        queueMicrotask(() => handlers.onResync({ type: 'stream.resync_required' }))
      }
      handlers.onOpen()
      let cancelled = false
      const timers: ReturnType<typeof setTimeout>[] = []
      const event = scoreEvent(43)
      if (afterEventId < 43) {
        timers.push(setTimeout(() => {
          if (cancelled) return
          if (options.disconnectOnce && !disconnectSent) {
            disconnectSent = true
            handlers.onError()
            return
          }
          currentSnapshot = {
            ...currentSnapshot,
            lastEventId: event.eventId,
            leaderUserId: event.payload.leaderUserId,
            players: clone(event.payload.players),
          }
          handlers.onEvent(event)
        }, 4_000))
      }
      if (afterEventId < 44) {
        timers.push(setTimeout(() => {
          if (cancelled) return
          const finishEvent: PublicMatchEvent = {
            eventId: 44,
            type: 'match.finished',
            matchId,
            runId,
            payload: { winnerUserId: olegId },
          }
          currentSnapshot = { ...currentSnapshot, status: 'FINISHED', winnerUserId: olegId, lastEventId: 44 }
          handlers.onEvent(finishEvent)
        }, 9_000))
      }
      return () => {
        cancelled = true
        timers.forEach(clearTimeout)
      }
    },
  }
}
