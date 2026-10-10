import { PUBLIC_MATCH_STATUSES, PUBLIC_TASK_STATUSES, PUBLIC_VERDICTS, PublicProtocolError, type PublicBracketSnapshot, type PublicMatchEvent, type PublicMatchSnapshot, type PublicPlayerState, type PublicScoringRule, type PublicTaskState, type PublicVerdict } from './types'

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function exactKeys(value: Record<string, unknown>, expected: string[], label: string): void {
  if (Object.keys(value).sort().join('|') !== [...expected].sort().join('|')) {
    throw new PublicProtocolError(`${label}: unexpected or missing public fields.`)
  }
}

function text(value: unknown, label: string, maxLength = 160): string {
  if (typeof value !== 'string' || value.length === 0 || value.length > maxLength) {
    throw new PublicProtocolError(`${label}: invalid text.`)
  }
  return value
}

// Problem ids come from the imported package and may be any canonical UUID, not only RFC 4122 v1-v8.
function uuid(value: unknown, label: string): string {
  const candidate = text(value, label, 64)
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(candidate)) {
    throw new PublicProtocolError(`${label}: invalid identifier.`)
  }
  return candidate
}

function nullableUuid(value: unknown, label: string): string | null {
  return value === null ? null : uuid(value, label)
}

function integer(value: unknown, label: string, min = 0): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min) {
    throw new PublicProtocolError(`${label}: invalid integer.`)
  }
  return value
}

function verdict(value: unknown, label: string): PublicVerdict | null {
  if (value === null) return null
  if (typeof value !== 'string' || !PUBLIC_VERDICTS.includes(value as PublicVerdict)) {
    throw new PublicProtocolError(`${label}: invalid verdict.`)
  }
  return value as PublicVerdict
}

function parseTask(value: unknown): PublicTaskState {
  if (!record(value)) throw new PublicProtocolError('Task state must be an object.')
  exactKeys(value, ['problemId', 'label', 'status', 'attempts', 'lastVerdict'], 'Task state')
  const status = value.status
  if (typeof status !== 'string' || !PUBLIC_TASK_STATUSES.includes(status as PublicTaskState['status'])) {
    throw new PublicProtocolError('Task state has an unknown status.')
  }
  return {
    problemId: uuid(value.problemId, 'Task problemId'),
    label: text(value.label, 'Task label', 24),
    status: status as PublicTaskState['status'],
    attempts: integer(value.attempts, 'Task attempts'),
    lastVerdict: verdict(value.lastVerdict, 'Task verdict'),
  }
}

function parsePlayer(value: unknown): PublicPlayerState {
  if (!record(value)) throw new PublicProtocolError('Player state must be an object.')
  exactKeys(value, ['userId', 'displayName', 'solvedCount', 'penaltyMs', 'lastAcceptedElapsedMs', 'tasks'], 'Player state')
  if (!Array.isArray(value.tasks) || value.tasks.length > 24) {
    throw new PublicProtocolError('Player tasks must be a bounded list.')
  }
  const tasks = value.tasks.map(parseTask)
  if (new Set(tasks.map((task) => task.problemId)).size !== tasks.length
    || new Set(tasks.map((task) => task.label)).size !== tasks.length) {
    throw new PublicProtocolError('Player tasks must be unique.')
  }
  if (tasks.filter((task) => task.status === 'SOLVED').length !== integer(value.solvedCount, 'Player solvedCount')) {
    throw new PublicProtocolError('Solved task count must match the public task states.')
  }
  for (const task of tasks) {
    if ((task.status === 'NOT_STARTED' && (task.attempts !== 0 || task.lastVerdict !== null))
      || (task.status === 'ATTEMPTED' && task.attempts === 0)
      || (task.status === 'SOLVED' && (task.attempts === 0 || task.lastVerdict === null))) {
      throw new PublicProtocolError('Task attempts, verdict, and status are inconsistent.')
    }
  }
  return {
    userId: uuid(value.userId, 'Player userId'),
    displayName: text(value.displayName, 'Player displayName'),
    solvedCount: value.solvedCount as number,
    penaltyMs: integer(value.penaltyMs, 'Player penaltyMs'),
    lastAcceptedElapsedMs: value.lastAcceptedElapsedMs === null ? null : integer(value.lastAcceptedElapsedMs, 'Player lastAcceptedElapsedMs'),
    tasks,
  }
}

