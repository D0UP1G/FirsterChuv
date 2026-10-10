import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { resetCsrfToken } from '../api/client'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

function emptyResponse(status: number): Response {
  return { ok: status >= 200 && status < 300, status, headers: new Headers() } as Response
}

const tournament = {
  id: 'tournament-1',
  slug: 'test-tournament',
  title: 'Блиц по строкам',
  description: 'Синтетический тестовый турнир',
  startsAt: '2026-11-01T10:00:00Z',
  endsAt: '2026-11-01T12:00:00Z',
  format: 'single_elimination',
  participantLimit: 4,
  visibility: 'public',
  status: 'draft',
  activeParticipantCount: 0,
  rosterFrozenAt: null,
  matchDurationSec: 1800,
  startMode: 'manual',
  scoringRule: {
    order: ['solved_desc', 'penalty_asc', 'last_accepted_asc'],
    wrongAttemptPenaltySec: 300,
    penalizedVerdicts: ['WA', 'TL', 'ML', 'RE'],
    finalTiePolicy: 'rematch',
  },
}

describe('admin and invite browser screens', () => {
  beforeEach(() => {
    let inviteCreated = false
    let createdInvite: { expiresAt: string | null; maxUses: number | null } | null = null
    resetCsrfToken()
    window.history.replaceState({}, '', '/')
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'
      if (url.endsWith('/auth/csrf')) return jsonResponse({ csrfToken: 'csrf-ui-test' })
      if (url.endsWith('/me')) return jsonResponse({ id: 'admin-1', displayName: 'Организатор', role: 'admin' })
      if (url.includes('/tournaments?limit=')) return jsonResponse({ count: 0, next: null, previous: null, results: [] })
      if (url.endsWith('/tournaments') && method === 'POST') return jsonResponse(tournament, 201)
      if (url.endsWith('/tournaments/tournament-1')) return jsonResponse(tournament)
      if (url.endsWith('/tournaments/tournament-1/participants?limit=100&offset=0')) return jsonResponse({ count: 0, next: null, previous: null, results: [] })
      if (url.endsWith('/tournaments/tournament-1/invites?limit=100&offset=0')) return jsonResponse({
        count: inviteCreated ? 1 : 0,
        next: null,
        previous: null,
        results: inviteCreated ? [{ id: 'invite-1', tournamentId: 'tournament-1', ...createdInvite, uses: 0, revokedAt: null }] : [],
      })
      if (url.endsWith('/tournaments/tournament-1/invites') && method === 'POST') {
        inviteCreated = true
        createdInvite = JSON.parse(String(init?.body)) as { expiresAt: string | null; maxUses: number | null }
        return jsonResponse({
          invite: { id: 'invite-1', tournamentId: 'tournament-1', ...createdInvite, uses: 0, revokedAt: null },
          token: 'synthetic-invite-token',
          url: '/invites/synthetic-invite-token',
        }, 201)
      }
      if (url.endsWith('/tournaments/tournament-1/invites/invite-1') && method === 'DELETE') {
        inviteCreated = false
        return emptyResponse(204)
      }
      return jsonResponse({ error: { code: 'not_found', message: 'Не найдено.' } }, 404)
    }))
  })

  afterEach(() => {
    cleanup()
    resetCsrfToken()
    vi.unstubAllGlobals()
  })

  it('creates a tournament and an invite through the admin UI', async () => {
    const user = userEvent.setup()
    window.history.replaceState({}, '', '/admin')
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'Турниры' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Создать турнир' }))
    await user.type(screen.getByLabelText('Название'), 'Блиц по строкам')
    await user.click(screen.getByRole('button', { name: 'Создать турнир' }))

    expect(await screen.findByRole('heading', { name: 'Состав участников' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/admin/tournaments/tournament-1')
    const expiry = '2026-11-01T12:00'
    fireEvent.change(screen.getByLabelText('Действует до'), { target: { value: expiry } })
    const maxUses = screen.getByLabelText('Лимит активаций')
    await user.type(maxUses, '2')
    await user.click(screen.getByRole('button', { name: 'Создать приглашение' }))

    const linkField = await screen.findByRole('textbox', { name: 'Ссылка-приглашение' })
    expect(linkField).toHaveValue('http://localhost:3000/invites/synthetic-invite-token')
    const clipboardWrite = vi.fn().mockResolvedValue(undefined)
    const clipboardDescriptor = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: clipboardWrite } })
    await user.click(screen.getByRole('button', { name: 'Скопировать' }))
    expect(await screen.findByRole('button', { name: 'Скопировано' })).toBeInTheDocument()
    expect(clipboardWrite).toHaveBeenCalledWith('http://localhost:3000/invites/synthetic-invite-token')
    if (clipboardDescriptor) Object.defineProperty(navigator, 'clipboard', clipboardDescriptor)
    else Reflect.deleteProperty(navigator, 'clipboard')

    await user.click(screen.getByRole('button', { name: 'Отозвать' }))
    expect(screen.getByRole('alertdialog', { name: 'Подтверждение отзыва приглашения' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Подтвердить отзыв' }))
    expect(await screen.findByText('Приглашение отозвано.')).toBeInTheDocument()

    const calls = vi.mocked(fetch).mock.calls
    const createRequest = calls.find(([input, init]) => String(input).endsWith('/tournaments') && init?.method === 'POST')
    const inviteRequest = calls.find(([input, init]) => String(input).endsWith('/tournaments/tournament-1/invites') && init?.method === 'POST')
    expect(createRequest).toBeDefined()
    expect(inviteRequest).toBeDefined()
    expect(new Headers(inviteRequest?.[1]?.headers).get('X-CSRFToken')).toBe('csrf-ui-test')
    expect(JSON.parse(String(inviteRequest?.[1]?.body))).toEqual({ expiresAt: new Date(expiry).toISOString(), maxUses: 2 })
  })

  it('keeps invite preview public and preserves the invite path through registration', async () => {
    const user = userEvent.setup()
    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/auth/csrf')) return jsonResponse({ csrfToken: 'csrf-ui-test' })
      if (url.endsWith('/me')) return jsonResponse({ error: { code: 'not_authenticated', message: 'Требуется вход.' } }, 401)
      if (url.endsWith('/invites/synthetic-invite-token')) return jsonResponse({ tournament: { id: 'tournament-1', title: 'Блиц по строкам' }, valid: true, expiresAt: null })
      if (url.endsWith('/auth/register') && init?.method === 'POST') return jsonResponse({ id: 'player-1', displayName: 'Новый игрок', role: 'participant' }, 201)
      return jsonResponse({ error: { code: 'not_found', message: 'Не найдено.' } }, 404)
    })
    window.history.replaceState({}, '', '/invites/synthetic-invite-token')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Блиц по строкам' })).toBeInTheDocument()
    await user.click(screen.getAllByRole('link', { name: 'Создать аккаунт' })[1])
    expect(await screen.findByRole('heading', { name: 'Создать аккаунт' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Имя в турнире'), 'Новый игрок')
    await user.type(screen.getByLabelText('Электронная почта'), 'player@example.test')
    await user.type(screen.getByLabelText('Пароль'), 'synthetic-password-410')
    await user.click(screen.getByRole('button', { name: 'Зарегистрироваться' }))
    await user.click(await screen.findByRole('button', { name: 'Перейти ко входу' }))

    expect(await screen.findByRole('heading', { name: 'Войти в аккаунт' })).toBeInTheDocument()
    await waitFor(() => expect(window.location.pathname).toBe('/login'))
    expect(window.location.search).toContain(encodeURIComponent('/invites/synthetic-invite-token'))
  })
})
