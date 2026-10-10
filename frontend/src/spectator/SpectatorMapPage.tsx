import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, SetStateAction } from 'react'
import { Link, useLocation, useParams } from 'react-router'
import { ApiError } from '../api/client'
import { applyPublicEvent, applyPublicSnapshot, applyResyncNotice, createSpectatorState, failSpectatorProtocol, requestPublicResync, setSpectatorConnection } from './reducer'
import { resolveSpectatorTransport, spectatorConnectionLabel, type SpectatorTransport } from './transport'
import { PublicProtocolError, type PublicBracketMatch, type PublicBracketSnapshot, type PublicMatchSnapshot, type PublicPlayerState, type PublicTaskState, type SpectatorState } from './types'
import { validatePublicBracket, validatePublicSnapshot } from './validation'
import './spectator.css'

interface SpectatorMapPageProps {
  transport?: SpectatorTransport
}

function messageFor(error: unknown): string {
  if (error instanceof ApiError || error instanceof PublicProtocolError) return error.message
  if (error instanceof Error) return error.message
  return 'Не удалось загрузить публичную карту матча.'
}

function statusName(status: PublicBracketMatch['status']): string {
  const labels: Record<PublicBracketMatch['status'], string> = {
    WAITING: 'Ожидает', READY: 'Готов', RUNNING: 'Идёт', PAUSED: 'Пауза',
    FINALIZING: 'Проверка', FINISHED: 'Завершён', TIED: 'Переигровка', SUPERSEDED: 'Новый запуск', BYE: 'Без матча',
  }
  return labels[status]
}

function taskStatusName(status: PublicTaskState['status']): string {
  if (status === 'SOLVED') return 'решена'
  if (status === 'ATTEMPTED') return 'есть попытки'
  return 'не начата'
}

function formatClock(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const shortMinutes = minutes % 60
  const clock = `${shortMinutes.toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`
  return hours > 0 ? `${hours.toString().padStart(2, '0')}:${clock}` : clock
}

function scoringExplanation(snapshot: PublicMatchSnapshot): string {
  const labels: Record<string, string> = {
    solved_desc: 'больше решённых задач',
    penalty_asc: 'меньше штраф',
    last_accepted_asc: 'раньше принято решение',
  }
  const order = snapshot.scoringRule.order.map((rule) => labels[rule]).filter((label): label is string => Boolean(label))
  if (order.length === 0) return 'Лидер определяется опубликованным правилом турнира.'
  const penalty = snapshot.scoringRule.order.includes('penalty_asc')
    ? ` За неверную попытку добавляется ${snapshot.scoringRule.wrongAttemptPenaltySec} с штрафа.`
    : ''
  return `Лидер определяется так: ${order.join(' → ')}.${penalty}`
}

function safeRouteSearch(search: string, projector: boolean): string {
  const source = new URLSearchParams(search)
  const result = new URLSearchParams()
  for (const key of ['scenario', 'disconnect', 'resync']) {
    const value = source.get(key)
    if (value) result.set(key, value)
  }
  if (projector) result.set('projector', '1')
  const query = result.toString()
  return query ? `?${query}` : ''
}

function chooseMatch(bracket: PublicBracketSnapshot, preferredId: string): PublicBracketMatch | null {
  if (preferredId) return bracket.matches.find((match) => match.id === preferredId) ?? null
  return bracket.matches.find((match) => match.status === 'RUNNING' || match.status === 'PAUSED' || match.status === 'FINALIZING')
    ?? bracket.matches.find((match) => match.status === 'READY')
    ?? bracket.matches[0]
    ?? null
}