function parseScoringRule(value: unknown): PublicScoringRule {
  if (!record(value)) throw new PublicProtocolError('Scoring rule must be an object.')
  exactKeys(value, ['order', 'wrongAttemptPenaltySec', 'penalizedVerdicts', 'finalTiePolicy'], 'Scoring rule')
  if (!Array.isArray(value.order) || value.order.length > 8 || !value.order.every((entry) => typeof entry === 'string' && entry.length <= 48)) {
    throw new PublicProtocolError('Scoring rule order is invalid.')
  }
  if (!Array.isArray(value.penalizedVerdicts) || !value.penalizedVerdicts.every((entry) => ['WA', 'TL', 'ML', 'RE'].includes(String(entry)))) {
    throw new PublicProtocolError('Scoring rule verdicts are invalid.')
  }
  if (value.finalTiePolicy !== 'rematch') throw new PublicProtocolError('Scoring rule tie policy is invalid.')
  return {
    order: value.order as string[],
    wrongAttemptPenaltySec: integer(value.wrongAttemptPenaltySec, 'Wrong-attempt penalty'),
    penalizedVerdicts: value.penalizedVerdicts as PublicScoringRule['penalizedVerdicts'],
    finalTiePolicy: 'rematch',
  }
}

export function validatePublicSnapshot(value: unknown): PublicMatchSnapshot {
  if (!record(value)) throw new PublicProtocolError('Public match snapshot must be an object.')
  exactKeys(value, [
    'matchId', 'runId', 'status', 'serverNow', 'elapsedMs', 'remainingMs', 'allowedDurationMs',
    'leaderUserId', 'winnerUserId', 'lastEventId', 'scoringRule', 'players',
  ], 'Public match snapshot')
  if (typeof value.status !== 'string' || !PUBLIC_MATCH_STATUSES.includes(value.status as PublicMatchSnapshot['status'])) {
    throw new PublicProtocolError('Public match has an unknown status.')
  }
  if (typeof value.serverNow !== 'string' || !Number.isFinite(Date.parse(value.serverNow))) {
    throw new PublicProtocolError('Public match serverNow is invalid.')
  }
  if (!Array.isArray(value.players) || value.players.length !== 2) {
    throw new PublicProtocolError('Public match must have exactly two players.')
  }
  const players = value.players.map(parsePlayer) as [PublicPlayerState, PublicPlayerState]
  if (players[0].userId === players[1].userId) throw new PublicProtocolError('Public match players must be distinct.')
  const taskShape = players[0].tasks.map(({ problemId, label }) => `${problemId}:${label}`).join('|')
  if (players[1].tasks.map(({ problemId, label }) => `${problemId}:${label}`).join('|') !== taskShape) {
    throw new PublicProtocolError('Players must have the same published task list and order.')
  }
  const status = value.status as PublicMatchSnapshot['status']
  const leaderUserId = nullableUuid(value.leaderUserId, 'Leader userId')
  const winnerUserId = nullableUuid(value.winnerUserId, 'Winner userId')
  if (leaderUserId && !players.some((player) => player.userId === leaderUserId)) {
    throw new PublicProtocolError('Leader must be one of the public match players.')
  }
  if (winnerUserId && !players.some((player) => player.userId === winnerUserId)) {
    throw new PublicProtocolError('Winner must be one of the public match players.')
  }
  if (winnerUserId && status !== 'FINISHED') throw new PublicProtocolError('Only a finished match can have a winner.')
  return {
    matchId: uuid(value.matchId, 'Match id'),
    runId: nullableUuid(value.runId, 'Run id'),
    status,
    serverNow: value.serverNow,
    elapsedMs: integer(value.elapsedMs, 'Elapsed time'),
    remainingMs: integer(value.remainingMs, 'Remaining time'),
    allowedDurationMs: integer(value.allowedDurationMs, 'Allowed duration', 1),
    leaderUserId,
    winnerUserId,
    lastEventId: integer(value.lastEventId, 'Last event id'),
    scoringRule: parseScoringRule(value.scoringRule),
    players,
  }
}

