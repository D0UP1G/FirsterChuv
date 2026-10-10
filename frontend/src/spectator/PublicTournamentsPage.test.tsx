import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PublicTournamentsPage } from './PublicTournamentsPage'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

function renderPage() {
  return render(<MemoryRouter><PublicTournamentsPage /></MemoryRouter>)
}

describe('PublicTournamentsPage', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('lists public tournaments from the real endpoint with links to their maps', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      count: 1, next: null, previous: null,
      results: [{ id: '00000000-0000-4000-8000-000000000010', title: 'Осенний отбор', status: 'running', startsAt: '2026-10-10T10:00:00Z', endsAt: '2026-10-10T13:00:00Z' }],
    }))
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    const link = await screen.findByRole('link', { name: /Осенний отбор/ })
    expect(link).toHaveAttribute('href', '/watch/00000000-0000-4000-8000-000000000010')
    expect(screen.getByText('Идёт')).toBeInTheDocument()
    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/public/tournaments?limit=50&offset=0')
  })

  it('shows an empty state when no tournament is public yet', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ count: 0, next: null, previous: null, results: [] })))

    renderPage()

    expect(await screen.findByRole('heading', { name: 'Открытых турниров пока нет' })).toBeInTheDocument()
  })

  it('shows the error and retries without a login redirect', async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ error: { code: 'public_snapshot_unavailable', message: 'Недоступно.', fields: null } }, 503))
      .mockResolvedValueOnce(jsonResponse({ count: 0, next: null, previous: null, results: [] }))
    vi.stubGlobal('fetch', fetchMock)

    renderPage()

    expect(await screen.findByRole('alert')).toHaveTextContent('Недоступно.')
    await user.click(screen.getByRole('button', { name: 'Повторить' }))
    expect(await screen.findByRole('heading', { name: 'Открытых турниров пока нет' })).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
