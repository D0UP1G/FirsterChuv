import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { resetCsrfToken } from './api/client'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

describe('public and private routes', () => {
  beforeEach(() => {
    resetCsrfToken()
    window.history.replaceState({}, '', '/')
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/csrf')) return Promise.resolve(jsonResponse({ csrfToken: 'csrf-test' }))
      if (url.endsWith('/me')) return Promise.resolve(jsonResponse({ error: { code: 'not_authenticated', message: 'Требуется вход.' } }, 401))
      return Promise.resolve(jsonResponse({}, 404))
    }))
  })

  afterEach(() => {
    cleanup()
    resetCsrfToken()
    vi.unstubAllGlobals()
  })

  it('keeps the spectator page public for an anonymous visitor', async () => {
    window.history.replaceState({}, '', '/watch')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Публичные турниры' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/watch')
    expect(screen.getByText('Зрительский просмотр доступен без аккаунта. Код участников здесь не показывается.')).toBeInTheDocument()
  })

  it('opens an anonymous match map and keeps projector mode free of site navigation', async () => {
    const tournamentId = '00000000-0000-4000-8000-000000000010'
    const matchId = '00000000-0000-4000-8000-000000000020'
    window.history.replaceState({}, '', `/watch/${tournamentId}/matches/${matchId}?scenario=public-map`)
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Демонстрационный блиц · данные разработки' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Основная навигация' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Войти в аккаунт' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Режим проектора' }))
    expect(await screen.findByRole('link', { name: 'Обычный вид' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Основная навигация' })).not.toBeInTheDocument()
  })

  it('redirects only a private dashboard route to login', async () => {
    window.history.replaceState({}, '', '/dashboard')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Войти в аккаунт' })).toBeInTheDocument()
    await waitFor(() => expect(window.location.pathname).toBe('/login'))
    expect(window.location.search).toContain(encodeURIComponent('/dashboard'))
  })

  it('keeps a protected match destination when switching from login to registration', async () => {
    const next = '/matches/match-42?problem=problem-7#editor'
    window.history.replaceState({}, '', next)
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Войти в аккаунт' })).toBeInTheDocument()
    await waitFor(() => expect(new URLSearchParams(window.location.search).get('next')).toBe(next))
    await userEvent.click(screen.getAllByRole('link', { name: 'Создать аккаунт' }).at(-1)!)

    expect(await screen.findByRole('heading', { name: 'Создать аккаунт' })).toBeInTheDocument()
    expect(new URLSearchParams(window.location.search).get('next')).toBe(next)
  })

  it('returns a participant to the requested protected match after login', async () => {
    const next = '/matches/match-42?problem=problem-7#editor'
    window.history.replaceState({}, '', next)
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/csrf')) return Promise.resolve(jsonResponse({ csrfToken: 'csrf-before-login' }))
      if (url.endsWith('/me')) return Promise.resolve(jsonResponse({ error: { code: 'not_authenticated', message: 'Требуется вход.' } }, 401))
      if (url.endsWith('/auth/login')) return Promise.resolve(jsonResponse({
        id: 'participant-1',
        displayName: 'Участник',
        role: 'participant',
        csrfToken: 'csrf-after-login',
      }))
      return Promise.resolve(jsonResponse({ error: { code: 'integration_unavailable', message: 'Матч пока недоступен.' } }, 503))
    })
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Войти в аккаунт' })).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Электронная почта'), 'participant@example.test')
    await userEvent.type(screen.getByLabelText('Пароль'), 'secret-example')
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }))

    await waitFor(() => {
      expect(window.location.pathname).toBe('/matches/match-42')
      expect(window.location.search).toBe('?problem=problem-7')
      expect(window.location.hash).toBe('#editor')
    })
  })

  it('shows admin navigation only for the server-provided admin role', async () => {
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/csrf')) return Promise.resolve(jsonResponse({ csrfToken: 'csrf-test' }))
      if (url.endsWith('/me')) return Promise.resolve(jsonResponse({ id: 'admin-1', displayName: 'Организатор', role: 'admin' }))
      return Promise.resolve(jsonResponse({}, 404))
    })
    render(<App />)

    expect(await screen.findByRole('link', { name: 'Организатору' })).toHaveAttribute('href', '/admin')
    expect(screen.getByText('Организатор')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Создать аккаунт' })).not.toBeInTheDocument()
  })
})