export function validatePublicBracket(value: unknown): PublicBracketSnapshot {
  if (!record(value)) throw new PublicProtocolError('Public bracket must be an object.')
  exactKeys(value, ['tournamentId', 'title', 'bracketSize', 'matches'], 'Public bracket')
  if (!Array.isArray(value.matches) || value.matches.length > 128) {
    throw new PublicProtocolError('Public bracket matches must be a bounded list.')
  }
  const matches = value.matches.map((item) => {
    if (!record(item)) throw new PublicProtocolError('Public bracket match must be an object.')
    exactKeys(item, ['id', 'key', 'roundIndex', 'position', 'status', 'slots', 'winnerName'], 'Public bracket match')
    if (!Array.isArray(item.slots) || item.slots.length !== 2) throw new PublicProtocolError('Public bracket match must have two slots.')
    const slots = item.slots.map((slot) => {
      if (!record(slot)) throw new PublicProtocolError('Public bracket slot must be an object.')
      exactKeys(slot, ['displayName'], 'Public bracket slot')
      return { displayName: slot.displayName === null ? null : text(slot.displayName, 'Participant name') }
    }) as [{ displayName: string | null }, { displayName: string | null }]
    const allowedStatuses = [...PUBLIC_MATCH_STATUSES, 'BYE']
    if (typeof item.status !== 'string' || !allowedStatuses.includes(item.status as PublicMatchSnapshot['status'] | 'BYE')) {
      throw new PublicProtocolError('Public bracket match has an unknown status.')
    }
    return {
      id: uuid(item.id, 'Bracket match id'),
      key: text(item.key, 'Bracket match key', 40),
      roundIndex: integer(item.roundIndex, 'Bracket round index'),
      position: integer(item.position, 'Bracket position'),
      status: item.status as PublicBracketSnapshot['matches'][number]['status'],
      slots,
      winnerName: item.winnerName === null ? null : text(item.winnerName, 'Winner name'),
    }
  })
  if (new Set(matches.map((match) => match.id)).size !== matches.length
    || new Set(matches.map((match) => match.key)).size !== matches.length) {
    throw new PublicProtocolError('Public bracket contains duplicate matches.')
  }
  return {
    tournamentId: uuid(value.tournamentId, 'Tournament id'),
    title: text(value.title, 'Tournament title', 200),
    bracketSize: integer(value.bracketSize, 'Bracket size', 2),
    matches,
  }
}

function hasExactKeys(value: Record<string, unknown>, expected: string[]): boolean {
  return Object.keys(value).sort().join('|') === [...expected].sort().join('|')
}

function eventEnvelope(value: unknown): Record<string, unknown> {
  if (!record(value)) throw new PublicProtocolError('Public event must be an object.')
  exactKeys(value, ['eventId', 'type', 'matchId', 'runId', 'payload'], 'Public event')
  integer(value.eventId, 'Event id', 1)
  uuid(value.matchId, 'Event match id')
  uuid(value.runId, 'Event run id')
  if (!record(value.payload)) throw new PublicProtocolError('Public event payload must be an object.')
  return value
}

function inspectResyncPayload(value: unknown, state = { nodes: 0 }, depth = 0): void {
  state.nodes += 1
  if (state.nodes > 512) throw new PublicProtocolError('Public event payload is too large.')
  if (depth > 6) throw new PublicProtocolError('Public event payload is too deeply nested.')
  if (typeof value === 'string') {
    if (value.length > 512) throw new PublicProtocolError('Public event payload is too large.')
    return
  }
  if (Array.isArray(value)) {
    if (value.length > 64) throw new PublicProtocolError('Public event payload is too large.')
    value.forEach((item) => inspectResyncPayload(item, state, depth + 1))
    return
  }
  if (!record(value)) return
  const entries = Object.entries(value)
  if (entries.length > 64) throw new PublicProtocolError('Public event payload is too large.')
  for (const [key, item] of entries) {
    if (/(source|email|diagnostic|compiler|stderr|stdout|stdin|testinput|testoutput|secret|password|token|session|filepath|sourcepath)/i.test(key)) {
      throw new PublicProtocolError('Public event contains a private field.')
    }
    inspectResyncPayload(item, state, depth + 1)
  }
}

