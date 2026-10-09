import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { ApiError, type LoginInput } from '../api/client'
import { useAuth } from '../auth/useAuth'
import { AuthPageFrame } from '../components/AuthPageFrame'

export function LoginPage() {
  const { status, signIn } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  if (status === 'authenticated') return <Navigate to={safeNext(location.search) ?? '/dashboard'} replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setMessage(null)
    setFieldErrors({})
    const input: LoginInput = { email: email.trim(), password }
    try {
      await signIn(input)
      navigate(safeNext(location.search) ?? '/dashboard', { replace: true })
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось войти. Попробуйте ещё раз.')
      setFieldErrors(readFieldErrors(error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthPageFrame
      eyebrow="С возвращением"
      title="Войти в аккаунт"
      description="Продолжите турнир с того места, где остановились."
      footer={<>Ещё нет аккаунта? <Link to="/register">Создать аккаунт</Link></>}
    >
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        {message && <div className="form-alert" role="alert">{message}</div>}
        <label className="field-label" htmlFor="login-email">Электронная почта</label>
        <input
          id="login-email"
          name="email"
          type="email"
          autoComplete="email"
          inputMode="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          aria-invalid={Boolean(fieldErrors.email)}
          aria-describedby={fieldErrors.email ? 'login-email-error' : undefined}
        />
        {fieldErrors.email && <span className="field-error" id="login-email-error">{fieldErrors.email}</span>}
        <div className="label-row"><label className="field-label" htmlFor="login-password">Пароль</label></div>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          aria-invalid={Boolean(fieldErrors.password)}
          aria-describedby={fieldErrors.password ? 'login-password-error' : undefined}
        />
        {fieldErrors.password && <span className="field-error" id="login-password-error">{fieldErrors.password}</span>}
        <button className="button auth-submit" type="submit" disabled={submitting}>
          {submitting ? 'Входим…' : 'Войти'} <span aria-hidden="true">↗</span>
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
