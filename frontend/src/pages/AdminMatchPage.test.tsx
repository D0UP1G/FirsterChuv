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

  it('shows the missing production endpoint instead of switching to fixture data', async () => {
    window.history.replaceState({}, '', '/admin/tournaments/tournament-1/matches')
    render(<App />)

    expect(await screen.findByText('Endpoint не подключён.')).toBeInTheDocument()
    expect(screen.getByText(/endpoint недоступен на подключённом сервере/)).toBeInTheDocument()
    expect(screen.queryByText(/синтетические данные и эмуляция команд/)).not.toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/v1/tournaments/tournament-1', expect.anything())
  })
})
