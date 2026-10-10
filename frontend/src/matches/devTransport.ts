import { ApiError, type Bracket, type BracketMatch, type BracketParticipant, type BracketSlot, type DirectoryUser, type FirstRoundPairing, type MatchActionInput, type MatchConfigInput, type MatchPlayerState, type MatchView, type ProblemCatalogEntry, type ProblemVersion, type RosterEntry, type Tournament } from '../api/client'
import type { MatchAdminTransport } from './transport'

const tournamentId = '00000000-0000-4000-8000-000000000010'
const participants: BracketParticipant[] = [1, 2, 3, 4, 5].map((number) => ({
  id: `00000000-0000-4000-8000-00000000020${number}`,
  userId: `00000000-0000-4000-8000-00000000000${number}`,
  displayName: ['Ира', 'Дима', 'Лена', 'Олег', 'Миша'][number - 1],
  seed: number,
}))
const replacementCandidate: BracketParticipant = {
  id: '00000000-0000-4000-8000-000000000026',
  userId: '00000000-0000-4000-8000-000000000006',
  displayName: 'Новый участник',
  seed: null,
}
const problems: ProblemCatalogEntry[] = [
  { problemId: '00000000-0000-4000-8000-000000000040', label: 'A', version: 'synthetic-v1', readiness: 'READY' },
  { problemId: '00000000-0000-4000-8000-000000000041', label: 'B', version: 'synthetic-v1', readiness: 'READY' },
  { problemId: '00000000-0000-4000-8000-000000000042', label: 'C', version: 'synthetic-v1', readiness: 'READY' },
  { problemId: '00000000-0000-4000-8000-000000000043', label: 'D', version: 'synthetic-v1', readiness: 'NOT_READY' },
]
const readyVersions: ProblemVersion[] = problems
  .filter((problem) => problem.readiness === 'READY')
  .map(({ problemId, label, version }) => ({ problemId, label, version, conditionAvailable: true }))
const scoringRule: Tournament['scoringRule'] = {
  order: ['solved_desc', 'penalty_asc', 'last_accepted_asc'],
  wrongAttemptPenaltySec: 60,
  penalizedVerdicts: ['WA', 'TL', 'ML', 'RE'],
  finalTiePolicy: 'rematch',
}

function makeSlot(index: number, resolution: BracketSlot['resolution'], participant: BracketParticipant | null, sourceMatchId: string | null = null): BracketSlot {
  return { index, resolution, participant, sourceMatchId }
}

export function buildDevBracket(count: number): Bracket {
  const roster = participants.slice(0, Math.min(Math.max(count, 2), participants.length))
  const size = 2 ** Math.ceil(Math.log2(roster.length))
  const byeCount = size - roster.length
  const roundOnePairs: Array<[BracketParticipant | null, BracketParticipant | null]> = []
  roster.slice(0, byeCount).forEach((entrant) => roundOnePairs.push([entrant, null]))
  const playedEntrants = roster.slice(byeCount)
  for (let index = 0; index < playedEntrants.length; index += 2) {
    roundOnePairs.push([playedEntrants[index] ?? null, playedEntrants[index + 1] ?? null])
  }

  const rounds: BracketMatch[][] = []
  const firstRound = roundOnePairs.map(([left, right], position): BracketMatch => {
    const id = `00000000-0000-4000-8000-${String(300 + position).padStart(12, '0')}`
    const isBye = left === null || right === null
    return {
      id,
      key: `r1-p${position + 1}`,
      roundIndex: 0,
      position,
      kind: isBye ? 'BYE' : 'MATCH',
      status: isBye ? 'BYE' : 'READY',
      winner: isBye ? left ?? right : null,
      nextMatchId: null,
      nextSlot: null,
      slots: [
        makeSlot(0, left ? 'PLAYER' : 'BYE', left),
        makeSlot(1, right ? 'PLAYER' : 'BYE', right),
      ],
    }
  })
  rounds.push(firstRound)

  let priorRound = firstRound
  let roundIndex = 1
  while (priorRound.length > 1) {
    const nextRound: BracketMatch[] = []
    for (let index = 0; index < priorRound.length; index += 2) {
      const leftSource = priorRound[index]
      const rightSource = priorRound[index + 1]
      const id = `00000000-0000-4000-8000-${String(300 + firstRound.length + nextRound.length + rounds.slice(1).reduce((sum, round) => sum + round.length, 0)).padStart(12, '0')}`
      const leftPlayer = leftSource?.kind === 'BYE' ? leftSource.winner : null
      const rightPlayer = rightSource?.kind === 'BYE' ? rightSource.winner : null
      nextRound.push({
        id,
        key: `r${roundIndex + 1}-p${nextRound.length + 1}`,
        roundIndex,
        position: nextRound.length,
        kind: 'MATCH',
        status: leftPlayer && rightPlayer ? 'READY' : 'WAITING',
        winner: null,
        nextMatchId: null,
        nextSlot: null,
        slots: [
          makeSlot(0, leftPlayer ? 'PLAYER' : 'WAITING', leftPlayer, leftSource?.id ?? null),
          makeSlot(1, rightPlayer ? 'PLAYER' : 'WAITING', rightPlayer, rightSource?.id ?? null),
        ],
      })
    }
    priorRound.forEach((match, index) => {
      const parent = nextRound[Math.floor(index / 2)]
      match.nextMatchId = parent?.id ?? null
      match.nextSlot = index % 2
    })
    rounds.push(nextRound)
    priorRound = nextRound
    roundIndex += 1
  }

  return {
    tournamentId,
    bracketSize: size,
    rosterFrozenAt: '2026-10-09T17:00:00Z',
    matches: rounds.flat(),
  }
}

