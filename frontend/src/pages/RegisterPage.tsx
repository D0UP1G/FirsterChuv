import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { ApiError, type RegisterInput } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { AuthPageFrame } from '../components/AuthPageFrame'

export function RegisterPage() {
  const { status, signUp } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const next = safeNext(location.search)
  const loginPath = next ? `/login?next=${encodeURIComponent(next)}` : '/login'

  if (status === 'authenticated') return <Navigate to="/dashboard" replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setMessage(null)
    setFieldErrors({})
    const input: RegisterInput = { displayName: displayName.trim(), email: email.trim(), password }
    try {
      await signUp(input)
      setSuccess(true)
      setPassword('')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось создать аккаунт. Попробуйте ещё раз.')
      setFieldErrors(readFieldErrors(error))
    } finally {
      setSubmitting(false)
    }
  }

  if (success) {
    return (
      <AuthPageFrame
        eyebrow="Готово"
        title="Аккаунт создан"
        description="Теперь войдите, чтобы открыть личный кабинет."
        footer={<>Уже есть аккаунт? <Link to={loginPath}>Войти</Link></>}
      >
        <div className="success-panel" role="status">
          <span className="success-mark" aria-hidden="true">✓</span>
          <div><strong>Вы зарегистрированы как участник.</strong><p>Роль организатора выдаётся отдельно и не выбирается при регистрации.</p></div>
        </div>
        <button className="button auth-submit" type="button" onClick={() => navigate(loginPath, { replace: true })}>Перейти ко входу <span aria-hidden="true">↗</span></button>
      </AuthPageFrame>
    )
  }

  return (
    <AuthPageFrame
      eyebrow="Новый участник"
      title="Создать аккаунт"
      description="Зарегистрируйтесь, чтобы входить в турниры по приглашению."
      footer={<>Уже есть аккаунт? <Link to={loginPath}>Войти</Link></>}
    >
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        {message && <div className="form-alert" role="alert">{message}</div>}
        <label className="field-label" htmlFor="register-name">Имя в турнире</label>
        <input
          id="register-name"
          name="displayName"
          type="text"
          autoComplete="name"
          maxLength={80}
          required
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          aria-invalid={Boolean(fieldErrors.displayName)}
          aria-describedby={fieldErrors.displayName ? 'register-name-error' : undefined}
        />
        {fieldErrors.displayName && <span className="field-error" id="register-name-error">{fieldErrors.displayName}</span>}
        <label className="field-label" htmlFor="register-email">Электронная почта</label>
        <input
          id="register-email"
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          aria-invalid={Boolean(fieldErrors.email)}
          aria-describedby={fieldErrors.email ? 'register-email-error' : undefined}
        />
        {fieldErrors.email && <span className="field-error" id="register-email-error">{fieldErrors.email}</span>}
        <label className="field-label" htmlFor="register-password">Пароль</label>
        <input
          id="register-password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          aria-invalid={Boolean(fieldErrors.password)}
          aria-describedby={fieldErrors.password ? 'register-password-error' : 'register-password-help'}
        />
        {fieldErrors.password
          ? <span className="field-error" id="register-password-error">{fieldErrors.password}</span>
          : <span className="field-help" id="register-password-help">Используйте пароль, который не применяете на других сайтах.</span>}
        <p className="role-note"><span aria-hidden="true">↳</span> Новый аккаунт получает роль участника.</p>
        <button className="button auth-submit" type="submit" disabled={submitting}>
          {submitting ? 'Создаём аккаунт…' : 'Зарегистрироваться'} <span aria-hidden="true">↗</span>
        </button>
      </form>
    </AuthPageFrame>
  )
}

function safeNext(search: string): string | null {
  const candidate = new URLSearchParams(search).get('next')
  if (!candidate || !candidate.startsWith('/') || candidate.startsWith('//')) return null
  try {
    const destination = new URL(candidate, window.location.origin)
    if (destination.origin !== window.location.origin) return null
    return `${destination.pathname}${destination.search}${destination.hash}`
  } catch {
    return null
  }
}

function readFieldErrors(error: unknown): Record<string, string> {
  if (!(error instanceof ApiError) || typeof error.fields !== 'object' || error.fields === null || Array.isArray(error.fields)) return {}
  return Object.fromEntries(Object.entries(error.fields).flatMap(([key, value]) => {
    const first = Array.isArray(value) ? value[0] : value
    return typeof first === 'string' ? [[key, first]] : []
  }))
}
