export const PUBLIC_MATCH_STATUSES = [
  'WAITING', 'READY', 'RUNNING', 'PAUSED', 'FINALIZING', 'FINISHED', 'TIED', 'SUPERSEDED',
] as const

export const PUBLIC_TASK_STATUSES = ['NOT_STARTED', 'ATTEMPTED', 'SOLVED'] as const
export const PUBLIC_VERDICTS = ['OK', 'WA', 'TL', 'ML', 'RE', 'CE'] as const

export type PublicMatchStatus = typeof PUBLIC_MATCH_STATUSES[number]
export type PublicTaskStatus = typeof PUBLIC_TASK_STATUSES[number]
export type PublicVerdict = typeof PUBLIC_VERDICTS[number]

export interface PublicTaskState {
  problemId: string
  label: string
  status: PublicTaskStatus
  attempts: number
  lastVerdict: PublicVerdict | null
}

export interface PublicPlayerState {
  userId: string
  displayName: string
  solvedCount: number
  penaltyMs: number
  lastAcceptedElapsedMs: number | null
  tasks: PublicTaskState[]
}

export interface PublicScoringRule {
  order: string[]
  wrongAttemptPenaltySec: number
  penalizedVerdicts: Array<'WA' | 'TL' | 'ML' | 'RE'>
  finalTiePolicy: 'rematch'
}

/** Exact allowlisted fields from contracts/mvp-v1/public-match.json. */
export interface PublicMatchSnapshot {
  matchId: string
  runId: string | null
  status: PublicMatchStatus
  serverNow: string
  elapsedMs: number
  remainingMs: number
  allowedDurationMs: number
  leaderUserId: string | null
  winnerUserId: string | null
  lastEventId: number
  scoringRule: PublicScoringRule
  players: [PublicPlayerState, PublicPlayerState]
}

export type PublicBracketStatus = PublicMatchStatus | 'BYE'

export interface PublicBracketMatch {
  id: string
  key: string
  roundIndex: number
  position: number
  status: PublicBracketStatus
  slots: [{ displayName: string | null }, { displayName: string | null }]
  winnerName: string | null
}

/** UI projection only. It intentionally carries no account/user identifiers. */
export interface PublicBracketSnapshot {
  tournamentId: string
  title: string
  bracketSize: number
  matches: PublicBracketMatch[]
}

export interface PublicScoreChangedEvent {
  eventId: number
  type: 'score.changed'
  matchId: string
  runId: string
  payload: {
    leaderUserId: string | null
    players: [PublicPlayerState, PublicPlayerState]
  }
}

export interface PublicSubmissionAcceptedEvent {
  eventId: number
  type: 'submission.accepted'
  matchId: string
  runId: string
  payload: { playerId: string; taskLabel: string; attemptCount: number }
}

export interface PublicSubmissionJudgedEvent {
  eventId: number
  type: 'submission.judged'
  matchId: string
  runId: string
  payload: { playerId: string; taskLabel: string; verdict: PublicVerdict }
}

export interface PublicMatchFinishedEvent {
  eventId: number
  type: 'match.finished'
  matchId: string
  runId: string
  payload: { winnerUserId: string | null }
}

export interface PublicMatchClockEvent {
  eventId: number
  type: 'match.paused' | 'match.resumed' | 'match.extended'
  matchId: string
  runId: string
  payload: {
    elapsedMs: number
    remainingMs: number
    allowedDurationMs?: number
  }
}

export interface PublicRefreshEvent {
  eventId: number
  type: 'match.started' | 'match.tied' | 'match.restarted' | 'participant.replaced' | 'bracket.advanced'
  matchId: string
  runId: string
  payload: Record<string, never>
}

export type PublicMatchEvent = PublicScoreChangedEvent
  | PublicSubmissionAcceptedEvent
  | PublicSubmissionJudgedEvent
  | PublicMatchFinishedEvent
  | PublicMatchClockEvent
  | PublicRefreshEvent

export interface PublicResyncNotice {
  type: 'stream.resync_required'
}

export type SpectatorConnection = 'loading' | 'connecting' | 'live' | 'reconnecting' | 'stale' | 'resyncing' | 'unavailable'

export type PublicAnimation =
  | { id: string; kind: 'solve'; playerId: string; taskLabel: string }
  | { id: string; kind: 'overtake'; fromUserId: string; toUserId: string }
  | { id: string; kind: 'win'; winnerUserId: string | null }

export interface SpectatorState {
  snapshot: PublicMatchSnapshot | null
  lastEventId: number
  connection: SpectatorConnection
  needsResync: boolean
  error: string | null
  animations: PublicAnimation[]
  animateProgress: boolean
}

export class PublicProtocolError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'PublicProtocolError'
  }
}