function makeTournament(activeParticipantCount: number): Tournament {
  return {
    id: tournamentId,
    slug: 'dev-match-scenario',
    title: 'Демонстрационная сетка · данные разработки',
    description: 'Синтетический сценарий интерфейса. Не является живым турниром.',
    startsAt: '2026-10-10T09:00:00Z',
    endsAt: '2026-10-10T12:00:00Z',
    format: 'single_elimination',
    participantLimit: 8,
    visibility: 'unlisted',
    status: 'scheduled',
    activeParticipantCount,
    rosterFrozenAt: '2026-10-09T17:00:00Z',
    matchDurationSec: 1200,
    startMode: 'both_ready',
    scoringRule,
  }
}

function makePlayers(problemVersions: ProblemVersion[], matchParticipants: BracketParticipant[]): [MatchPlayerState, MatchPlayerState] {
  return matchParticipants.slice(0, 2).map((participant) => ({
    userId: participant.userId,
    displayName: participant.displayName,
    solvedCount: 0,
    penaltyMs: 0,
    lastAcceptedElapsedMs: null,
    tasks: problemVersions.map((problem) => ({
      problemId: problem.problemId,
      label: problem.label,
      status: 'NOT_STARTED',
      attempts: 0,
      lastVerdict: null,
    })),
  })) as [MatchPlayerState, MatchPlayerState]
}