function PublicLane({
  player,
  leader,
  totalTasks,
}: {
  player: PublicPlayerState
  leader: boolean
  totalTasks: number
}) {
  const progress = totalTasks === 0 ? 0 : Math.min(1, player.solvedCount / totalTasks)
  const position = Math.max(0, Math.min(100, progress * 100))
  return (
    <article className={`spectator-lane${leader ? ' is-leader' : ''}`} aria-label={`${player.displayName}: ${player.solvedCount} задач, штраф ${formatClock(player.penaltyMs)}`}>
      <div className="spectator-lane-heading">
        <div className="spectator-player-name">
          <span className="spectator-player-marker" aria-hidden="true" />
          <strong>{player.displayName}</strong>
          {leader && <span className="spectator-leader-badge">ЛИДЕР</span>}
        </div>
        <div className="spectator-player-score">
          <strong>{player.solvedCount}</strong><span>решено</span>
          <span className="spectator-score-separator" aria-hidden="true">·</span>
          <span>штраф {formatClock(player.penaltyMs)}</span>
        </div>
      </div>
      <div className="spectator-track-labels" style={{ '--task-count': totalTasks } as CSSProperties} aria-hidden="true">
        <span>СТАРТ</span>
        {player.tasks.map((task) => <span key={task.problemId}>{task.label}</span>)}
        <span>ФИНИШ</span>
      </div>
      <div className="spectator-track" style={{ '--solved-progress': `${position}%` } as CSSProperties}>
        <span className="spectator-track-line" aria-hidden="true" />
        {player.tasks.map((task, index) => {
          const left = totalTasks > 0 ? ((index + 1) / (totalTasks + 1)) * 100 : 50
          return <span key={task.problemId} className={`spectator-checkpoint checkpoint-${task.status.toLowerCase()}`} style={{ left: `${left}%` }} aria-hidden="true" />
        })}
        <span className="spectator-runner" style={{ left: `${position}%` }} aria-hidden="true">{player.displayName.slice(0, 1).toLocaleUpperCase('ru-RU')}</span>
      </div>
      <ol className="spectator-task-grid" aria-label={`Задачи: ${player.displayName}`}>
        {player.tasks.map((task) => (
          <li className={`spectator-task-state task-${task.status.toLowerCase()}`} key={task.problemId}>
            <span className="spectator-task-label">{task.label}</span>
            <span className="spectator-task-result">{taskStatusName(task.status)}</span>
            <span className="spectator-task-attempts">Попытки: {task.attempts}</span>
            <span className="spectator-task-verdict">Последний вердикт: {task.lastVerdict ?? '—'}</span>
          </li>
        ))}
      </ol>
    </article>
  )
}

function BracketNavigation({
  bracket,
  selectedMatchId,
  tournamentId,
  search,
  projector,
}: {
  bracket: PublicBracketSnapshot
  selectedMatchId: string
  tournamentId: string
  search: string
  projector: boolean
}) {
  const rounds = useMemo(() => {
    const grouped = new Map<number, PublicBracketMatch[]>()
    for (const match of bracket.matches) grouped.set(match.roundIndex, [...(grouped.get(match.roundIndex) ?? []), match])
    return [...grouped.entries()].sort(([left], [right]) => left - right)
  }, [bracket.matches])
  return (
    <nav className="spectator-bracket" aria-label="Сетка турнира">
      <div className="spectator-section-heading"><span>СЕТКА</span><strong>{bracket.bracketSize} мест</strong></div>
      <div className="spectator-bracket-rounds">
        {rounds.map(([roundIndex, matches]) => (
          <section className="spectator-round" key={roundIndex} aria-label={`Раунд ${roundIndex + 1}`}>
            <h2>{rounds.length === 1 ? 'Матчи' : `Раунд ${roundIndex + 1}`}</h2>
            {matches.map((match) => (
              <Link
                className={`spectator-bracket-match${match.id === selectedMatchId ? ' is-selected' : ''}`}
                key={match.id}
                to={`/watch/${encodeURIComponent(tournamentId)}/matches/${encodeURIComponent(match.id)}${safeRouteSearch(search, projector)}`}
                aria-current={match.id === selectedMatchId ? 'page' : undefined}
              >
                <span className="spectator-bracket-pairing">
                  <span>{match.slots[0].displayName ?? 'Ожидается участник'}</span>
                  <span>{match.slots[1].displayName ?? 'Ожидается участник'}</span>
                </span>
                <span className={`spectator-bracket-status status-${match.status.toLowerCase()}`}>{statusName(match.status)}</span>
                {match.winnerName && <small>Победитель: {match.winnerName}</small>}
              </Link>
            ))}
          </section>
        ))}
      </div>
    </nav>
  )
}

function animationText(state: SpectatorState, snapshot: PublicMatchSnapshot): string[] {
  return state.animations.map((animation) => {
    if (animation.kind === 'solve') {
      const player = snapshot.players.find((candidate) => candidate.userId === animation.playerId)
      return player ? `${player.displayName} решила задачу ${animation.taskLabel}` : ''
    }
    if (animation.kind === 'overtake') {
      const from = snapshot.players.find((candidate) => candidate.userId === animation.fromUserId)?.displayName
      const to = snapshot.players.find((candidate) => candidate.userId === animation.toUserId)?.displayName
      return from && to ? `${to} вышел вперёд` : ''
    }
    const winner = snapshot.players.find((candidate) => candidate.userId === animation.winnerUserId)?.displayName
    return winner ? `${winner} победил` : ''
  }).filter(Boolean)
}

