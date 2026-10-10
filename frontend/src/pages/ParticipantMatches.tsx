import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { ApiError, api, type Bracket } from '../api/client'

interface MyMatch {
  tournamentId: string
  tournamentTitle: string
  matchId: string
  status: string
  opponent: string
}

const statusNames: Record<string, string> = {
  READY: 'Готов к старту', RUNNING: 'Идёт', PAUSED: 'Пауза', FINALIZING: 'Проверяем результаты',
  FINISHED: 'Завершён', TIED: 'Равенство', SUPERSEDED: 'Переигран', WAITING: 'Ожидает настройки',
}

function myMatches(userId: string, title: string, bracket: Bracket): MyMatch[] {
  return bracket.matches
    .filter((match) => match.kind === 'MATCH' && match.slots.some((slot) => slot.participant?.userId === userId))
    .map((match) => {
      const other = match.slots.find((slot) => slot.participant && slot.participant.userId !== userId)
      return {
        tournamentId: bracket.tournamentId,
        tournamentTitle: title,
        matchId: match.id,
        status: match.status,
        opponent: other?.participant?.displayName ?? 'соперник определяется',
      }
    })
}

/** Lists the participant's own matches so the workspace is reachable without knowing its URL. */
export function ParticipantMatches({ userId }: { userId: string }) {
  const [matches, setMatches] = useState<MyMatch[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    void (async () => {
      try {
        const tournaments = (await api.tournaments()).results
        const found: MyMatch[] = []
        for (const tournament of tournaments) {
          try {
            found.push(...myMatches(userId, tournament.title, await api.bracket(tournament.id)))
          } catch (reason) {
            // A tournament without a generated bracket simply has no matches yet.
            if (!(reason instanceof ApiError && reason.status === 404)) throw reason
          }
        }
        if (active) {
          setError(null)
          setMatches(found)
        }
      } catch (reason) {
        if (active) setError(reason instanceof ApiError ? reason.message : 'Не удалось загрузить матчи.')
      }
    })()
    return () => { active = false }
  }, [userId, attempt])

  const retry = useCallback(() => {
    setMatches(null)
    setError(null)
    setAttempt((value) => value + 1)
  }, [])

  if (error) {
    return <div className="state-card state-card-error" role="alert"><span>{error}</span><button className="text-button" type="button" onClick={retry}>Повторить</button></div>
  }
  if (matches === null) return <div className="state-card" role="status"><span>Загружаем ваши матчи…</span></div>
  if (matches.length === 0) return <p className="muted-copy">Матчей пока нет: войдите по ссылке-приглашению и дождитесь формирования сетки.</p>
  return (
    <ul className="public-tournament-list" aria-label="Ваши матчи">
      {matches.map((match) => (
        <li key={match.matchId}>
          <Link className="public-tournament-link" to={`/matches/${encodeURIComponent(match.matchId)}`}>
            <strong>{match.tournamentTitle} · против {match.opponent}</strong>
            <span className="meta-pill meta-pill-status">{statusNames[match.status] ?? match.status}</span>
            <span>Открыть матч <span aria-hidden="true">↗</span></span>
          </Link>
        </li>
      ))}
    </ul>
  )
}
