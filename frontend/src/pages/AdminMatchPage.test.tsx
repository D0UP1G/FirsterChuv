import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { resetCsrfToken } from '../api/client'
import { buildDevBracket } from '../matches/devTransport'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

function useAdminSession() {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/auth/csrf')) return Promise.resolve(jsonResponse({ csrfToken: 'csrf-match-ui-test' }))
    if (url.endsWith('/me')) return Promise.resolve(jsonResponse({ id: 'admin-1', displayName: 'Организатор', role: 'admin' }))
    return Promise.resolve(jsonResponse({ error: { code: 'missing_endpoint', message: 'Endpoint не подключён.' } }, 404))
  }))
}

function renderScenario(participants = 4) {
  window.history.replaceState({}, '', `/admin/tournaments/dev-match/matches?scenario=match-ui&participants=${participants}`)
  return render(<App />)
}

describe('admin bracket and match controls', () => {
  beforeEach(() => {
    resetCsrfToken()
    window.history.replaceState({}, '', '/')
    useAdminSession()
  })

  afterEach(() => {
    cleanup()
    resetCsrfToken()
    vi.unstubAllGlobals()
  })

  it.each([2, 3, 4, 5])('builds a complete synthetic grid for %i participants', (count) => {
    const bracket = buildDevBracket(count)
    const firstRound = bracket.matches.filter((match) => match.roundIndex === 0)
    expect(bracket.bracketSize).toBe(count <= 2 ? 2 : count <= 4 ? 4 : 8)
    expect(firstRound).toHaveLength(bracket.bracketSize / 2)
    expect(firstRound.flatMap((match) => match.slots).filter((slot) => slot.participant)).toHaveLength(count)
    expect(firstRound.some((match) => match.status === 'BYE')).toBe(count === 3 || count === 5)
    expect(bracket.matches.some((match) => match.status === 'WAITING')).toBe(count > 2)
    expect(firstRound.flatMap((match) => match.slots).filter((slot) => slot.resolution === 'BYE')).toHaveLength(bracket.bracketSize - count)
  })

  it('keeps BYE separate from a later WAITING match', async () => {
    renderScenario(3)

    expect(await screen.findByRole('heading', { name: 'Сетка и матчи' })).toBeInTheDocument()
    expect(screen.getByText('BYE · свободный проход')).toBeInTheDocument()
    expect(screen.getByText('Ожидает победителя')).toBeInTheDocument()
    expect(screen.getByText(/синтетические данные и эмуляция команд/)).toBeInTheDocument()
  })

  it('requires a complete unique pairing set and saves the full round with a reason', async () => {
    const user = userEvent.setup()
    renderScenario()

    await screen.findByRole('heading', { name: 'Сетка и матчи' })
    const firstLeft = screen.getByLabelText('Пара 1, левая сторона')
    await user.selectOptions(firstLeft, '00000000-0000-4000-8000-000000000002')
    expect(screen.getByRole('button', { name: 'Сохранить полный раунд' })).toBeDisabled()

    await user.selectOptions(firstLeft, '00000000-0000-4000-8000-000000000003')
    await user.selectOptions(screen.getByLabelText('Пара 2, левая сторона'), '00000000-0000-4000-8000-000000000001')
    await user.type(screen.getByLabelText('Причина ручной перестановки'), 'Уточнение жеребьёвки')
    await user.click(screen.getByRole('button', { name: 'Сохранить полный раунд' }))

    expect(await screen.findByText('Изменения сохранены.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Настройки матча · Лена — Дима' })).toBeInTheDocument()
  })

  it('starts a both-ready match only after readiness from both participants', async () => {
    const user = userEvent.setup()
    renderScenario()

    expect(await screen.findByText('Автозапуск ждёт готовность обоих участников: 0/2.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Готов: Ира' }))
    expect(await screen.findByText('Автозапуск ждёт готовность обоих участников: 1/2.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Запустить матч' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Готов: Дима' }))
    await waitFor(() => expect(screen.getAllByText('Идёт').length).toBeGreaterThan(0))
  })

  it('lets the organizer start manually after selecting the manual mode', async () => {
    const user = userEvent.setup()
    renderScenario()

    await screen.findByRole('heading', { name: 'Сетка и матчи' })
    await user.selectOptions(screen.getByLabelText('Запуск'), 'manual')
    await user.click(screen.getByRole('button', { name: 'Сохранить настройки' }))
    await user.click(await screen.findByRole('button', { name: 'Запустить матч' }))
    await waitFor(() => expect(screen.getAllByText('Идёт').length).toBeGreaterThan(0))
    await user.type(screen.getByLabelText('Причина аудируемого действия'), 'Остановка по просьбе судьи')
    await user.click(screen.getByRole('button', { name: 'Пауза' }))
    expect(await screen.findByRole('button', { name: 'Продолжить' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Продлить время' }))
    expect(await screen.findByText(/осталось 21:00/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Продолжить' }))
    await waitFor(() => expect(screen.getAllByText('Идёт').length).toBeGreaterThan(0))
  })

  it('searches a free participant before a pre-start replacement and records a reason', async () => {
    const user = userEvent.setup()
    renderScenario()

    await screen.findByRole('heading', { name: 'Сетка и матчи' })
    await user.type(screen.getByLabelText('Найти свободного участника'), 'Новый')
    await user.click(screen.getByRole('button', { name: 'Найти' }))
    await user.selectOptions(screen.getByLabelText('Новый участник'), '00000000-0000-4000-8000-000000000006')
    await user.type(screen.getByLabelText('Причина аудируемого действия'), 'Участник сообщил о болезни')
    await user.click(screen.getByRole('button', { name: 'Заменить до старта' }))

    expect(await screen.findByText('Изменения сохранены.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Настройки матча · Новый участник — Дима' })).toBeInTheDocument()
    expect(screen.getByText('Новый участник', { selector: '.bracket-slot span' })).toBeInTheDocument()
  })

  it('offers bracket generation when the server has no bracket yet and answers with a generic 404', async () => {
    const tournament = {
      id: 'tournament-1', title: 'Осенний отбор', description: '', status: 'draft', format: 'single_elimination',
      startsAt: '2026-10-11T10:00:00Z', endsAt: '2026-10-11T13:00:00Z', participantLimit: 4, visibility: 'public',
      matchDurationSec: 1800, startMode: 'manual', rosterFrozenAt: null,
      scoringRule: { wrongAttemptPenaltySec: 300 },
    }
    const roster = ['u-1', 'u-2'].map((userId, index) => ({
      id: `entry-${index}`, userId, displayName: `Игрок ${index + 1}`, status: 'ACTIVE', seed: null,
    }))
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/auth/csrf')) return Promise.resolve(jsonResponse({ csrfToken: 'csrf-match-ui-test' }))
      if (url.endsWith('/me')) return Promise.resolve(jsonResponse({ id: 'admin-1', displayName: 'Организатор', role: 'admin' }))
      if (url.endsWith('/tournaments/tournament-1')) return Promise.resolve(jsonResponse(tournament))
      if (url.includes('/tournaments/tournament-1/participants')) return Promise.resolve(jsonResponse({ results: roster, count: 2 }))
      if (url.includes('/problems')) return Promise.resolve(jsonResponse({ results: [] }))
      return Promise.resolve(jsonResponse({ error: { code: 'not_found', message: 'Not found.', fields: null } }, 404))
    }))
    window.history.replaceState({}, '', '/admin/tournaments/tournament-1/matches')
    render(<App />)

    expect(await screen.findByRole('heading', { name: 'Сетка не создана' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Сформировать сетку' })).toBeEnabled()
    expect(screen.queryByText(/endpoint недоступен/)).not.toBeInTheDocument()
  })

  describe('against the real HTTP contract', () => {
    const tournament = {
      id: 'tournament-1', title: 'Осенний отбор', description: '', status: 'draft', format: 'single_elimination',
      startsAt: '2026-10-11T10:00:00Z', endsAt: '2026-10-11T13:00:00Z', participantLimit: 4, visibility: 'public',
      matchDurationSec: 1800, startMode: 'manual', rosterFrozenAt: null,
      scoringRule: { wrongAttemptPenaltySec: 300 },
    }
    const players = [
      { id: 'part-1', userId: 'u-1', displayName: 'Игрок 1', seed: null },
      { id: 'part-2', userId: 'u-2', displayName: 'Игрок 2', seed: null },
    ]
    const roster = players.map((player) => ({ userId: player.userId, displayName: player.displayName, seed: null, status: 'ACTIVE', addedAt: '2026-10-10T00:00:00Z', removedAt: null }))
    const bracket = {
      tournamentId: 'tournament-1', bracketSize: 2, rosterFrozenAt: '2026-10-10T00:00:00Z',
      matches: [{
        id: 'match-1', key: 'r1-p1', roundIndex: 0, position: 0, kind: 'MATCH', status: 'WAITING', winner: null, nextMatchId: null, nextSlot: null,
        slots: players.map((participant, index) => ({ index, resolution: 'PLAYER', participant, sourceMatchId: null })),
      }],
    }
    const matchView = {
      matchId: 'match-1', runId: 'run-1', status: 'READY', serverNow: '2026-10-10T01:00:00Z', elapsedMs: 0, remainingMs: 1_200_000,
      allowedDurationMs: 1_200_000, leaderUserId: null, winnerUserId: null, lastEventId: 0, scoringRule: tournament.scoringRule,
      players: players.map((player) => ({ userId: player.userId, displayName: player.displayName, solvedCount: 0, penaltyMs: 0, tasks: [] })),
      tournamentId: 'tournament-1', startMode: 'manual', readyUserIds: [],
      problemVersions: [{ problemId: 'problem-1', label: 'A', version: 'v1', conditionAvailable: false }],
    }

    function stubBackend(catalog: unknown[], configured = false) {
      const calls: Array<{ url: string; init?: RequestInit }> = []
      let isConfigured = configured
      vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        calls.push({ url, init })
        if (url.endsWith('/auth/csrf')) return Promise.resolve(jsonResponse({ csrfToken: 'csrf-match-ui-test' }))
        if (url.endsWith('/me')) return Promise.resolve(jsonResponse({ id: 'admin-1', displayName: 'Организатор', role: 'admin' }))
        if (url.endsWith('/tournaments/tournament-1')) return Promise.resolve(jsonResponse(tournament))
        if (url.includes('/tournaments/tournament-1/participants')) return Promise.resolve(jsonResponse({ results: roster, count: 2 }))
        if (url.includes('/problems')) return Promise.resolve(jsonResponse({ results: catalog, count: catalog.length }))
        if (url.endsWith('/tournaments/tournament-1/bracket')) return Promise.resolve(jsonResponse(bracket))
        if (url.endsWith('/matches/match-1') && init?.method === 'PATCH') {
          isConfigured = true
          return Promise.resolve(jsonResponse(matchView))
        }
        if (url.endsWith('/matches/match-1')) {
          return Promise.resolve(isConfigured
            ? jsonResponse(matchView)
            : jsonResponse({ error: { code: 'match_run_not_configured', message: 'У матча ещё нет настроенного запуска.', fields: null } }, 409))
        }
        return Promise.resolve(jsonResponse({ error: { code: 'not_found', message: 'Not found.', fields: null } }, 404))
      }))
      return calls
    }

    it('lets the organizer configure a match that has two players but no saved run yet', async () => {
      stubBackend([])
      window.history.replaceState({}, '', '/admin/tournaments/tournament-1/matches')
      render(<App />)

      expect(await screen.findByRole('heading', { name: 'Настройки матча · Игрок 1 — Игрок 2' })).toBeInTheDocument()
      expect(screen.queryByText('Нет матча первого раунда, доступного для управления.')).not.toBeInTheDocument()
      expect(screen.getByText('Каталог не вернул готовые версии задач.')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Сохранить настройки' })).toBeDisabled()
    })

    it('saves the match config with an idempotency key and then shows the manual start', async () => {
      const user = userEvent.setup()
      const calls = stubBackend([{ problemId: 'problem-1', label: 'A', version: 'v1', readiness: 'READY' }])
      window.history.replaceState({}, '', '/admin/tournaments/tournament-1/matches')
      render(<App />)

      await user.click(await screen.findByRole('checkbox', { name: /A/ }))
      await user.click(screen.getByRole('button', { name: 'Сохранить настройки' }))

      expect(await screen.findByRole('button', { name: 'Запустить матч' })).toBeInTheDocument()
      const patch = calls.find((call) => call.init?.method === 'PATCH')
      expect(patch?.url).toBe('/api/v1/matches/match-1')
      expect(JSON.parse(String(patch?.init?.body))).toEqual({ problemIds: ['problem-1'], matchDurationSec: 1800, startMode: 'manual' })
      const headers = new Headers(patch?.init?.headers)
      expect(headers.get('Idempotency-Key')).toMatch(/\S{8,}/)
      expect(headers.get('X-CSRFToken')).toBe('csrf-match-ui-test')
    })
  })

  it('shows the missing production endpoint instead of switching to fixture data', async () => {
    window.history.replaceState({}, '', '/admin/tournaments/tournament-1/matches')
    render(<App />)

    expect(await screen.findByText('Endpoint не подключён.')).toBeInTheDocument()
    expect(screen.getByText(/endpoint недоступен на подключённом сервере/)).toBeInTheDocument()
    expect(screen.queryByText(/синтетические данные и эмуляция команд/)).not.toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/v1/tournaments/tournament-1', expect.anything())
  })
})
