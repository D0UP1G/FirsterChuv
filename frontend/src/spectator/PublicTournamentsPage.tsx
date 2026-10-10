import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { ApiError, api, type PublicTournamentSummary } from '../api/client'
import './spectator.css'

const statusNames: Record<PublicTournamentSummary['status'], string> = {
  draft: 'Черновик',
  scheduled: 'Запланирован',
  running: 'Идёт',
  completed: 'Завершён',
  archived: 'Архив',
}

function formatPeriod(startsAt: string, endsAt: string): string {
  const format = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })
  const start = new Date(startsAt)
  const end = new Date(endsAt)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 'Даты уточняются'
  return `${format.format(start)} — ${format.format(end)}`
}

export function PublicTournamentsPage() {
  const [tournaments, setTournaments] = useState<PublicTournamentSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    api.publicTournaments().then((page) => {
      if (!active) return
      setError(null)
      setTournaments(page.results)
    }).catch((reason: unknown) => {
      if (!active) return
      setError(reason instanceof ApiError ? reason.message : 'Не удалось загрузить список турниров.')
    })
    return () => { active = false }
  }, [attempt])

  const retry = useCallback(() => {
    setTournaments(null)
    setError(null)
    setAttempt((value) => value + 1)
  }, [])

  return (
    <section className="page-section public-page">
      <div className="page-heading">
        <p className="eyebrow"><span className="live-dot" /> Открытый просмотр</p>
        <h1>Публичные турниры</h1>
        <p>Зрительский просмотр доступен без аккаунта. Код участников здесь не показывается.</p>
      </div>
      {error && (
        <div className="state-card state-card-error" role="alert">
          <span>{error}</span>
          <button className="text-button" type="button" onClick={retry}>Повторить</button>
        </div>
      )}
      {!error && tournaments === null && <div className="state-card" role="status"><span>Загружаем турниры…</span></div>}
      {!error && tournaments !== null && tournaments.length === 0 && (
        <div className="empty-state">
          <div className="empty-orbit" aria-hidden="true"><span>Б</span></div>
          <h2>Открытых турниров пока нет</h2>
          <p>Как только организатор откроет турнир, он появится в этом списке.</p>
          <Link className="text-link" to="/">На главную <span aria-hidden="true">↗</span></Link>
        </div>
      )}
      {!error && tournaments !== null && tournaments.length > 0 && (
        <ul className="public-tournament-list">
          {tournaments.map((tournament) => (
            <li key={tournament.id}>
              <Link className="public-tournament-link" to={`/watch/${encodeURIComponent(tournament.id)}`}>
                <strong>{tournament.title}</strong>
                <span>{formatPeriod(tournament.startsAt, tournament.endsAt)}</span>
                <span className="meta-pill meta-pill-status">{statusNames[tournament.status] ?? tournament.status}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