export function SpectatorMapPage({ transport: injectedTransport }: SpectatorMapPageProps) {
  const { tournamentId = '', matchId: routeMatchId = '' } = useParams()
  const location = useLocation()
  const projector = new URLSearchParams(location.search).get('projector') === '1'
  const [spectator, setSpectator] = useState(createSpectatorState)
  const spectatorRef = useRef(spectator)
  const [bracket, setBracket] = useState<PublicBracketSnapshot | null>(null)
  const [selectedMatchId, setSelectedMatchId] = useState(routeMatchId)
  const [pageError, setPageError] = useState<string | null>(null)
  const [retrySequence, setRetrySequence] = useState(0)
  const [clockRead, setClockRead] = useState<{ runId: string | null; anchorRemainingMs: number; status: string; remainingMs: number } | null>(null)

  const commit = useCallback((update: SetStateAction<SpectatorState>) => {
    const previous = spectatorRef.current
    const next = typeof update === 'function' ? update(previous) : update
    spectatorRef.current = next
    setSpectator(next)
  }, [])

  useEffect(() => {
    let active = true
    let transport: SpectatorTransport | null = null
    let stopStream: () => void = () => undefined
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let staleTimer: ReturnType<typeof setTimeout> | null = null
    let retryAttempt = 0
    let resyncInFlight = false
    let staleReported = false
    let activeMatchId = ''

    const clearReconnectTimer = () => {
      if (reconnectTimer) clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    const clearStaleTimer = () => {
      if (staleTimer) clearTimeout(staleTimer)
      staleTimer = null
    }

    const clearTimers = () => {
      clearReconnectTimer()
      clearStaleTimer()
    }
    const closeStream = () => {
      stopStream()
      stopStream = () => undefined
    }
    const retryConnection = () => {
      if (!active || reconnectTimer) return
      closeStream()
      commit((current) => setSpectatorConnection(current, 'reconnecting'))
      if (!staleReported && !staleTimer) {
        staleTimer = setTimeout(() => {
          staleReported = true
          staleTimer = null
          if (active) commit((current) => setSpectatorConnection(current, 'stale'))
        }, 8_000)
      }
      const delay = Math.min(15_000, 1_000 * (2 ** Math.min(retryAttempt, 4)))
      retryAttempt += 1
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null
        connectStream()
      }, delay)
    }
    const refreshSnapshot = async () => {
      if (!active || !transport || !activeMatchId || resyncInFlight) return
      resyncInFlight = true
      closeStream()
      commit((current) => requestPublicResync(current))
      try {
        const [freshBracketResponse, freshSnapshotResponse] = await Promise.all([
          transport.bracket(tournamentId, activeMatchId),
          transport.snapshot(activeMatchId),
        ])
        const freshBracket = validatePublicBracket(freshBracketResponse)
        const fresh = validatePublicSnapshot(freshSnapshotResponse)
        if (!active) return
        if (freshBracket.tournamentId !== tournamentId || !freshBracket.matches.some((match) => match.id === activeMatchId)) {
          throw new PublicProtocolError('Updated bracket does not include the selected public match.')
        }
        if (fresh.matchId !== activeMatchId) throw new PublicProtocolError('Snapshot does not match the selected public match.')
        const next = applyPublicSnapshot(spectatorRef.current, fresh)
        if (next.needsResync) throw new PublicProtocolError('The refreshed public snapshot is behind the accepted event cursor.')
        setBracket(freshBracket)
        commit(next)
        retryAttempt = 0
        connectStream()
      } catch (error) {
        if (active && error instanceof PublicProtocolError) {
          closeStream()
          commit((current) => failSpectatorProtocol(current, error))
        } else if (active) retryConnection()
      } finally {
        resyncInFlight = false
      }
    }
    const handleEvent = (event: unknown) => {
      if (!active) return
      const next = applyPublicEvent(spectatorRef.current, event)
      commit(next)
      if (next.connection === 'unavailable') {
        closeStream()
      } else if (next.needsResync) {
        void refreshSnapshot()
      }
    }
    function connectStream() {
      if (!active || !transport || !activeMatchId) return
      clearReconnectTimer()
      closeStream()
      commit((current) => setSpectatorConnection(current, 'connecting'))
      try {
        stopStream = transport.subscribe(activeMatchId, spectatorRef.current.lastEventId, {
          onOpen() {
            if (!active) return
            retryAttempt = 0
            staleReported = false
            clearTimers()
            commit((current) => setSpectatorConnection(current, 'live'))
          },
          onEvent: handleEvent,
          onResync(notice) {
            if (!active) return
            commit((current) => applyResyncNotice(current, notice))
            void refreshSnapshot()
          },
          onError: retryConnection,
        })
      } catch {
        retryConnection()
      }
    }

    async function load() {
      clearTimers()
      closeStream()
      const empty = createSpectatorState()
      spectatorRef.current = empty
      setSpectator(empty)
      setBracket(null)
      setSelectedMatchId(routeMatchId)
      setPageError(null)
      try {
        transport = injectedTransport ?? await resolveSpectatorTransport(location.search)
        if (!active) return
        const publicBracket = validatePublicBracket(await transport.bracket(tournamentId, routeMatchId || undefined))
        if (publicBracket.tournamentId !== tournamentId) throw new PublicProtocolError('Bracket does not match the requested tournament.')
        const chosen = chooseMatch(publicBracket, routeMatchId)
        if (!chosen) throw new PublicProtocolError(routeMatchId
          ? 'Выбранный матч отсутствует в публичной сетке.'
          : 'В публичной сетке пока нет матчей.')
        activeMatchId = chosen.id
        const snapshot = validatePublicSnapshot(await transport.snapshot(chosen.id))
        if (!active) return
        if (snapshot.matchId !== chosen.id) throw new PublicProtocolError('Snapshot does not match the bracket match.')
        setBracket(publicBracket)
        setSelectedMatchId(chosen.id)
        commit((current) => applyPublicSnapshot(current, snapshot))
        connectStream()
      } catch (error) {
        if (!active) return
        setPageError(messageFor(error))
        commit((current) => failSpectatorProtocol(current, error))
      }
    }
    void load()

    return () => {
      active = false
      clearTimers()
      closeStream()
    }
  }, [commit, injectedTransport, location.search, retrySequence, routeMatchId, tournamentId])

  const hasSnapshot = spectator.snapshot !== null
  const snapshotRemainingMs = spectator.snapshot?.remainingMs ?? 0
  const snapshotStatus = spectator.snapshot?.status ?? 'WAITING'
  const snapshotRunId = spectator.snapshot?.runId ?? null

  useEffect(() => {
    if (!hasSnapshot) return undefined
    const anchor = performance.now()
    const updateTimer = () => setClockRead({
      runId: snapshotRunId,
      anchorRemainingMs: snapshotRemainingMs,
      status: snapshotStatus,
      remainingMs: Math.max(0, snapshotRemainingMs - (snapshotStatus === 'RUNNING' ? performance.now() - anchor : 0)),
    })
    const timer = setInterval(updateTimer, 250)
    return () => clearInterval(timer)
  }, [hasSnapshot, snapshotRemainingMs, snapshotStatus, snapshotRunId])

  const snapshot = spectator.snapshot
  const clockIsCurrent = snapshot && clockRead?.runId === snapshot.runId
    && clockRead.anchorRemainingMs === snapshot.remainingMs
    && clockRead.status === snapshot.status
  const remainingMs = clockIsCurrent ? clockRead.remainingMs : snapshot?.remainingMs ?? 0
  const currentWinnerName = snapshot?.players.find((player) => player.userId === snapshot.winnerUserId)?.displayName ?? null
  const displayBracket = bracket && snapshot ? {
    ...bracket,
    matches: bracket.matches.map((match) => match.id === selectedMatchId
      ? { ...match, status: snapshot.status, winnerName: currentWinnerName }
      : match),
  } : bracket
  const activeMatch = displayBracket?.matches.find((match) => match.id === selectedMatchId) ?? null
  const leaderName = snapshot?.players.find((player) => player.userId === snapshot.leaderUserId)?.displayName ?? null
  const winnerName = snapshot?.players.find((player) => player.userId === snapshot.winnerUserId)?.displayName ?? null
  const announcement = snapshot ? animationText(spectator, snapshot) : []
  const taskCount = snapshot?.players[0]?.tasks.length ?? 0
  const search = safeRouteSearch(location.search, projector)

  if (pageError) {
    return (
      <section className="spectator-error page-section" role="alert">
        <p className="eyebrow">ПУБЛИЧНЫЙ ПРОСМОТР</p>
        <h1>Зрительская карта недоступна</h1>
        <p>{pageError}</p>
        <div className="spectator-error-actions">
          <button className="button button-small" type="button" onClick={() => setRetrySequence((value) => value + 1)}>Повторить</button>
          <Link className="button button-outline button-small" to="/watch">К списку турниров</Link>
        </div>
      </section>
    )
  }

  if (!bracket || !snapshot || !activeMatch) {
    return <section className="page-section"><p role="status">Загружаем зрительскую карту…</p></section>
  }

  return (
    <section className={`spectator-page page-section${projector ? ' spectator-page-projector' : ''}`}>
      <header className="spectator-page-heading">
        <div>
          <p className="eyebrow"><span className={spectator.connection === 'live' ? 'live-dot' : 'spectator-status-dot'} /> ПУБЛИЧНЫЙ ПРОСМОТР</p>
          <h1>{bracket.title}</h1>
          <p>Открытая карта матча. Исходный код и приватные данные участников здесь не показываются.</p>
        </div>
        <div className="spectator-view-actions">
          <Link className="button button-outline button-small" to={`/watch${search}`}>Все турниры</Link>
          {projector
            ? <Link className="button button-quiet button-small" to={`/watch/${encodeURIComponent(tournamentId)}/matches/${encodeURIComponent(selectedMatchId)}${safeRouteSearch(location.search, false)}`}>Обычный вид</Link>
            : <Link className="button button-quiet button-small" to={`/watch/${encodeURIComponent(tournamentId)}/matches/${encodeURIComponent(selectedMatchId)}${safeRouteSearch(location.search, true)}`}>Режим проектора</Link>}
        </div>
      </header>

      <div className="spectator-live-status" data-connection={spectator.connection} role="status" aria-live="polite">
        <span className="spectator-status-dot" aria-hidden="true" />
        <strong>{spectatorConnectionLabel(spectator.connection)}</strong>
        <span>·</span><span>событие {spectator.lastEventId}</span>
        {spectator.connection === 'stale' && <span>Показываем последнее подтверждённое состояние.</span>}
        {spectator.error && <span>{spectator.error}</span>}
      </div>

      {spectator.connection !== 'live' && spectator.connection !== 'connecting' && (
        <div className="spectator-reconnect-banner" role="alert">
          <span>Карта сохранена; восстанавливаем подтверждённое состояние.</span>
          <button className="text-button" type="button" onClick={() => setRetrySequence((value) => value + 1)}>Перезагрузить снимок</button>
        </div>
      )}

      <div className="spectator-layout">
        <BracketNavigation
          bracket={displayBracket ?? bracket}
          selectedMatchId={selectedMatchId}
          tournamentId={tournamentId}
          search={location.search}
          projector={projector}
        />

        <div className="spectator-main-column">
          <section className="spectator-match-card" aria-label="Текущий матч">
            <div className="spectator-match-topline">
              <div><span className="spectator-match-key">{activeMatch.key}</span><span className={`spectator-match-status status-${snapshot.status.toLowerCase()}`}>{statusName(snapshot.status)}</span></div>
              <span>Раунд {activeMatch.roundIndex + 1} · матч {activeMatch.position + 1}</span>
            </div>
            <div className="spectator-scoreboard">
              <div className="spectator-score-player"><span>{snapshot.players[0].displayName}</span><strong>{snapshot.players[0].solvedCount}</strong></div>
              <div className="spectator-clock" aria-label={`Осталось ${formatClock(remainingMs)}`}>
                <span>ОСТАЛОСЬ</span><strong aria-live="off">{formatClock(remainingMs)}</strong>
              </div>
              <div className="spectator-score-player spectator-score-player-right"><span>{snapshot.players[1].displayName}</span><strong>{snapshot.players[1].solvedCount}</strong></div>
            </div>
            <div className={`spectator-map${spectator.animateProgress ? ' has-progress-animation' : ''}`} aria-label="Карта прогресса участников">
              {snapshot.players.map((player) => <PublicLane
                key={player.userId}
                player={player}
                leader={player.userId === snapshot.leaderUserId}
                totalTasks={taskCount}
              />)}
            </div>
            <div className="spectator-match-summary">
              <span>{leaderName ? <><b>{leaderName}</b> впереди</> : 'Пока нет лидера'}</span>
              <span>{scoringExplanation(snapshot)}</span>
              {winnerName && <strong className="spectator-winner">Победитель: {winnerName}</strong>}
            </div>
            <div className="spectator-announcements" aria-live="polite" aria-atomic="true">
              {announcement.map((text, index) => <span key={`${spectator.animations[index]?.id ?? index}`}>{text}</span>)}
            </div>
          </section>
          <p className="spectator-scope-note">Позиция фишки соответствует подтверждённому числу решённых задач. Отказ или ожидание проверки не переводят задачу в решённые.</p>
        </div>
      </div>
    </section>
  )
}
