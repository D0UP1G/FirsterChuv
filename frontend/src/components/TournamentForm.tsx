import { useState, type FormEvent } from 'react'
import type { Tournament, TournamentInput } from '../api/client'

type BasicTournamentFields = Pick<TournamentInput, 'title' | 'description' | 'visibility'>

interface TournamentFormProps {
  initial?: Tournament
  frozen?: boolean
  lifecycleLocked?: boolean
  submitLabel: string
  submitting: boolean
  onSubmit: (input: TournamentInput | BasicTournamentFields) => Promise<void>
}

interface TournamentFormState {
  title: string
  description: string
  startsAt: string
  endsAt: string
  participantLimit: string
  visibility: 'public' | 'unlisted'
  matchDurationSec: string
  startMode: 'manual' | 'both_ready'
  wrongAttemptPenaltySec: string
}

function localInputValue(value: Date): string {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000)
  return local.toISOString().slice(0, 16)
}

function initialFormState(tournament?: Tournament): TournamentFormState {
  if (tournament) {
    return {
      title: tournament.title,
      description: tournament.description,
      startsAt: localInputValue(new Date(tournament.startsAt)),
      endsAt: localInputValue(new Date(tournament.endsAt)),
      participantLimit: String(tournament.participantLimit),
      visibility: tournament.visibility,
      matchDurationSec: String(tournament.matchDurationSec),
      startMode: tournament.startMode,
      wrongAttemptPenaltySec: String(tournament.scoringRule.wrongAttemptPenaltySec),
    }
  }
  const startsAt = new Date(Date.now() + 60 * 60_000)
  const endsAt = new Date(startsAt.getTime() + 2 * 60 * 60_000)
  return {
    title: '',
    description: '',
    startsAt: localInputValue(startsAt),
    endsAt: localInputValue(endsAt),
    participantLimit: '4',
    visibility: 'public',
    matchDurationSec: '1800',
    startMode: 'manual',
    wrongAttemptPenaltySec: '300',
  }
}

export function TournamentForm({
  initial,
  frozen = false,
  lifecycleLocked = false,
  submitLabel,
  submitting,
  onSubmit,
}: TournamentFormProps) {
  const [values, setValues] = useState(() => initialFormState(initial))
  const [dateError, setDateError] = useState<string | null>(null)
  const canEdit = !lifecycleLocked

  function update<K extends keyof TournamentFormState>(key: K, value: TournamentFormState[K]) {
    setValues((current) => ({ ...current, [key]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (frozen) {
      await onSubmit({ title: values.title.trim(), description: values.description, visibility: values.visibility })
      return
    }
    const startsAt = new Date(values.startsAt)
    const endsAt = new Date(values.endsAt)
    if (Number.isNaN(startsAt.getTime()) || Number.isNaN(endsAt.getTime()) || endsAt <= startsAt) {
      setDateError('Окончание должно быть позже начала турнира.')
      return
    }
    setDateError(null)
    await onSubmit({
      title: values.title.trim(),
      description: values.description,
      startsAt: startsAt.toISOString(),
      endsAt: endsAt.toISOString(),
      format: 'single_elimination',
      participantLimit: Number(values.participantLimit),
      visibility: values.visibility,
      matchDurationSec: Number(values.matchDurationSec),
      startMode: values.startMode,
      scoringRule: {
        order: ['solved_desc', 'penalty_asc', 'last_accepted_asc'],
        wrongAttemptPenaltySec: Number(values.wrongAttemptPenaltySec),
        penalizedVerdicts: ['WA', 'TL', 'ML', 'RE'],
        finalTiePolicy: 'rematch',
      },
    })
  }

  return (
    <form className="tournament-form" onSubmit={(event) => void handleSubmit(event)}>
      <div className="form-grid">
        <label className="form-field form-field-wide">
          <span>Название</span>
          <input required maxLength={160} value={values.title} onChange={(event) => update('title', event.target.value)} disabled={lifecycleLocked} />
        </label>
        <label className="form-field form-field-wide">
          <span>Описание</span>
          <textarea maxLength={10000} rows={3} value={values.description} onChange={(event) => update('description', event.target.value)} disabled={lifecycleLocked} />
        </label>
        <label className="form-field">
          <span>Начало</span>
          <input required type="datetime-local" value={values.startsAt} onChange={(event) => update('startsAt', event.target.value)} disabled={!canEdit || frozen} />
        </label>
        <label className="form-field">
          <span>Окончание</span>
          <input required type="datetime-local" value={values.endsAt} onChange={(event) => update('endsAt', event.target.value)} disabled={!canEdit || frozen} />
        </label>
        <label className="form-field">
          <span>Лимит участников</span>
          <input required type="number" min={2} step={1} value={values.participantLimit} onChange={(event) => update('participantLimit', event.target.value)} disabled={!canEdit || frozen} />
        </label>
        <label className="form-field">
          <span>Видимость</span>
          <select value={values.visibility} onChange={(event) => update('visibility', event.target.value as TournamentFormState['visibility'])} disabled={lifecycleLocked}>
            <option value="public">Публичный</option>
            <option value="unlisted">По ссылке</option>
          </select>
        </label>
        <label className="form-field">
          <span>Длительность матча, секунды</span>
          <input required type="number" min={60} max={7200} step={60} value={values.matchDurationSec} onChange={(event) => update('matchDurationSec', event.target.value)} disabled={!canEdit || frozen} />
        </label>
        <label className="form-field">
          <span>Запуск матча</span>
          <select value={values.startMode} onChange={(event) => update('startMode', event.target.value as TournamentFormState['startMode'])} disabled={!canEdit || frozen}>
            <option value="manual">Вручную</option>
            <option value="both_ready">Когда готовы оба</option>
          </select>
        </label>
        <label className="form-field">
          <span>Штраф за неверную попытку, секунды</span>
          <input required type="number" min={0} max={7200} step={1} value={values.wrongAttemptPenaltySec} onChange={(event) => update('wrongAttemptPenaltySec', event.target.value)} disabled={!canEdit || frozen} />
        </label>
      </div>
      {dateError && <p className="inline-note" role="alert">{dateError}</p>}
      {frozen && <p className="inline-note">Состав заморожен: доступны только название и описание.</p>}
      {lifecycleLocked && <p className="inline-note">В этом статусе турнир нельзя редактировать.</p>}
      <div className="form-actions">
        <button className="button button-small" type="submit" disabled={submitting || lifecycleLocked}>
          {submitting ? 'Сохраняем…' : submitLabel}
        </button>
      </div>
    </form>
  )
}
