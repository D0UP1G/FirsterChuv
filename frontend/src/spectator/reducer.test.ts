import { describe, expect, it } from 'vitest'
import { applyPublicEvent, applyPublicSnapshot, createSpectatorState } from './reducer'
import { validatePublicBracket, validatePublicEvent, validatePublicSnapshot } from './validation'
import type { PublicBracketSnapshot, PublicMatchSnapshot } from './types'

const matchId = '00000000-0000-4000-8000-000000000020'
const runId = '00000000-0000-4000-8000-000000000030'
const playerOneId = '00000000-0000-4000-8000-000000000001'
const playerTwoId = '00000000-0000-4000-8000-000000000004'
const problems = [
  '00000000-0000-4000-8000-000000000040',
  '00000000-0000-4000-8000-000000000041',
  '00000000-0000-4000-8000-000000000042',
  '00000000-0000-4000-8000-000000000043',
]

function makePlayer(userId: string, displayName: string, solvedProblemId: string | null, penaltyMs: number) {
  return {
    userId,
    displayName,
    solvedCount: solvedProblemId ? 1 : 0,
    penaltyMs,
    lastAcceptedElapsedMs: solvedProblemId ? 90_000 : null,
    tasks: problems.map((problemId, index) => ({
      problemId,
      label: String.fromCharCode(65 + index),
      status: problemId === solvedProblemId ? 'SOLVED' as const : 'NOT_STARTED' as const,
      attempts: problemId === solvedProblemId ? 1 : 0,
      lastVerdict: problemId === solvedProblemId ? 'OK' as const : null,
    })),
  }
}

const snapshot: PublicMatchSnapshot = {
  matchId,
  runId,
  status: 'RUNNING',
  serverNow: '2026-10-09T18:00:00Z',
  elapsedMs: 180_000,
  remainingMs: 1_020_000,
  allowedDurationMs: 1_200_000,
  leaderUserId: playerOneId,
  winnerUserId: null,
  lastEventId: 42,
  scoringRule: {
    order: ['solved_desc', 'penalty_asc', 'last_accepted_asc'],
    wrongAttemptPenaltySec: 60,
    penalizedVerdicts: ['WA', 'TL', 'ML', 'RE'],
    finalTiePolicy: 'rematch',
  },
  players: [makePlayer(playerOneId, 'Ира', problems[2] ?? null, 120_000), makePlayer(playerTwoId, 'Олег', null, 150_000)],
}

const bracket: PublicBracketSnapshot = {
  tournamentId: '00000000-0000-4000-8000-000000000010',
  title: 'Блиц',
  bracketSize: 2,
  matches: [{
    id: matchId,
    key: 'r1-p1',
    roundIndex: 0,
    position: 0,
    status: 'RUNNING',
    slots: [{ displayName: 'Ира' }, { displayName: 'Олег' }],
    winnerName: null,
  }],
}

function scoreChange(eventId = 43) {
  const players = structuredClone(snapshot.players)
  const challenger = players[1]
  if (!challenger) throw new Error('Fixture requires player two.')
  challenger.solvedCount = 1
  challenger.penaltyMs = 100_000
  challenger.lastAcceptedElapsedMs = 175_000
  challenger.tasks[1] = { problemId: problems[1] ?? '', label: 'B', status: 'SOLVED', attempts: 1, lastVerdict: 'OK' }
  return {
    eventId,
    type: 'score.changed',
    matchId,
    runId,
    payload: { leaderUserId: playerTwoId, players },
  }
}

