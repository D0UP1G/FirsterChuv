import { validatePublicEvent } from './validation'
import { PublicProtocolError, type PublicAnimation, type PublicMatchEvent, type PublicMatchSnapshot, type PublicResyncNotice, type SpectatorConnection, type SpectatorState } from './types'

export function createSpectatorState(): SpectatorState {
  return {
    snapshot: null,
    lastEventId: 0,
    connection: 'loading',
    needsResync: false,
    error: null,
    animations: [],
    animateProgress: false,
  }
}

export function setSpectatorConnection(state: SpectatorState, connection: SpectatorConnection): SpectatorState {
  if (state.connection === connection && state.error === null) return state
  return {
    ...state,
    connection,
    error: null,
    ...(connection === 'live' ? {} : { animations: [], animateProgress: false }),
  }
}

export function applyPublicSnapshot(state: SpectatorState, snapshot: PublicMatchSnapshot): SpectatorState {
  if (state.snapshot?.matchId === snapshot.matchId
    && state.snapshot.runId === snapshot.runId
    && snapshot.lastEventId < state.lastEventId) {
    return {
      ...state,
      connection: 'resyncing',
      needsResync: true,
      error: 'Снимок устарел относительно уже принятых событий.',
      animations: [],
      animateProgress: false,
    }
  }
  return {
    snapshot,
    lastEventId: snapshot.lastEventId,
    connection: 'connecting',
    needsResync: false,
    error: null,
    animations: [],
    animateProgress: false,
  }
}

export function requestPublicResync(state: SpectatorState): SpectatorState {
  return { ...state, connection: 'resyncing', needsResync: true, animations: [], animateProgress: false }
}

export function failSpectatorProtocol(state: SpectatorState, error: unknown): SpectatorState {
  const message = error instanceof PublicProtocolError
    ? 'Сервер прислал неподдерживаемые данные публичной карты.'
    : error instanceof Error
      ? error.message
      : 'Не удалось обработать публичные данные матча.'
  return { ...state, connection: 'unavailable', needsResync: false, error: message, animations: [], animateProgress: false }
}

function publicAnimations(previous: PublicMatchSnapshot, next: PublicMatchSnapshot, eventId: number): PublicAnimation[] {
  const animations: PublicAnimation[] = []
  for (const nextPlayer of next.players) {
    const previousPlayer = previous.players.find((player) => player.userId === nextPlayer.userId)
    if (!previousPlayer) continue
    const justSolved = nextPlayer.tasks.find((task) => task.status === 'SOLVED'
      && previousPlayer.tasks.find((candidate) => candidate.problemId === task.problemId)?.status !== 'SOLVED')
    if (justSolved) animations.push({
      id: `${next.runId ?? next.matchId}:${eventId}:solve:${nextPlayer.userId}:${justSolved.problemId}`,
      kind: 'solve',
      playerId: nextPlayer.userId,
      taskLabel: justSolved.label,
    })
  }
  const oldLeader = previous.leaderUserId
  const newLeader = next.leaderUserId
  if (oldLeader && newLeader && oldLeader !== newLeader) {
    animations.push({
      id: `${next.runId ?? next.matchId}:${eventId}:overtake:${oldLeader}:${newLeader}`,
      kind: 'overtake',
      fromUserId: oldLeader,
      toUserId: newLeader,
    })
  }
  return animations
}

function withEventCursor(state: SpectatorState, event: PublicMatchEvent, snapshot: PublicMatchSnapshot, animations: PublicAnimation[] = []): SpectatorState {
  return {
    ...state,
    snapshot: { ...snapshot, lastEventId: event.eventId },
    lastEventId: event.eventId,
    connection: 'live',
    needsResync: false,
    error: null,
    animations,
    animateProgress: animations.some((animation) => animation.kind === 'solve'),
  }
}

export function applyPublicEvent(state: SpectatorState, input: unknown): SpectatorState {
  if (!state.snapshot) return requestPublicResync(state)
  let event: PublicMatchEvent
  try {
    event = validatePublicEvent(input)
  } catch (error) {
    return failSpectatorProtocol(state, error)
  }

  const snapshot = state.snapshot
  if (event.matchId !== snapshot.matchId) return requestPublicResync(state)
  if (event.eventId <= state.lastEventId) return state
  if (event.eventId !== state.lastEventId + 1) return requestPublicResync(state)
  if (!snapshot.runId || event.runId !== snapshot.runId) return requestPublicResync(state)
  if (event.type === 'match.started' || event.type === 'match.tied' || event.type === 'match.restarted'
    || event.type === 'participant.replaced' || event.type === 'bracket.advanced') {
    return requestPublicResync(state)
  }

  if (event.type === 'score.changed') {
    const currentPlayerIds = snapshot.players.map((player) => player.userId).sort()
    const eventPlayerIds = event.payload.players.map((player) => player.userId).sort()
    if (currentPlayerIds.some((id, index) => id !== eventPlayerIds[index])) return requestPublicResync(state)
    for (const player of event.payload.players) {
      const current = snapshot.players.find((candidate) => candidate.userId === player.userId)
      const taskShape = (value: PublicMatchSnapshot['players'][number]) => value.tasks.map((task) => `${task.problemId}:${task.label}`).join('|')
      if (!current || taskShape(current) !== taskShape(player)) return requestPublicResync(state)
    }
    const next: PublicMatchSnapshot = {
      ...snapshot,
      leaderUserId: event.payload.leaderUserId,
      players: event.payload.players,
    }
    return withEventCursor(state, event, next, publicAnimations(snapshot, next, event.eventId))
  }

  // These event IDs are not explicitly equivalent to public-match user IDs in v1.
  // Re-read the public-safe snapshot instead of guessing which lane to update.
  if (event.type === 'submission.accepted' || event.type === 'submission.judged') return requestPublicResync(state)

  if (event.type === 'match.finished') {
    if (event.payload.winnerUserId && !snapshot.players.some((player) => player.userId === event.payload.winnerUserId)) {
      return requestPublicResync(state)
    }
    const next: PublicMatchSnapshot = { ...snapshot, status: 'FINISHED', winnerUserId: event.payload.winnerUserId }
    const animations = snapshot.status === 'FINISHED' || !event.payload.winnerUserId
      ? []
      : [{ id: `${snapshot.runId}:${event.eventId}:win`, kind: 'win' as const, winnerUserId: event.payload.winnerUserId }]
    return withEventCursor(state, event, next, animations)
  }

  if (event.type === 'match.paused' || event.type === 'match.resumed' || event.type === 'match.extended') {
    const next: PublicMatchSnapshot = {
      ...snapshot,
      status: event.type === 'match.paused' ? 'PAUSED' : event.type === 'match.resumed' ? 'RUNNING' : snapshot.status,
      elapsedMs: event.payload.elapsedMs,
      remainingMs: event.payload.remainingMs,
      allowedDurationMs: event.type === 'match.extended' ? event.payload.allowedDurationMs as number : snapshot.allowedDurationMs,
    }
    return withEventCursor(state, event, next)
  }

  return requestPublicResync(state)
}

export function applyResyncNotice(state: SpectatorState, notice: PublicResyncNotice): SpectatorState {
  if (notice.type !== 'stream.resync_required') return state
  return requestPublicResync(state)
}