export function createDevMatchTransport(count = 4): MatchAdminTransport {
  const entrantCount = Number.isFinite(count) && count >= 2 && count <= participants.length ? Math.floor(count) : 4
  const tournament = makeTournament(entrantCount)
  let rosterParticipants = participants.slice(0, entrantCount)
  const bracket = buildDevBracket(entrantCount)
  const firstPlayable = bracket.matches.find((match) => match.roundIndex === 0 && match.kind === 'MATCH')
  const matchParticipants = firstPlayable?.slots.flatMap((slot) => slot.participant ? [slot.participant] : []) ?? participants.slice(0, 2)
  const commandKeys = new Set<string>()
  let currentMatch: MatchView | null = firstPlayable ? {
    matchId: firstPlayable.id,
    runId: '00000000-0000-4000-8000-000000000390',
    status: 'READY',
    serverNow: new Date().toISOString(),
    elapsedMs: 0,
    remainingMs: tournament.matchDurationSec * 1000,
    allowedDurationMs: tournament.matchDurationSec * 1000,
    leaderUserId: null,
    winnerUserId: null,
    lastEventId: 0,
    scoringRule,
    players: makePlayers(readyVersions.slice(0, 2), matchParticipants),
    tournamentId,
    startMode: tournament.startMode,
    readyUserIds: [],
    problemVersions: readyVersions.slice(0, 2),
  } : null

  function requireMatch(id: string): MatchView {
    if (!currentMatch || currentMatch.matchId !== id) {
      throw new ApiError('В этом синтетическом сценарии нет выбранного матча.', 404, 'match_not_found')
    }
    return currentMatch
  }

  function syncBracketStatus(match: MatchView): void {
    const bracketMatch = bracket.matches.find((candidate) => candidate.id === match.matchId)
    if (!bracketMatch) return
    bracketMatch.status = match.status
    if (match.winnerUserId) {
      bracketMatch.winner = participants.find((participant) => participant.userId === match.winnerUserId) ?? null
    }
  }

  function applyAction(input: MatchActionInput): MatchView {
    if (!currentMatch) throw new ApiError('Сначала выберите готовый матч.', 409, 'match_not_ready')
    switch (input.name) {
      case 'start':
        if (currentMatch.startMode === 'both_ready' && currentMatch.readyUserIds.length < 2) {
          throw new ApiError('Ожидается готовность обоих участников.', 409, 'both_players_not_ready')
        }
        currentMatch = { ...currentMatch, status: 'RUNNING', serverNow: new Date().toISOString() }
        break
      case 'pause':
        currentMatch = { ...currentMatch, status: 'PAUSED' }
        break
      case 'resume':
        currentMatch = { ...currentMatch, status: 'RUNNING' }
        break
      case 'extend':
        currentMatch = { ...currentMatch, allowedDurationMs: currentMatch.allowedDurationMs + input.seconds * 1000, remainingMs: currentMatch.remainingMs + input.seconds * 1000 }
        break
      case 'technical-result':
        currentMatch = { ...currentMatch, status: 'FINISHED', winnerUserId: input.winnerUserId }
        break
      case 'rematches':
        currentMatch = {
          ...currentMatch,
          runId: crypto.randomUUID(),
          status: 'READY',
          elapsedMs: 0,
          remainingMs: currentMatch.allowedDurationMs,
          readyUserIds: [],
          winnerUserId: null,
          problemVersions: input.problemIds
            ? readyVersions.filter((problem) => input.problemIds?.includes(problem.problemId))
            : currentMatch.problemVersions,
          players: makePlayers(
            input.problemIds ? readyVersions.filter((problem) => input.problemIds?.includes(problem.problemId)) : currentMatch.problemVersions,
            currentMatch.players.map((player) => ({ id: player.userId, userId: player.userId, displayName: player.displayName, seed: null })),
          ),
        }
        break
      case 'replacements':
        {
          const replacement = [...participants, replacementCandidate].find((participant) => participant.userId === input.newUserId)
          const alreadyPaired = bracket.matches.some((candidate) => candidate.slots.some((slot) => slot.participant?.userId === input.newUserId))
          if (!replacement || alreadyPaired || !bracket.matches.some((candidate) => candidate.slots.some((slot) => slot.participant?.userId === input.oldUserId))) {
            throw new ApiError('Новый участник уже находится в сетке или недоступен.', 409, 'replacement_not_available')
          }
          for (const candidate of bracket.matches) {
            candidate.slots = candidate.slots.map((slot) => slot.participant?.userId === input.oldUserId
              ? makeSlot(slot.index, 'PLAYER', replacement, slot.sourceMatchId)
              : slot) as [BracketSlot, BracketSlot]
          }
          rosterParticipants = rosterParticipants.filter((participant) => participant.userId !== input.oldUserId)
          rosterParticipants.push(replacement)
          tournament.activeParticipantCount = rosterParticipants.length
          const activeMatch = currentMatch
          const replacedPlayers = activeMatch.players.map((player) => player.userId === input.oldUserId
            ? {
              ...player,
              userId: replacement.userId,
              displayName: replacement.displayName,
              solvedCount: 0,
              penaltyMs: 0,
              lastAcceptedElapsedMs: null,
              tasks: activeMatch.problemVersions.map((problem) => ({ problemId: problem.problemId, label: problem.label, status: 'NOT_STARTED' as const, attempts: 0, lastVerdict: null })),
            }
            : player) as [MatchPlayerState, MatchPlayerState]
          currentMatch = { ...activeMatch, players: replacedPlayers }
        }
        break
    }
    syncBracketStatus(currentMatch)
    return currentMatch
  }

  return {
    mode: 'development-scenario',
    async tournament() { return tournament },
    async roster() {
      return rosterParticipants.map((participant) => ({
        userId: participant.userId,
        displayName: participant.displayName,
        seed: participant.seed,
        status: 'ACTIVE',
        addedAt: '2026-10-09T16:00:00Z',
        removedAt: null,
      })) as RosterEntry[]
    },
    async directory(query: string) {
      const existingIds = new Set(bracket.matches.flatMap((candidate) => candidate.slots.map((slot) => slot.participant?.userId).filter((id): id is string => Boolean(id))))
      const normalized = query.trim().toLocaleLowerCase('ru-RU')
      return [...participants, replacementCandidate]
        .filter((participant) => !existingIds.has(participant.userId) && participant.displayName.toLocaleLowerCase('ru-RU').includes(normalized))
        .map((participant): DirectoryUser => ({ id: participant.userId, displayName: participant.displayName }))
    },
    async problems() { return problems },
    async bracket() { return bracket },
    async generateBracket() { return bracket },
    async savePairings(_id: string, pairings: FirstRoundPairing[], _reason: string, key: string) {
      if (commandKeys.has(key)) return bracket
      const userIds = pairings.flatMap((pairing) => [pairing.leftUserId, pairing.rightUserId]).filter((value): value is string => Boolean(value))
      const expected = rosterParticipants.map((participant) => participant.userId)
      const positions = pairings.map((pairing) => pairing.position).sort((left, right) => left - right)
      const expectedPositions = Array.from({ length: bracket.bracketSize / 2 }, (_, index) => index)
      if (pairings.length !== expectedPositions.length || positions.some((position, index) => position !== expectedPositions[index]) || userIds.length !== expected.length || new Set(userIds).size !== expected.length || expected.some((id) => !userIds.includes(id)) || pairings.some((pairing) => !pairing.leftUserId && !pairing.rightUserId)) {
        throw new ApiError('Каждый замороженный участник должен встретиться ровно один раз.', 409, 'invalid_pairings')
      }
      pairings.forEach((pairing) => {
        const match = bracket.matches.find((candidate) => candidate.roundIndex === 0 && candidate.position === pairing.position)
        if (!match) return
        const left = participants.find((participant) => participant.userId === pairing.leftUserId) ?? null
        const right = participants.find((participant) => participant.userId === pairing.rightUserId) ?? null
        match.kind = left && right ? 'MATCH' : 'BYE'
        match.status = left && right ? 'READY' : 'BYE'
        match.winner = left && !right ? left : right && !left ? right : null
        match.slots = [makeSlot(0, left ? 'PLAYER' : 'BYE', left), makeSlot(1, right ? 'PLAYER' : 'BYE', right)]
      })
      for (const downstream of bracket.matches.filter((candidate) => candidate.roundIndex > 0)) {
        downstream.slots = downstream.slots.map((slot) => {
          const source = bracket.matches.find((candidate) => candidate.id === slot.sourceMatchId)
          const advanced = source?.kind === 'BYE' ? source.winner : null
          return makeSlot(slot.index, advanced ? 'PLAYER' : 'WAITING', advanced, slot.sourceMatchId)
        }) as [BracketSlot, BracketSlot]
        downstream.status = downstream.slots.every((slot) => slot.participant) ? 'READY' : 'WAITING'
      }
      const activeMatch = bracket.matches.find((candidate) => candidate.roundIndex === 0 && candidate.kind === 'MATCH')
      if (activeMatch && currentMatch) {
        const activePlayers = activeMatch.slots.flatMap((slot) => slot.participant ? [slot.participant] : [])
        if (activePlayers.length === 2) {
          currentMatch = {
            ...currentMatch,
            matchId: activeMatch.id,
            players: makePlayers(currentMatch.problemVersions, activePlayers),
            status: 'READY',
            readyUserIds: [],
          }
        }
      }
      commandKeys.add(key)
      return bracket
    },
    async match(id) { return requireMatch(id) },
    async updateConfig(id: string, input: MatchConfigInput, key: string) {
      const match = requireMatch(id)
      if (!commandKeys.has(key)) {
        const chosenProblems = readyVersions.filter((problem) => input.problemIds.includes(problem.problemId))
        if (chosenProblems.length !== input.problemIds.length || chosenProblems.length === 0) {
          throw new ApiError('Выберите задачи из готового синтетического каталога.', 400, 'invalid_problem_set')
        }
        tournament.startMode = input.startMode
        tournament.matchDurationSec = input.matchDurationSec
        currentMatch = {
          ...match,
          allowedDurationMs: input.matchDurationSec * 1000,
          remainingMs: input.matchDurationSec * 1000,
          startMode: input.startMode,
          problemVersions: chosenProblems,
          players: makePlayers(chosenProblems, match.players.map((player) => ({
            id: player.userId,
            userId: player.userId,
            displayName: player.displayName,
            seed: null,
          }))),
        }
        commandKeys.add(key)
      }
      return currentMatch ?? match
    },
    async action(id: string, input: MatchActionInput, key: string) {
      requireMatch(id)
      if (commandKeys.has(key)) return currentMatch as MatchView
      const result = applyAction(input)
      commandKeys.add(key)
      return result
    },
    async simulateReady(id: string, userId: string) {
      const match = requireMatch(id)
      const readyUserIds = match.readyUserIds.includes(userId) ? match.readyUserIds : [...match.readyUserIds, userId]
      currentMatch = { ...match, readyUserIds }
      if (currentMatch.startMode === 'both_ready' && currentMatch.players.every((player) => readyUserIds.includes(player.userId))) {
        currentMatch = { ...currentMatch, status: 'RUNNING', serverNow: new Date().toISOString() }
      }
      syncBracketStatus(currentMatch)
      return currentMatch
    },
  }
}
