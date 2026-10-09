import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError, api, type InvitePreview } from '../api/client'
import { useAuth } from '../auth/useAuth'
import './Admin.css'

function dateTime(value: string | null): string {
  if (!value) return 'без срока действия'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'срок не указан'
    : new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

export function InvitePage() {
  const { token = '' } = useParams()
  const { status, user } = useAuth()
  const [preview, setPreview] = useState<InvitePreview | null>(null)
  const [previewForToken, setPreviewForToken] = useState<string | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [retrySequence, setRetrySequence] = useState(0)
  const [acceptError, setAcceptError] = useState<string | null>(null)
  const [accepting, setAccepting] = useState(false)
  const [joined, setJoined] = useState(false)

  useEffect(() => {
    let active = true
    void api.previewInvite(token).then((result) => {
      if (!active) return
      setPreview(result)
      setPreviewError(null)
      setJoined(false)
    }).catch((error: unknown) => {
      if (!active) return
      setPreview(null)
      setPreviewError(error instanceof ApiError ? error.message : 'Не удалось проверить приглашение. Попробуйте ещё раз.')
    }).finally(() => {
      if (active) setPreviewForToken(token)
    })
    return () => { active = false }
  }, [token, retrySequence])
  const loading = previewForToken !== token

  const invitePath = `/invites/${encodeURIComponent(token)}`
  const loginPath = `/login?next=${encodeURIComponent(invitePath)}`
  const registerPath = `/register?next=${encodeURIComponent(invitePath)}`

  async function accept() {
    setAccepting(true)
    setAcceptError(null)
    try {
      await api.acceptInvite(token)
      setJoined(true)
    } catch (error) {
      const message = error instanceof ApiError ? error.message : 'Не удалось присоединиться. Попробуйте ещё раз.'
      setAcceptError(message)
    } finally {
      setAccepting(false)
    }
  }

  return (
    <section className="page-section invite-page">
      <p className="eyebrow">Приглашение в турнир</p>
      <h1>Присоединиться по ссылке</h1>
      <p className="page-lede">До входа в аккаунт отображаются только название турнира и состояние ссылки. Состав, задачи и чужие решения здесь не раскрываются.</p>
      {loading ? (
        <div className="state-card" role="status">Проверяем приглашение…</div>
      ) : previewError ? (
        <div className="invite-preview-card invite-error-panel" role="alert">
          <h2>Приглашение недоступно</h2>
          <p>{previewError}</p>
          <button className="button button-quiet button-small" type="button" onClick={() => { setPreviewForToken(null); setPreviewError(null); setRetrySequence((value) => value + 1) }}>Проверить ещё раз</button>
        </div>
      ) : preview ? (
        <div className="invite-preview-card">
          <span className="meta-pill meta-pill-status">Ссылка действительна</span>
          <h2>{preview.tournament.title}</h2>
          <p>Приглашение действует до {dateTime(preview.expiresAt)}. После входа подтвердите присоединение.</p>
          {acceptError && <div className="state-card state-card-error" role="alert">{acceptError}</div>}
          {joined ? (
            <div className="invite-preview-actions" role="status"><strong>Вы присоединились к турниру.</strong><Link className="button button-small" to="/dashboard">Открыть кабинет</Link></div>
          ) : status === 'authenticated' && user?.role === 'participant' ? (
            <div className="invite-preview-actions"><button className="button" type="button" disabled={accepting} onClick={() => void accept()}>{accepting ? 'Присоединяем…' : 'Присоединиться'}</button><Link className="button button-outline" to="/dashboard">Позже</Link></div>
          ) : status === 'authenticated' ? (
            <div className="invite-preview-actions"><p className="inline-note">Эта ссылка предназначена для аккаунта участника. Аккаунт администратора не может вступить в ростер.</p><Link className="button button-quiet button-small" to="/dashboard">В кабинет</Link></div>
          ) : (
            <div className="invite-preview-actions"><Link className="button" to={loginPath}>Войти и продолжить</Link><Link className="button button-outline" to={registerPath}>Создать аккаунт</Link></div>
          )}
        </div>
      ) : null}
    </section>
  )
}