describe('public spectator validation and event reducer', () => {
  it('allows a task to be solved independently of earlier checkpoints', () => {
    const parsed = validatePublicSnapshot(snapshot)
    expect(parsed.players[0].tasks[0]?.status).toBe('NOT_STARTED')
    expect(parsed.players[0].tasks[2]?.status).toBe('SOLVED')
    expect(parsed.players[0].solvedCount).toBe(1)
  })

  it('rejects private or undocumented fields in snapshots, events, and bracket DTOs', () => {
    expect(() => validatePublicSnapshot({ ...snapshot, source: 'print(secret)' })).toThrow(/unexpected or missing public fields/)
    expect(() => validatePublicSnapshot({
      ...snapshot,
      players: snapshot.players.map((player, index) => index === 0 ? { ...player, email: 'hidden@example.test' } : player),
    })).toThrow(/unexpected or missing public fields/)
    expect(() => validatePublicEvent({ ...scoreChange(), payload: { ...scoreChange().payload, compilerLog: 'private' } })).toThrow(/Score event payload is invalid/)
    expect(() => validatePublicBracket({ ...bracket, matches: [{ ...bracket.matches[0], slots: [{ displayName: 'Ира', userId: playerOneId }, { displayName: 'Олег' }] }] })).toThrow(/unexpected or missing public fields/)
  })

  it('deduplicates score events and animates only authoritative solve and leader transitions', () => {
    const initial = applyPublicSnapshot(createSpectatorState(), snapshot)
    const event = scoreChange()
    const updated = applyPublicEvent(initial, event)
    expect(updated.snapshot?.players[1]?.tasks[1]?.status).toBe('SOLVED')
    expect(updated.snapshot?.leaderUserId).toBe(playerTwoId)
    expect(updated.animations.map((animation) => animation.kind)).toEqual(['solve', 'overtake'])
    expect(applyPublicEvent(updated, event)).toBe(updated)
  })

  it('reloads authoritative task state instead of guessing event-player identity', () => {
    const initial = applyPublicSnapshot(createSpectatorState(), snapshot)
    const accepted = applyPublicEvent(initial, {
      eventId: 43,
      type: 'submission.accepted',
      matchId,
      runId,
      payload: { playerId: playerTwoId, taskLabel: 'C', attemptCount: 1 },
    })
    const task = accepted.snapshot?.players[1]?.tasks[2]
    expect(accepted.needsResync).toBe(true)
    expect(task?.status).toBe('NOT_STARTED')
    expect(task?.attempts).toBe(0)
    expect(accepted.animations).toEqual([])
  })

  it('requests a snapshot after a missing event or a different run', () => {
    const initial = applyPublicSnapshot(createSpectatorState(), snapshot)
    expect(applyPublicEvent(initial, scoreChange(44)).needsResync).toBe(true)
    expect(applyPublicEvent(initial, { ...scoreChange(), runId: '00000000-0000-4000-8000-000000000099' }).needsResync).toBe(true)
  })

  it('only emits a win effect for the first finished event', () => {
    const initial = applyPublicSnapshot(createSpectatorState(), snapshot)
    const finish = { eventId: 43, type: 'match.finished', matchId, runId, payload: { winnerUserId: playerTwoId } }
    const finished = applyPublicEvent(initial, finish)
    expect(finished.snapshot?.status).toBe('FINISHED')
    expect(finished.animations.map((animation) => animation.kind)).toEqual(['win'])
    expect(applyPublicEvent(finished, finish)).toBe(finished)
  })

  it('rejects duplicate bracket matches', () => {
    expect(validatePublicBracket(bracket).matches[0]?.slots[0]?.displayName).toBe('Ира')
    expect(() => validatePublicBracket({ ...bracket, matches: [...bracket.matches, ...bracket.matches] })).toThrow(/duplicate matches/)
  })

  it('refreshes from the server for a documented bracket or run change event', () => {
    const initial = applyPublicSnapshot(createSpectatorState(), snapshot)
    const refreshed = applyPublicEvent(initial, {
      eventId: 43,
      type: 'bracket.advanced',
      matchId,
      runId,
      payload: { winner: playerOneId, downstreamMatchId: '00000000-0000-4000-8000-000000000021' },
    })
    expect(refreshed.needsResync).toBe(true)
    expect(() => validatePublicEvent({
      eventId: 43,
      type: 'bracket.advanced',
      matchId,
      runId,
      payload: { winner: playerOneId, source: 'private source' },
    })).toThrow(/private field/)
  })
})
