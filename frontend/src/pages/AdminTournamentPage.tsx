import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router'
import {
  ApiError,
  api,
  type DirectoryUser,
  type InviteCreated,
  type InviteMetadata,
  type RosterEntry,
  type Tournament,
  type TournamentInput,
} from '../api/client'
import { TournamentForm } from '../components/TournamentForm'
import { statusLabel } from './tournamentStatus'
import './Admin.css'

function messageFor(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return 'Не удалось выполнить запрос. Попробуйте ещё раз.'
}

function dateTime(value: string | null): string {
  if (!value) return 'Без срока'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Дата не указана'
    : new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function localDateTime(value: string): string {
  const date = new Date(value)
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

function inviteStatus(invite: InviteMetadata): string {
  if (invite.revokedAt) return 'Отозвано'
  if (invite.expiresAt && new Date(invite.expiresAt).getTime() <= Date.now()) return 'Истекло'
  if (invite.maxUses !== null && invite.uses >= invite.maxUses) return 'Лимит исчерпан'
  return 'Действует'
}

function sameOriginInvitePath(value: string): string {
  const parsed = new URL(value, window.location.origin)
  if (parsed.origin !== window.location.origin || !/^\/invites\/[^/]+$/.test(parsed.pathname) || parsed.search || parsed.hash) {
    throw new Error('Сервер вернул некорректный адрес приглашения.')
  }
  return parsed.pathname
}

export function AdminTournamentPage() {
  const { tournamentId = '' } = useParams()
  const [tournament, setTournament] = useState<Tournament | null>(null)
  const [roster, setRoster] = useState<RosterEntry[]>([])
  const [invites, setInvites] = useState<InviteMetadata[]>([])
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [pendingRemovalId, setPendingRemovalId] = useState<string | null>(null)
  const [pendingRevokeId, setPendingRevokeId] = useState<string | null>(null)
  const [directoryQuery, setDirectoryQuery] = useState('')
  const [directoryResults, setDirectoryResults] = useState<DirectoryUser[]>([])
  const [directoryLoading, setDirectoryLoading] = useState(false)
  const [directoryError, setDirectoryError] = useState<string | null>(null)
  const [assignmentSeeds, setAssignmentSeeds] = useState<Record<string, string>>({})
  const [newInvite, setNewInvite] = useState<InviteCreated | null>(null)
  const [inviteExpiresAt, setInviteExpiresAt] = useState('')
  const [inviteMaxUses, setInviteMaxUses] = useState('')
  const [inviteCopied, setInviteCopied] = useState(false)
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [inviteMinDate] = useState(() => localDateTime(new Date(Date.now() + 60_000).toISOString()))

  const load = useCallback(async () => {
    try {
      const [nextTournament, rosterPage, invitePage] = await Promise.all([
        api.tournament(tournamentId),
        api.roster(tournamentId),
        api.invites(tournamentId),
      ])
      setTournament(nextTournament)
      setRoster(rosterPage.results)
      setInvites(invitePage.results)
      setAssignmentSeeds(Object.fromEntries(rosterPage.results.map((entry) => [entry.userId, entry.seed === null ? '' : String(entry.seed)])))
    } catch (error) {
      setPageError(messageFor(error))
    } finally {
      setLoading(false)
    }
  }, [tournamentId])

  const loadDirectory = useCallback(async (query: string) => {
    try {
      const page = await api.directory(query.trim())
      setDirectoryResults(page.results)
    } catch (error) {
      setDirectoryError(messageFor(error))
    } finally {
      setDirectoryLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    void Promise.all([
      api.tournament(tournamentId),
      api.roster(tournamentId),
      api.invites(tournamentId),
    ]).then(([nextTournament, rosterPage, invitePage]) => {
      if (!active) return
      setTournament(nextTournament)
      setRoster(rosterPage.results)
      setInvites(invitePage.results)
      setAssignmentSeeds(Object.fromEntries(rosterPage.results.map((entry) => [entry.userId, entry.seed === null ? '' : String(entry.seed)])))
    }).catch((error: unknown) => {
      if (active) setPageError(messageFor(error))
    }).finally(() => {
      if (active) setLoading(false)
    })
    return () => { active = false }
  }, [tournamentId])
  const activeUserIds = useMemo(
    () => new Set(roster.filter((entry) => entry.status === 'ACTIVE').map((entry) => entry.userId)),
    [roster],
  )

  async function perform(key: string, action: () => Promise<void>) {
    setBusy(key)
    setActionError(null)
    setActionMessage(null)
    try {
      await action()
      await load()
    } catch (error) {
      setActionError(messageFor(error))
    } finally {
      setBusy(null)
    }
  }

  async function saveTournament(input: TournamentInput | Pick<TournamentInput, 'title' | 'description' | 'visibility'>) {
    await perform('tournament', async () => {
      const saved = await api.updateTournament(tournamentId, input)
      setTournament(saved)
      setActionMessage('Изменения турнира сохранены.')
    })
  }

  async function assign(user: DirectoryUser) {
    const seedText = assignmentSeeds[user.id]?.trim() ?? ''
    if (seedText !== '' && (!/^\d+$/.test(seedText) || Number(seedText) < 1 || Number(seedText) > 2_147_483_647)) {
      setActionError('Посев должен быть целым числом от 1 до 2147483647 или пустым.')
      return
    }
    await perform(`assign:${user.id}`, async () => {
      await api.assignParticipant(tournamentId, user.id, seedText === '' ? undefined : Number(seedText))
      setActionMessage(`${user.displayName} добавлен в состав.`)
    })
  }

  async function saveSeed(entry: RosterEntry) {
    const seedText = assignmentSeeds[entry.userId]?.trim() ?? ''
    if (seedText !== '' && (!/^\d+$/.test(seedText) || Number(seedText) < 1 || Number(seedText) > 2_147_483_647)) {
      setActionError('Посев должен быть целым числом от 1 до 2147483647 или пустым.')
      return
    }
    await perform(`seed:${entry.userId}`, async () => {
      await api.setParticipantSeed(tournamentId, entry.userId, seedText === '' ? null : Number(seedText))
      setActionMessage(`Посев для ${entry.displayName} сохранён.`)
    })
  }

  async function remove(entry: RosterEntry) {
    await perform(`remove:${entry.userId}`, async () => {
      await api.removeParticipant(tournamentId, entry.userId)
      setPendingRemovalId(null)
      setActionMessage(`${entry.displayName} снят с турнира.`)
    })
  }

  async function createInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setInviteError(null)
    setInviteCopied(false)
    const maxUsesText = inviteMaxUses.trim()
    if (!inviteExpiresAt && !maxUsesText) {
      setInviteError('Укажите срок действия или лимит активаций.')
      return
    }
    if (maxUsesText && (!/^\d+$/.test(maxUsesText) || Number(maxUsesText) < 1 || Number(maxUsesText) > 2_147_483_647)) {
      setInviteError('Лимит активаций должен быть целым числом от 1 до 2147483647.')
      return
    }
    const expiresAt = inviteExpiresAt ? new Date(inviteExpiresAt) : null
    if (expiresAt && (!Number.isFinite(expiresAt.getTime()) || expiresAt.getTime() <= Date.now())) {
      setInviteError('Укажите срок действия в будущем.')
      return
    }
    setBusy('invite:create')
    try {
      const created = await api.createInvite(tournamentId, {
        ...(expiresAt ? { expiresAt: expiresAt.toISOString() } : {}),
        ...(maxUsesText ? { maxUses: Number(maxUsesText) } : {}),
      })
      const safePath = sameOriginInvitePath(created.url)
      setNewInvite({ ...created, url: safePath })
      setInviteMaxUses('')
      setInviteExpiresAt('')
      setActionMessage('Приглашение создано. Ссылка показана только в этом сеансе.')
      await load()
    } catch (error) {
      setInviteError(messageFor(error))
    } finally {
      setBusy(null)
    }
  }

  async function copyInvite() {
    if (!newInvite) return
    try {
      await navigator.clipboard.writeText(new URL(newInvite.url, window.location.origin).toString())
      setInviteCopied(true)
      setInviteError(null)
    } catch {
      setInviteError('Браузер не разрешил доступ к буферу обмена. Скопируйте адрес из поля вручную.')
    }
  }

  async function revoke(invite: InviteMetadata) {
    setBusy(`invite:${invite.id}`)
    setInviteError(null)
    try {
      await api.revokeInvite(tournamentId, invite.id)
      setPendingRevokeId(null)
      if (newInvite?.invite.id === invite.id) setNewInvite(null)
      await load()
      setActionMessage('Приглашение отозвано.')
    } catch (error) {
      setInviteError(messageFor(error))
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <section className="page-section management-page"><div className="state-card" role="status">Загружаем турнир, состав и приглашения…</div></section>
  if (pageError || !tournament) {
    return <section className="page-section management-page"><div className="state-card state-card-error" role="alert"><span>{pageError ?? 'Турнир не найден.'}</span><button className="text-button" type="button" onClick={() => { setLoading(true); setPageError(null); void load() }}>Повторить</button></div></section>
  }

  const lifecycleLocked = ['running', 'completed', 'archived'].includes(tournament.status)
  const activeCount = roster.filter((entry) => entry.status === 'ACTIVE').length

  return (
    <section className="page-section management-page">
      <nav className="breadcrumbs" aria-label="Навигационная цепочка"><Link to="/admin">Турниры</Link><span aria-hidden="true">/</span><span>{tournament.title}</span></nav>
      <div className="management-heading">
        <div><p className="eyebrow">Управление турниром · {statusLabel[tournament.status] ?? tournament.status}</p><h1>{tournament.title}</h1><p>{activeCount} из {tournament.participantLimit} участников · {tournament.rosterFrozenAt ? 'состав заморожен' : 'состав открыт'}</p></div>
        <div className="management-actions">
          <Link className="button button-outline button-small" to={`/admin/tournaments/${encodeURIComponent(tournament.id)}/matches`}>Сетка и матчи</Link>
          <button className="button button-quiet button-small" type="button" onClick={() => { setLoading(true); setPageError(null); void load() }}>Обновить</button>
        </div>
      </div>

      {actionError && <div className="state-card state-card-error" role="alert">{actionError}</div>}
      {actionMessage && <div className="state-card" role="status">{actionMessage}</div>}

      <section className="management-panel" aria-labelledby="tournament-settings-heading">
        <div className="panel-heading"><div><h2 id="tournament-settings-heading">Параметры турнира</h2><p>Ограничения статуса турнира, состава и прав проверяются сервером.</p></div></div>
        <TournamentForm
          key={`${tournament.id}:${tournament.rosterFrozenAt ?? 'open'}:${tournament.status}`}
          initial={tournament}
          frozen={Boolean(tournament.rosterFrozenAt)}
          lifecycleLocked={lifecycleLocked}
          submitLabel="Сохранить параметры"
          submitting={busy === 'tournament'}
          onSubmit={saveTournament}
        />
      </section>

      <section className="management-panel" aria-labelledby="roster-heading">
        <div className="panel-heading"><div><h2 id="roster-heading">Состав участников</h2><p>Активно {activeCount} из {tournament.participantLimit}. Посев — уникальное целое число или пустое значение.</p></div></div>
        {roster.length === 0 ? <p className="inline-note">В составе пока нет участников.</p> : (
          <div className="roster-list">
            {roster.map((entry) => (
              <RosterRow
                key={`${entry.userId}:${entry.status}`}
                entry={entry}
                seedValue={assignmentSeeds[entry.userId] ?? ''}
                busy={busy}
                confirmingRemoval={pendingRemovalId === entry.userId}
                onSeedChange={(value) => setAssignmentSeeds((current) => ({ ...current, [entry.userId]: value }))}
                onSave={() => void saveSeed(entry)}
                onRequestRemove={() => setPendingRemovalId(entry.userId)}
                onCancelRemove={() => setPendingRemovalId(null)}
                onRemove={() => void remove(entry)}
              />
            ))}
          </div>
        )}
      </section>

      <section className="management-panel" aria-labelledby="directory-heading">
        <div className="panel-heading"><div><h2 id="directory-heading">Найти участника</h2><p>Каталог показывает только ID и имя участника; электронная почта не запрашивается.</p></div></div>
        <form className="search-form" onSubmit={(event) => { event.preventDefault(); setDirectoryLoading(true); setDirectoryError(null); void loadDirectory(directoryQuery) }}>
          <input className="management-input" type="search" maxLength={80} value={directoryQuery} onChange={(event) => setDirectoryQuery(event.target.value)} placeholder="Имя участника" aria-label="Поиск участников по имени" />
          <button className="button button-small" type="submit" disabled={directoryLoading}>{directoryLoading ? 'Ищем…' : 'Найти'}</button>
        </form>
        {directoryError && <div className="state-card state-card-error" role="alert"><span>{directoryError}</span><button className="text-button" type="button" onClick={() => { setDirectoryLoading(true); setDirectoryError(null); void loadDirectory(directoryQuery) }}>Повторить</button></div>}
        {activeCount >= tournament.participantLimit && <p className="inline-note" role="status">Достигнут лимит состава. Увеличьте лимит до добавления новых участников.</p>}
        {!directoryLoading && directoryResults.length === 0 && <p className="inline-note">Введите имя участника и нажмите «Найти»; каталог показывает только аккаунты participant.</p>}
        <div className="directory-results">
          {directoryResults.map((user) => (
            <div className="directory-row" key={user.id}>
              <span className="directory-name">{user.displayName}<small>{activeUserIds.has(user.id) ? 'Уже в составе' : 'Аккаунт participant'}</small></span>
              <div className="directory-controls">
                <input className="seed-input" type="number" min={1} max={2_147_483_647} step={1} aria-label={`Посев для ${user.displayName}`} placeholder="Посев" value={assignmentSeeds[user.id] ?? ''} onChange={(event) => setAssignmentSeeds((current) => ({ ...current, [user.id]: event.target.value }))} />
                <button className="button button-quiet button-small" type="button" disabled={activeUserIds.has(user.id) || Boolean(tournament.rosterFrozenAt) || activeCount >= tournament.participantLimit || busy === `assign:${user.id}`} onClick={() => void assign(user)}>
                  {activeUserIds.has(user.id) ? 'Уже добавлен' : busy === `assign:${user.id}` ? 'Добавляем…' : 'Добавить'}
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="management-panel" aria-labelledby="invites-heading">
        <div className="panel-heading"><div><h2 id="invites-heading">Приглашения</h2><p>Ссылка выдаётся один раз при создании. В списке остаются только ограниченные данные приглашения, без секретного токена.</p></div></div>
        <form className="tournament-form" onSubmit={(event) => void createInvite(event)}>
          <div className="form-grid">
            <label className="form-field"><span>Действует до</span><input type="datetime-local" min={inviteMinDate} value={inviteExpiresAt} onChange={(event) => setInviteExpiresAt(event.target.value)} disabled={Boolean(tournament.rosterFrozenAt) || busy === 'invite:create'} /></label>
            <label className="form-field"><span>Лимит активаций</span><input type="number" min={1} max={2_147_483_647} step={1} value={inviteMaxUses} onChange={(event) => setInviteMaxUses(event.target.value)} placeholder="Например, 2" disabled={Boolean(tournament.rosterFrozenAt) || busy === 'invite:create'} /></label>
          </div>
          <p className="inline-note">Нужно указать срок действия, лимит активаций или оба ограничения.</p>
          {inviteError && <div className="state-card state-card-error invite-error" role="alert">{inviteError}</div>}
          <div className="form-actions"><button className="button button-small" type="submit" disabled={Boolean(tournament.rosterFrozenAt) || busy === 'invite:create'}>{busy === 'invite:create' ? 'Создаём…' : 'Создать приглашение'}</button></div>
        </form>
        {newInvite && (
          <div className="invite-result">
            <strong>Новая ссылка — скопируйте её сейчас</strong>
            <div className="invite-url-row"><input aria-label="Ссылка-приглашение" readOnly value={new URL(newInvite.url, window.location.origin).toString()} onFocus={(event) => event.currentTarget.select()} /><button className="button button-small" type="button" onClick={() => void copyInvite()}>{inviteCopied ? 'Скопировано' : 'Скопировать'}</button></div>
            <span className="invite-status">Секретный токен останется только в памяти этой страницы. Список приглашений не возвращает его повторно.</span>
          </div>
        )}
        <div className="invite-list" aria-label="Список приглашений">
          {invites.map((invite) => (
            <div className="invite-row" key={invite.id}>
              <span className="roster-name">{inviteStatus(invite)}<small>{invite.uses}{invite.maxUses === null ? ' использований' : ` из ${invite.maxUses}`} · до {dateTime(invite.expiresAt)}</small></span>
              <div className="invite-controls">
                {!invite.revokedAt && <button className="button button-quiet button-small text-danger" type="button" disabled={busy === `invite:${invite.id}`} onClick={() => setPendingRevokeId(invite.id)}>{busy === `invite:${invite.id}` ? 'Отзываем…' : 'Отозвать'}</button>}
                {pendingRevokeId === invite.id && <div className="confirmation-panel" role="alertdialog" aria-label="Подтверждение отзыва приглашения"><span>Отозвать ссылку? Уже присоединившихся участников это не снимает.</span><button className="button button-small text-danger" type="button" disabled={busy === `invite:${invite.id}`} onClick={() => void revoke(invite)}>Подтвердить отзыв</button><button className="button button-quiet button-small" type="button" onClick={() => setPendingRevokeId(null)}>Отмена</button></div>}
              </div>
            </div>
          ))}
          {invites.length === 0 && <p className="inline-note">Приглашений пока нет.</p>}
        </div>
      </section>
    </section>
  )
}

function RosterRow({
  entry,
  seedValue,
  busy,
  confirmingRemoval,
  onSeedChange,
  onSave,
  onRequestRemove,
  onCancelRemove,
  onRemove,
}: {
  entry: RosterEntry
  seedValue: string
  busy: string | null
  confirmingRemoval: boolean
  onSeedChange: (value: string) => void
  onSave: () => void
  onRequestRemove: () => void
  onCancelRemove: () => void
  onRemove: () => void
}) {
  const active = entry.status === 'ACTIVE'
  return (
    <div className="roster-row">
      <span className="roster-name">{entry.displayName}<small>{active ? 'В составе' : 'Снят'} · seed {entry.seed ?? 'не задан'}</small></span>
      <div className="roster-controls">
        {active && <>
          <input className="seed-input" type="number" min={1} max={2_147_483_647} step={1} aria-label={`Изменить посев ${entry.displayName}`} placeholder="Посев" value={seedValue} onChange={(event) => onSeedChange(event.target.value)} />
          <button className="button button-quiet button-small" type="button" disabled={busy === `seed:${entry.userId}`} onClick={onSave}>{busy === `seed:${entry.userId}` ? 'Сохраняем…' : 'Сохранить seed'}</button>
          {confirmingRemoval ? <div className="confirmation-panel" role="alertdialog" aria-label={`Снятие участника ${entry.displayName}`}><span>Снять с турнира? Запись останется в истории состава.</span><button className="button button-small text-danger" type="button" disabled={busy === `remove:${entry.userId}`} onClick={onRemove}>{busy === `remove:${entry.userId}` ? 'Снимаем…' : 'Подтвердить снятие'}</button><button className="button button-quiet button-small" type="button" onClick={onCancelRemove}>Отмена</button></div> : <button className="button button-quiet button-small text-danger" type="button" disabled={busy === `remove:${entry.userId}`} onClick={onRequestRemove}>Снять</button>}
        </>}
      </div>
    </div>
  )
}
