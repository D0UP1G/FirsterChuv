import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router'
import { SpectatorMapPage } from './SpectatorMapPage'
import { createDevSpectatorTransport } from './devTransport'

const tournamentId = '00000000-0000-4000-8000-000000000010'
const matchId = '00000000-0000-4000-8000-000000000020'

function renderMap(search = '?scenario=public-map', transport = createDevSpectatorTransport()) {
  return render(
    <MemoryRouter initialEntries={[`/watch/${tournamentId}/matches/${matchId}${search}`]}>
      <Routes>
        <Route path="/watch/:tournamentId/matches/:matchId" element={<SpectatorMapPage transport={transport} />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('anonymous spectator map', () => {
  afterEach(cleanup)

  it('shows the public bracket, two lanes, and a C solve independently of A and B', async () => {
    renderMap()

    expect(await screen.findByRole('heading', { name: 'Демонстрационный блиц · данные разработки' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Сетка турнира' })).toBeInTheDocument()
    expect(screen.getByRole('article', { name: /Ира: 1 задач/ })).toBeInTheDocument()
    const iraTasks = screen.getByRole('list', { name: 'Задачи: Ира' })
    expect(within(iraTasks).getByText('C').closest('li')).toHaveClass('task-solved')
    expect(within(iraTasks).getByText('A').closest('li')).toHaveClass('task-attempted')
    expect(within(iraTasks).getByText('B').closest('li')).toHaveClass('task-not_started')
    expect(screen.getByText('Попытки: 2')).toBeInTheDocument()
    expect(screen.getByText('Последний вердикт: WA')).toBeInTheDocument()
    expect(screen.queryByText(/source|email|CE diagnostics/i)).not.toBeInTheDocument()
  })

  it('reloads the public snapshot and bracket after a resync notice', async () => {
    const transport = createDevSpectatorTransport({ resyncOnce: true })
    const bracketSpy = vi.spyOn(transport, 'bracket')
    renderMap('?scenario=public-map&resync=1', transport)

    expect(await screen.findByText('ЛИДЕР')).toBeInTheDocument()
    await waitFor(() => expect(bracketSpy).toHaveBeenCalledTimes(2))
    expect(screen.getByText(/Эфир обновляется|Подключаем трансляцию/)).toBeInTheDocument()
  })

  it('preserves the dev scenario while switching to projector mode', async () => {
    const user = userEvent.setup()
    renderMap()
    const projector = await screen.findByRole('link', { name: 'Режим проектора' })
    expect(projector.getAttribute('href')).toContain('scenario=public-map')
    await user.click(projector)
    expect(await screen.findByRole('link', { name: 'Обычный вид' })).toBeInTheDocument()
    expect(document.querySelector('.spectator-page-projector')).toBeInTheDocument()
  })

  it('renders untrusted public names and titles as text, not executable HTML', async () => {
    const base = createDevSpectatorTransport()
    const payload = '<img src=x onerror=alert(1)>'
    const transport = {
      ...base,
      async bracket(id: string) {
        return { ...await base.bracket(id), title: payload }
      },
      async snapshot(id: string) {
        const snapshot = await base.snapshot(id)
        return {
          ...snapshot,
          players: snapshot.players.map((player) => ({ ...player, displayName: payload })) as typeof snapshot.players,
        }
      },
    }

    renderMap('?scenario=public-map', transport)

    expect(await screen.findByRole('heading', { name: payload })).toBeInTheDocument()
    expect(document.querySelector('img')).toBeNull()
    expect(document.body.textContent).toContain(payload)
  })
})
