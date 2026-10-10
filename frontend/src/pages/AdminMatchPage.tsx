import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import {
  ApiError,
  type Bracket,
  type DirectoryUser,
  type FirstRoundPairing,
  type MatchActionInput,
  type MatchConfigInput,
  type MatchView,
  type ProblemCatalogEntry,
  type RosterEntry,
  type Tournament,
} from '../api/client'
import { resolveMatchAdminTransport, type MatchAdminTransport } from '../matches/transport'
import './Admin.css'

function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Не удалось выполнить запрос. Попробуйте ещё раз.'
}

function commandKey(cache: Map<string, string>, operation: string, payload: unknown): string {
  const fingerprint = `${operation}:${JSON.stringify(payload)}`
  const previous = cache.get(fingerprint)
  if (previous) return previous
  const next = crypto.randomUUID()
  cache.set(fingerprint, next)
  return next
}

type BracketMatch = Bracket['matches'][number]

// A match with both players but no saved run answers 409; the organizer must still be able to configure it.
function isUnconfiguredMatchError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409 && error.code === 'match_run_not_configured'
}

function hasBothPlayers(entry: BracketMatch): boolean {
  return entry.slots.every((slot) => slot.participant)
}

function firstRoundPairings(bracket: Bracket): FirstRoundPairing[] {
  const matches = bracket.matches.filter((match) => match.roundIndex === 0).sort((left, right) => left.position - right.position)
  return Array.from({ length: bracket.bracketSize / 2 }, (_, position) => {
    const match = matches.find((candidate) => candidate.position === position)
    return {
      position,
      leftUserId: match?.slots[0].participant?.userId ?? null,
      rightUserId: match?.slots[1].participant?.userId ?? null,
    }
  })
}

function roundName(index: number, total: number): string {
  if (index === total - 1) return 'Финал'
  if (index === total - 2) return 'Полуфиналы'
  if (index === total - 3) return 'Четвертьфиналы'
  return `Раунд ${index + 1}`
}

function statusName(status: string): string {
  const names: Record<string, string> = {
    WAITING: 'Ожидание', READY: 'Готов к старту', RUNNING: 'Идёт', PAUSED: 'Пауза',
    FINALIZING: 'Проверяем результаты', FINISHED: 'Завершён', TIED: 'Равенство',
    SUPERSEDED: 'Переигран', BYE: 'Свободный проход',
  }
  return names[status] ?? status
}

function slotName(slot: Bracket['matches'][number]['slots'][number]): string {
  if (slot.participant) return slot.participant.displayName
  if (slot.resolution === 'BYE') return 'BYE · свободный проход'
  if (slot.resolution === 'WAITING') return 'Ожидает победителя'
  return 'Участник не назначен'
}