export function validatePublicEvent(value: unknown): PublicMatchEvent {
  const envelope = eventEnvelope(value)
  const payload = envelope.payload as Record<string, unknown>
  const base = {
    eventId: envelope.eventId as number,
    matchId: envelope.matchId as string,
    runId: envelope.runId as string,
  }
  if (envelope.type === 'score.changed') {
    if (!hasExactKeys(payload, ['leaderUserId', 'players']) || !Array.isArray(payload.players) || payload.players.length !== 2) {
      throw new PublicProtocolError('Score event payload is invalid.')
    }
    const players = payload.players.map(parsePlayer) as [PublicPlayerState, PublicPlayerState]
    const leaderUserId = nullableUuid(payload.leaderUserId, 'Score leader userId')
    if (leaderUserId && !players.some((player) => player.userId === leaderUserId)) {
      throw new PublicProtocolError('Score leader must be one of the public players.')
    }
    return { ...base, type: 'score.changed', payload: { leaderUserId, players } }
  }
  if (envelope.type === 'submission.accepted') {
    if (!hasExactKeys(payload, ['playerId', 'taskLabel', 'attemptCount'])) throw new PublicProtocolError('Accepted submission payload is invalid.')
    return {
      ...base,
      type: 'submission.accepted',
      payload: {
        playerId: uuid(payload.playerId, 'Accepted player id'),
        taskLabel: text(payload.taskLabel, 'Accepted task label', 24),
        attemptCount: integer(payload.attemptCount, 'Accepted attempt count', 1),
      },
    }
  }
  if (envelope.type === 'submission.judged') {
    if (!hasExactKeys(payload, ['playerId', 'taskLabel', 'verdict'])) throw new PublicProtocolError('Judged submission payload is invalid.')
    const parsedVerdict = verdict(payload.verdict, 'Judged verdict')
    if (!parsedVerdict) throw new PublicProtocolError('Judged verdict must be present.')
    return {
      ...base,
      type: 'submission.judged',
      payload: {
        playerId: uuid(payload.playerId, 'Judged player id'),
        taskLabel: text(payload.taskLabel, 'Judged task label', 24),
        verdict: parsedVerdict,
      },
    }
  }
  if (envelope.type === 'match.finished') {
    if (!hasExactKeys(payload, ['winnerUserId'])) throw new PublicProtocolError('Finished match payload is invalid.')
    return { ...base, type: 'match.finished', payload: { winnerUserId: nullableUuid(payload.winnerUserId, 'Winner userId') } }
  }
  if (envelope.type === 'match.paused' || envelope.type === 'match.resumed' || envelope.type === 'match.extended') {
    const expected = envelope.type === 'match.extended'
      ? ['elapsedMs', 'remainingMs', 'allowedDurationMs']
      : ['elapsedMs', 'remainingMs']
    if (!hasExactKeys(payload, expected)) throw new PublicProtocolError('Match clock event payload is invalid.')
    return {
      ...base,
      type: envelope.type,
      payload: {
        elapsedMs: integer(payload.elapsedMs, 'Event elapsed time'),
        remainingMs: integer(payload.remainingMs, 'Event remaining time'),
        ...(envelope.type === 'match.extended' ? { allowedDurationMs: integer(payload.allowedDurationMs, 'Event allowed duration', 1) } : {}),
      },
    }
  }
  if (['match.started', 'match.tied', 'match.restarted', 'participant.replaced', 'bracket.advanced'].includes(String(envelope.type))) {
    inspectResyncPayload(payload)
    return {
      ...base,
      type: envelope.type as 'match.started' | 'match.tied' | 'match.restarted' | 'participant.replaced' | 'bracket.advanced',
      payload: {},
    }
  }
  throw new PublicProtocolError('Public event type is not allowlisted.')
}
