import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError, api, type Tournament, type TournamentInput } from '../api/client'
import { TournamentForm } from '../components/TournamentForm'
import { statusLabel } from './tournamentStatus'
import './Admin.css'

function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Не удалось выполнить запрос. Попробуйте ещё раз.'
}

function dateTime(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}


export function AdminTournamentsPage() {
  const navigate = useNavigate()
  const [tournaments, setTournaments] = useState<Tournament[]>([])
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [removingId, setRemovingId] = useState<string | null>(null)
  const [pendingRemoval, setPendingRemoval] = useState<Tournament | null>(null)

  const load = useCallback(async () => {
    try {
      const page = await api.tournaments()
      setTournaments(page.results)
    } catch (error) {
      setPageError(messageFor(error))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    void api.tournaments().then((page) => {
      if (active) setTournaments(page.results)
    }).catch((error: unknown) => {
      if (active) setPageError(messageFor(error))
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [])

  async function createTournament(input: TournamentInput) {
    setSubmitting(true)
    setFormError(null)
    try {
      const tournament = await api.createTournament(input)
      navigate(`/admin/tournaments/${encodeURIComponent(tournament.id)}`)
    } catch (error) {
      setFormError(messageFor(error))
    } finally {
      setSubmitting(false)
    }
  }

  async function removeTournament(tournament: Tournament) {
    setRemovingId(tournament.id)
    setPageError(null)
    try {
      await api.deleteTournament(tournament.id)
      setPendingRemoval(null)
      await load()
    } catch (error) {
      setPageError(messageFor(error))
    } finally {
      setRemovingId(null)
    }
  }

  return (
    <section className="page-section management-page">
      <div className="management-heading">
        <div>
          <p className="eyebrow">Панель организатора</p>
          <h1>Турниры</h1>
          <p>Настройте соревнование, ростер и приглашения. Статусы и ограничения подтверждает сервер.</p>
        </div>
        <div className="management-actions">
          {import.meta.env.DEV && <Link className="button button-outline button-small" to="/admin/tournaments/dev-match/matches?scenario=match-ui&participants=4">Открыть сценарий match UI</Link>}
          <button className="button" type="button" onClick={() => { setCreating((value) => !value); setFormError(null) }}>
            {creating ? 'Закрыть форму' : 'Создать турнир'}
          </button>
        </div>
      </div>

      {creating && (
        <section className="management-panel" aria-labelledby="create-tournament-heading">
          <div className="panel-heading"><div><h2 id="create-tournament-heading">Новый турнир</h2><p>Формат MVP — одиночное выбывание; роль организатора задаёт сервер.</p></div></div>
          {formError && <div className="state-card state-card-error" role="alert">{formError}</div>}
          <TournamentForm submitLabel="Создать турнир" submitting={submitting} onSubmit={(input) => 'startsAt' in input ? createTournament(input) : Promise.resolve()} />
        </section>
      )}

      {pageError && <div className="state-card state-card-error" role="alert"><span>{pageError}</span><button className="text-button" type="button" onClick={() => { setLoading(true); setPageError(null); void load() }}>Повторить</button></div>}
      {loading ? (
        <div className="state-card" role="status">Загружаем турниры…</div>
      ) : tournaments.length === 0 ? (
        <div className="empty-state compact-empty"><span className="empty-icon" aria-hidden="true">＋</span><h2>Турниров пока нет</h2><p>Создайте первый турнир — он появится в этом списке.</p></div>
      ) : (
        <div className="tournament-list" aria-label="Список турниров">
          {tournaments.map((tournament) => (
            <article className="tournament-card" key={tournament.id}>
              <div>
                <h2><Link to={`/admin/tournaments/${encodeURIComponent(tournament.id)}`}>{tournament.title}</Link></h2>
                <p>{tournament.description || 'Описание не добавлено.'}</p>
                <div className="tournament-meta">
                  <span className="meta-pill meta-pill-status">{statusLabel[tournament.status]}</span>
                  <span className="meta-pill">{dateTime(tournament.startsAt)}</span>
                  <span className="meta-pill">{tournament.activeParticipantCount}/{tournament.participantLimit} участников</span>
                  <span className="meta-pill">{tournament.visibility === 'public' ? 'Публичный' : 'По ссылке'}</span>
                </div>
              </div>
              <div className="tournament-card-actions">
                <Link className="button button-quiet button-small" to={`/admin/tournaments/${encodeURIComponent(tournament.id)}`}>Управлять</Link>
                {pendingRemoval?.id === tournament.id ? <div className="confirmation-panel" role="alertdialog" aria-label="Подтверждение удаления турнира"><span>Подтвердить действие для «{tournament.title}»?</span><button className="button button-small text-danger" type="button" disabled={removingId === tournament.id} onClick={() => void removeTournament(tournament)}>{removingId === tournament.id ? 'Обрабатываем…' : 'Подтвердить'}</button><button className="button button-quiet button-small" type="button" onClick={() => setPendingRemoval(null)}>Отмена</button></div> : <button className="button button-quiet button-small text-danger" type="button" disabled={removingId === tournament.id} onClick={() => setPendingRemoval(tournament)}>{tournament.status === 'draft' && !tournament.rosterFrozenAt ? 'Удалить' : 'Архивировать'}</button>}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