function formatClock(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(totalSeconds / 60).toString().padStart(2, '0')}:${(totalSeconds % 60).toString().padStart(2, '0')}`
}

export function AdminMatchPage() {
  const { tournamentId = '' } = useParams()
  const [transport, setTransport] = useState<MatchAdminTransport | null>(null)
  const [tournament, setTournament] = useState<Tournament | null>(null)
  const [roster, setRoster] = useState<RosterEntry[]>([])
  const [problems, setProblems] = useState<ProblemCatalogEntry[]>([])
  const [bracket, setBracket] = useState<Bracket | null>(null)
  const [match, setMatch] = useState<MatchView | null>(null)
  const [unconfigured, setUnconfigured] = useState<BracketMatch | null>(null)
  const [pairings, setPairings] = useState<FirstRoundPairing[]>([])
  const [pairingReason, setPairingReason] = useState('')
  const [selectedProblemIds, setSelectedProblemIds] = useState<string[]>([])
  const [duration, setDuration] = useState('1200')
  const [startMode, setStartMode] = useState<'manual' | 'both_ready'>('manual')
  const [reason, setReason] = useState('')
  const [extensionSeconds, setExtensionSeconds] = useState('60')
  const [winnerUserId, setWinnerUserId] = useState('')
  const [replacementOldId, setReplacementOldId] = useState('')
  const [replacementNewId, setReplacementNewId] = useState('')
  const [replacementSearch, setReplacementSearch] = useState('')
  const [replacementCandidates, setReplacementCandidates] = useState<DirectoryUser[]>([])
  const [replacementSearchLoading, setReplacementSearchLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [pageError, setPageError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const commandKeys = useRef(new Map<string, string>())
  const selectedMatchId = useRef<string | null>(null)

  const loadData = useCallback(async (source: MatchAdminTransport) => {
    setPageError(null)
    const [nextTournament, nextRoster, nextProblems] = await Promise.all([
      source.tournament(tournamentId),
      source.roster(tournamentId),
      source.problems(),
    ])
    let nextBracket: Bracket | null = null
    try {
      nextBracket = await source.bracket(tournamentId)
    } catch (error) {
      // The tournament was just read successfully, so a 404 on its bracket means "not generated yet".
      // Backend currently answers with the generic `not_found` code instead of the contract `bracket_not_found`.
      const isMissingBracket = error instanceof ApiError
        && error.status === 404
        && ['bracket_not_found', 'bracket_not_generated', 'not_found'].includes(error.code ?? '')
      if (!isMissingBracket) throw error
    }
    const sortedRoster = nextRoster.filter((entry) => entry.status === 'ACTIVE').sort((left, right) => {
      if (left.seed === null && right.seed !== null) return 1
      if (left.seed !== null && right.seed === null) return -1
      if (left.seed !== right.seed) return (left.seed ?? 0) - (right.seed ?? 0)
      return left.userId.localeCompare(right.userId)
    })
    const roundOneMatches = nextBracket?.matches
      .filter((candidate) => candidate.kind === 'MATCH' && candidate.roundIndex === 0 && hasBothPlayers(candidate))
      .sort((left, right) => left.position - right.position) ?? []
    const playable = roundOneMatches.find((candidate) => candidate.id === selectedMatchId.current) ?? roundOneMatches[0]
    let nextMatch: MatchView | null = null
    let nextUnconfigured: BracketMatch | null = null
    if (playable) {
      try {
        nextMatch = await source.match(playable.id)
      } catch (error) {
        if (!isUnconfiguredMatchError(error)) throw error
        nextUnconfigured = playable
      }
    }
    selectedMatchId.current = playable?.id ?? null
    setTournament(nextTournament)
    setRoster(sortedRoster)
    setProblems(nextProblems)
    setBracket(nextBracket)
    setMatch(nextMatch)
    setUnconfigured(nextUnconfigured)
    setPairings(nextBracket ? firstRoundPairings(nextBracket) : [])
    setSelectedProblemIds(nextMatch?.problemVersions.map((problem) => problem.problemId) ?? [])
    setDuration(String(nextMatch ? Math.round(nextMatch.allowedDurationMs / 1000) : nextTournament.matchDurationSec))
    setStartMode(nextMatch?.startMode ?? nextTournament.startMode)
    if (nextMatch?.players[0]) {
      setWinnerUserId(nextMatch.players[0].userId)
      setReplacementOldId(nextMatch.players[0].userId)
    }
  }, [tournamentId])

  const reload = useCallback(async () => {
    if (!transport) return
    setLoading(true)
    try {
      await loadData(transport)
    } catch (error) {
      setPageError(messageFor(error))
    } finally {
      setLoading(false)
    }
  }, [loadData, transport])

  useEffect(() => {
    let active = true
    void resolveMatchAdminTransport(window.location.search).then(async (source) => {
      if (!active) return
      setTransport(source)
      await loadData(source)
    }).catch((error: unknown) => {
      if (active) setPageError(messageFor(error))
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [loadData])

  const rounds = useMemo(() => {
    if (!bracket) return []
    const maxRound = Math.max(...bracket.matches.map((entry) => entry.roundIndex))
    return Array.from({ length: maxRound + 1 }, (_, index) => bracket.matches
      .filter((entry) => entry.roundIndex === index)
      .sort((left, right) => left.position - right.position))
  }, [bracket])
  const hasStarted = useMemo(
    () => Boolean(bracket?.matches.some((entry) => !['WAITING', 'READY', 'BYE'].includes(entry.status))),
    [bracket],
  )
  const expectedUserIds = roster.map((entry) => entry.userId)
  const pairedUserIds = pairings.flatMap((pairing) => [pairing.leftUserId, pairing.rightUserId]).filter((value): value is string => Boolean(value))
  const matchHasStarted = Boolean(match && !['WAITING', 'READY'].includes(match.status))
  const isDevelopmentScenario = import.meta.env.DEV && transport?.mode === 'development-scenario'
  const bracketUserIds = useMemo(() => new Set(bracket?.matches.flatMap((entry) => entry.slots
    .map((slot) => slot.participant?.userId)
    .filter((userId): userId is string => Boolean(userId))) ?? []), [bracket])
  const availableReplacementCandidates = replacementCandidates.filter((candidate) => !bracketUserIds.has(candidate.id))
  const configTarget = match
    ? { id: match.matchId, names: match.players.map((player) => player.displayName), status: match.status }
    : unconfigured
      ? { id: unconfigured.id, names: unconfigured.slots.map((slot) => slot.participant?.displayName ?? 'Участник'), status: 'WAITING' as const }
      : null
  const pairingsValid = Boolean(bracket)
    && pairings.length === (bracket?.bracketSize ?? 0) / 2
    && pairedUserIds.length === expectedUserIds.length
    && new Set(pairedUserIds).size === pairedUserIds.length
    && expectedUserIds.every((userId) => pairedUserIds.includes(userId))
    && pairings.every((pairing) => pairing.leftUserId || pairing.rightUserId)
  const selectedMatchReadyUsers = match?.readyUserIds.length ?? 0

  async function perform(operation: string, payload: unknown, action: (key: string) => Promise<void>) {
    const key = commandKey(commandKeys.current, operation, payload)
    setBusy(true)
    setActionError(null)
    setActionMessage(null)
    try {
      await action(key)
      commandKeys.current.delete(`${operation}:${JSON.stringify(payload)}`)
      await reload()
      setActionMessage('Изменения сохранены.')
    } catch (error) {
      setActionError(messageFor(error))
    } finally {
      setBusy(false)
    }
  }

  async function generateBracket() {
    if (!transport || !tournament) return
    const payload = { tournamentId: tournament.id, seedingMode: 'manual' }
    await perform('bracket-generate', payload, async (key) => {
      await transport.generateBracket(tournament.id, key)
    })
  }

  async function savePairings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!transport || !tournament || !pairingsValid) return
    const cleanReason = pairingReason.trim()
    if (cleanReason.length < 3) {
      setActionError('Укажите причину изменения пар (не менее 3 символов).')
      return
    }
    const payload = { pairings, reason: cleanReason }
    await perform('bracket-pairings', payload, async (key) => {
      await transport.savePairings(tournament.id, pairings, cleanReason, key)
    })
  }

  async function saveConfig(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!transport || !configTarget) return
    const seconds = Number(duration)
    if (!Number.isInteger(seconds) || seconds < 60 || seconds > 7200) {
      setActionError('Длительность должна быть целым числом от 60 до 7200 секунд.')
      return
    }
    if (!selectedProblemIds.length) {
      setActionError('Выберите хотя бы одну готовую задачу.')
      return
    }
    const input: MatchConfigInput = {
      problemIds: selectedProblemIds,
      matchDurationSec: seconds,
      startMode,
    }
    await perform('match-config', { matchId: configTarget.id, input }, async (key) => {
      await transport.updateConfig(configTarget.id, input, key)
    })
  }

  async function submitAction(input: MatchActionInput) {
    if (!transport || !match) return
    if ('reason' in input && input.reason.trim().length < 3) {
      setActionError('Укажите причину действия (не менее 3 символов).')
      return
    }
    const payload = { matchId: match.matchId, input }
    await perform(`match-action:${input.name}`, payload, async (key) => {
      await transport.action(match.matchId, input, key)
    })
  }

  async function simulateReady(userId: string) {
    if (!transport?.simulateReady || !match) return
    setBusy(true)
    setActionError(null)
    try {
      await transport.simulateReady(match.matchId, userId)
      await reload()
    } catch (error) {
      setActionError(messageFor(error))
    } finally {
      setBusy(false)
    }
  }

  async function openMatch(matchId: string) {
    if (!transport) return
    setActionError(null)
    try {
      const nextMatch = await transport.match(matchId)
      selectedMatchId.current = matchId
      setUnconfigured(null)
      setMatch(nextMatch)
      setSelectedProblemIds(nextMatch.problemVersions.map((problem) => problem.problemId))
      setDuration(String(Math.round(nextMatch.allowedDurationMs / 1000)))
      setStartMode(nextMatch.startMode)
      if (nextMatch.players[0]) {
        setWinnerUserId(nextMatch.players[0].userId)
        setReplacementOldId(nextMatch.players[0].userId)
      }
    } catch (error) {
      const entry = bracket?.matches.find((candidate) => candidate.id === matchId)
      if (entry && isUnconfiguredMatchError(error)) {
        selectedMatchId.current = matchId
        setMatch(null)
        setUnconfigured(entry)
        setSelectedProblemIds([])
        if (tournament) {
          setDuration(String(tournament.matchDurationSec))
          setStartMode(tournament.startMode)
        }
        return
      }
      setActionError(messageFor(error))
    }
  }

  async function searchReplacementCandidates() {
    if (!transport || replacementSearch.trim().length < 2) {
      setActionError('Введите не менее двух символов имени участника.')
      return
    }
    setReplacementSearchLoading(true)
    setActionError(null)
    try {
      const candidates = await transport.directory(replacementSearch.trim())
      setReplacementCandidates(candidates.filter((candidate) => !bracketUserIds.has(candidate.id)))
      setReplacementNewId('')
      if (!candidates.length) setActionMessage('Не найден свободный активный участник.')
    } catch (error) {
      setActionError(messageFor(error))
    } finally {
      setReplacementSearchLoading(false)
    }
  }

  function changePairing(position: number, side: 'leftUserId' | 'rightUserId', value: string) {
    setPairings((current) => current.map((pairing) => pairing.position === position
      ? { ...pairing, [side]: value || null }
      : pairing))
  }

  if (loading) return <div className="state-card" role="status"><span>Загружаем сетку и настройки матча…</span></div>
  if (pageError) {
    return <section className="page-section management-page">
      <div className="breadcrumbs"><Link to="/admin">Турниры</Link><span>/</span><span>Сетка и матчи</span></div>
      <div className="state-card state-card-error" role="alert"><span>{pageError}</span><button className="text-button" type="button" onClick={() => void reload()}>Повторить</button></div>
      {transport?.mode === 'http' && <p className="inline-note">Match/bracket endpoint недоступен на подключённом сервере. Dev-сценарий можно открыть по отдельной ссылке в development-сборке.</p>}
    </section>
  }
    if (!transport || !tournament) return null

  return <section className="page-section management-page match-admin-page">
    <div className="breadcrumbs"><Link to="/admin">Турниры</Link><span>/</span><Link to={`/admin/tournaments/${tournamentId}`}>{tournament.title}</Link><span>/</span><span>Сетка и матчи</span></div>
    <div className="management-heading">
      <div>
        <p className="eyebrow">Панель организатора</p>
        <h1>Сетка и матчи</h1>
        <p>{tournament.title} · {roster.length} активных участников · {bracket ? `сетка ${bracket.bracketSize}` : 'сетка не создана'}</p>
      </div>
      <div className="management-actions"><button className="button button-outline" type="button" disabled={busy} onClick={() => void reload()}>Обновить</button></div>
    </div>

    {isDevelopmentScenario && <div className="dev-scenario-banner" role="note">
      DEVELOPMENT · синтетические данные и эмуляция команд. Это не сохранённый турнир и не результат судьи.
      <label>Участников в preview
        <select value={String(roster.length)} onChange={(event) => {
          const nextCount = event.target.value
          window.location.search = `?scenario=match-ui&participants=${encodeURIComponent(nextCount)}`
        }}>
          {[2, 3, 4, 5].map((count) => <option key={count} value={count}>{count}</option>)}
        </select>
      </label>
    </div>}

    <section className="management-panel" aria-labelledby="bracket-heading">
      <div className="panel-heading"><div><h2 id="bracket-heading">Турнирная сетка</h2><p>{bracket ? `Сетка заморожена ${new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(bracket.rosterFrozenAt))}. ` : 'Сетка ещё не создана. Генерация одновременно фиксирует состав. '}BYE — свободный проход; WAITING — ещё нет победителя исходного матча.</p></div><button className="button button-outline button-small" type="button" disabled={busy || roster.length < 2 || hasStarted} onClick={() => void generateBracket()}>{bracket ? 'Сверить генерацию сетки' : 'Сформировать сетку'}</button></div>
      {bracket ? <div className="bracket-rounds">
        {rounds.map((round, index) => <section className="bracket-round" key={`round-${index}`} aria-label={roundName(index, rounds.length)}>
          <h3>{roundName(index, rounds.length)}</h3>
          <div className="bracket-match-list">
            {round.map((entry) => <article className="bracket-match-card" key={entry.id}>
              <div className="bracket-match-heading"><strong>{entry.key}</strong><span className={`match-status match-status-${entry.status.toLowerCase()}`}>{statusName(entry.status)}</span></div>
              {entry.slots.map((slot) => <div className={`bracket-slot ${slot.resolution.toLowerCase()}`} key={slot.index}><span>{slotName(slot)}</span>{slot.participant?.seed !== null && slot.participant && <small>Посев {slot.participant.seed}</small>}</div>)}
              {entry.winner && <p className="inline-note">Проходит дальше: {entry.winner.displayName}</p>}
              {entry.kind === 'MATCH' && entry.roundIndex === 0 && hasBothPlayers(entry) && (!isDevelopmentScenario || match?.matchId === entry.id) && <button className="text-button" type="button" disabled={busy} onClick={() => void openMatch(entry.id)}>Открыть матч</button>}
            </article>)}
          </div>
        </section>)}
      </div> : <div className="empty-state compact-empty"><h3>Сетка не создана</h3><p>Проверьте состав и сформируйте сетку из замороженного списка.</p></div>}
    </section>

    {bracket && <section className="management-panel">
      <div className="panel-heading"><div><h2>Пары первого раунда</h2><p>Отправляется весь раунд одной командой. Каждый участник должен встретиться ровно один раз.</p></div></div>
      {hasStarted && <div className="notice notice-error" role="status">Первый запуск уже начался. Изменение пар закрыто, история матчей сохраняется.</div>}
      <form className="match-form" onSubmit={(event) => void savePairings(event)}>
        <div className="pairing-grid">
          {pairings.map((pairing) => <div className="pairing-row" key={pairing.position}>
            <strong>Пара {pairing.position + 1}</strong>
            <label>Левая сторона<select aria-label={`Пара ${pairing.position + 1}, левая сторона`} value={pairing.leftUserId ?? ''} disabled={hasStarted || busy} onChange={(event) => changePairing(pairing.position, 'leftUserId', event.target.value)}>
              <option value="">BYE</option>{roster.map((entrant) => <option key={entrant.userId} value={entrant.userId}>{entrant.displayName}{entrant.seed ? ` · #${entrant.seed}` : ''}</option>)}
            </select></label>
            <label>Правая сторона<select aria-label={`Пара ${pairing.position + 1}, правая сторона`} value={pairing.rightUserId ?? ''} disabled={hasStarted || busy} onChange={(event) => changePairing(pairing.position, 'rightUserId', event.target.value)}>
              <option value="">BYE</option>{roster.map((entrant) => <option key={entrant.userId} value={entrant.userId}>{entrant.displayName}{entrant.seed ? ` · #${entrant.seed}` : ''}</option>)}
            </select></label>
          </div>)}
        </div>
        <label className="form-field">Причина ручной перестановки<input value={pairingReason} onChange={(event) => setPairingReason(event.target.value)} minLength={3} maxLength={500} disabled={hasStarted || busy} /></label>
        {(!pairingsValid && !hasStarted) && <p className="inline-note" role="status">Состав должен совпадать с замороженным roster; повтор участника и пара из двух BYE запрещены.</p>}
        <div className="form-actions"><button className="button" type="submit" disabled={busy || hasStarted || !pairingsValid}>Сохранить полный раунд</button></div>
      </form>
    </section>}

    {configTarget && <>
      <section className="management-panel" aria-labelledby="config-heading">
        <div className="panel-heading"><div><h2 id="config-heading">Настройки матча · {configTarget.names.join(' — ')}</h2><p>Правила и версии задач сохраняются в snapshot матча. Условия не загружаются и не показываются до старта.</p></div><span className={`match-status match-status-${configTarget.status.toLowerCase()}`}>{statusName(configTarget.status)}</span></div>
        <form className="match-form" onSubmit={(event) => void saveConfig(event)}>
          <fieldset className="problem-picker" disabled={matchHasStarted || busy}>
            <legend>Готовые задачи · одинаковый набор для обоих</legend>
            {problems.length ? problems.map((problem) => <label className="problem-choice" key={`${problem.problemId}:${problem.version}`}>
              <input type="checkbox" checked={selectedProblemIds.includes(problem.problemId)} disabled={problem.readiness !== 'READY'} onChange={(event) => setSelectedProblemIds((current) => event.target.checked ? [...current, problem.problemId] : current.filter((id) => id !== problem.problemId))} />
              <span><strong>{problem.label}</strong><small>{problem.version} · {problem.readiness === 'READY' ? 'готова · условие скрыто до старта' : 'не готова для матча'}</small></span>
            </label>) : <p className="inline-note">Каталог не вернул готовые версии задач.</p>}
          </fieldset>
          <div className="form-grid">
            <label className="form-field"><span>Длительность, секунд</span><input type="number" min="60" max="7200" step="1" value={duration} disabled={matchHasStarted || busy} onChange={(event) => setDuration(event.target.value)} /></label>
            <label className="form-field"><span>Запуск</span><select value={startMode} disabled={matchHasStarted || busy} onChange={(event) => setStartMode(event.target.value as 'manual' | 'both_ready')}><option value="manual">Вручную организатором</option><option value="both_ready">После готовности обоих</option></select></label>
            <label className="form-field"><span>Штраф за неверную попытку, секунд</span><input type="number" min="0" max="7200" value={tournament.scoringRule.wrongAttemptPenaltySec} disabled /></label>
            <label className="form-field"><span>Равенство в финале</span><input value="Переигровка" disabled /></label>
          </div>
          <div className="form-actions"><button className="button" type="submit" disabled={busy || matchHasStarted || !problems.some((problem) => problem.readiness === 'READY')}>Сохранить настройки</button></div>
        </form>
      </section>

      {match && <section className="management-panel" aria-labelledby="match-ops-heading">
        <div className="panel-heading"><div><h2 id="match-ops-heading">Матч и действия организатора</h2><p>Серверное время {new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'medium' }).format(new Date(match.serverNow))} · прошло {formatClock(match.elapsedMs)} · осталось {formatClock(match.remainingMs)} · событие {match.lastEventId}</p></div></div>
        <div className="readiness-grid">
          {match.players.map((player) => <article className="readiness-card" key={player.userId}><strong>{player.displayName}</strong><span>{match.readyUserIds.includes(player.userId) ? 'Готов' : 'Ожидает готовности'}</span><small>{player.solvedCount} решено · штраф {Math.floor(player.penaltyMs / 1000)} сек.</small></article>)}
        </div>
        {match.startMode === 'both_ready' && match.status === 'READY' && <p className="notice" role="status">Автозапуск ждёт готовность обоих участников: {selectedMatchReadyUsers}/2.</p>}
        {match.startMode === 'manual' && match.status === 'READY' && <button className="button" type="button" disabled={busy} onClick={() => void submitAction({ name: 'start' })}>Запустить матч</button>}
        {isDevelopmentScenario && transport.simulateReady && match.startMode === 'both_ready' && match.status === 'READY' && <div className="dev-ready-tools"><strong>Сценарий разработки · эмуляция готовности</strong>{match.players.map((player) => <button className="button button-outline button-small" type="button" key={player.userId} disabled={busy || match.readyUserIds.includes(player.userId)} onClick={() => void simulateReady(player.userId)}>Готов: {player.displayName}</button>)}</div>}
        {match.status === 'RUNNING' && <button className="button button-outline" type="button" disabled={busy} onClick={() => void submitAction({ name: 'pause', reason: reason.trim() })}>Пауза</button>}
        {match.status === 'PAUSED' && <button className="button button-outline" type="button" disabled={busy} onClick={() => void submitAction({ name: 'resume', reason: reason.trim() })}>Продолжить</button>}
        {['RUNNING', 'PAUSED'].includes(match.status) && <div className="match-action-row">
          <label className="form-field"><span>Продлить, секунд</span><input type="number" min="1" max="7200" value={extensionSeconds} onChange={(event) => setExtensionSeconds(event.target.value)} /></label>
          <button className="button button-outline" type="button" disabled={busy} onClick={() => void submitAction({ name: 'extend', seconds: Number(extensionSeconds), reason: reason.trim() })}>Продлить время</button>
        </div>}
        {['READY', 'RUNNING', 'PAUSED'].includes(match.status) && <div className="match-action-row">
          <label className="form-field"><span>Техническая победа</span><select value={winnerUserId} onChange={(event) => setWinnerUserId(event.target.value)}>{match.players.map((player) => <option key={player.userId} value={player.userId}>{player.displayName}</option>)}</select></label>
          <button className="button button-outline text-danger" type="button" disabled={busy} onClick={() => void submitAction({ name: 'technical-result', winnerUserId, reason: reason.trim() })}>Зафиксировать решение</button>
        </div>}
        {['FINISHED', 'TIED'].includes(match.status) && <button className="button button-outline" type="button" disabled={busy} onClick={() => void submitAction({ name: 'rematches', reason: reason.trim(), problemIds: match.problemVersions.map((problem) => problem.problemId) })}>Создать переигровку</button>}
        {match.status === 'READY' && <div className="match-action-row">
          <label className="form-field"><span>Кого заменить</span><select value={replacementOldId} onChange={(event) => setReplacementOldId(event.target.value)}>{match.players.map((player) => <option key={player.userId} value={player.userId}>{player.displayName}</option>)}</select></label>
          <label className="form-field"><span>Найти свободного участника</span><input value={replacementSearch} onChange={(event) => setReplacementSearch(event.target.value)} maxLength={120} placeholder="Имя участника" /></label>
          <button className="button button-quiet button-small" type="button" disabled={busy || replacementSearchLoading} onClick={() => void searchReplacementCandidates()}>{replacementSearchLoading ? 'Ищем…' : 'Найти'}</button>
          <label className="form-field"><span>Новый участник</span><select value={replacementNewId} onChange={(event) => setReplacementNewId(event.target.value)}><option value="">Выберите свободного</option>{availableReplacementCandidates.map((entry) => <option key={entry.id} value={entry.id}>{entry.displayName}</option>)}</select></label>
          <button className="button button-outline" type="button" disabled={busy || !replacementNewId} onClick={() => void submitAction({ name: 'replacements', oldUserId: replacementOldId, newUserId: replacementNewId, reason: reason.trim() })}>Заменить до старта</button>
        </div>}
        <label className="form-field match-reason"><span>Причина аудируемого действия</span><textarea rows={3} maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Кратко опишите основание вмешательства" /></label>
        <div className="match-task-statuses"><h3>Статус задач участников</h3>{match.players.map((player) => <div className="match-player-tasks" key={player.userId}><strong>{player.displayName}</strong><ul>{player.tasks.map((task) => <li key={task.problemId}>{task.label}: {task.status} · попыток {task.attempts}{task.lastVerdict ? ` · ${task.lastVerdict}` : ''}</li>)}</ul></div>)}</div>
      </section>}
    </>}
    {!configTarget && <div className="state-card" role="status">Нет матча первого раунда, доступного для управления.</div>}
    {actionError && <div className="state-card state-card-error" role="alert">{actionError}</div>}
    {actionMessage && <div className="state-card" role="status">{actionMessage}</div>}
  </section>
}
