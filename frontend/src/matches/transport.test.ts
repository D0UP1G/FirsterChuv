import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resolveMatchAdminTransport } from './transport'

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

describe('admin match transport catalog connection', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses the HTTP catalog for the default admin route', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockResolvedValueOnce(jsonResponse({
      count: 1,
      next: null,
      previous: null,
      results: [{ problemId: 'problem-1', label: 'A', version: 'v1', readiness: 'READY' }],
    }))

    const transport = await resolveMatchAdminTransport('')

    expect(transport.mode).toBe('http')
    await expect(transport.problems()).resolves.toEqual([
      { problemId: 'problem-1', label: 'A', version: 'v1', readiness: 'READY' },
    ])
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/problems?limit=100&offset=0', expect.objectContaining({
      credentials: 'include',
      cache: 'no-store',
    }))
  })

  it('preserves catalog API failures in HTTP mode without switching to fixtures', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockResolvedValueOnce(jsonResponse({
      error: { code: 'service_unavailable', message: 'Каталог временно недоступен.', fields: null },
      requestId: 'req-catalog-503',
    }, 503))

    const transport = await resolveMatchAdminTransport('')

    expect(transport.mode).toBe('http')
    await expect(transport.problems()).rejects.toMatchObject({
      status: 503,
      code: 'service_unavailable',
      requestId: 'req-catalog-503',
    })
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('uses the synthetic catalog only for an explicit development scenario', async () => {
    const transport = await resolveMatchAdminTransport('?scenario=match-ui&participants=2')

    expect(transport.mode).toBe('development-scenario')
    await expect(transport.problems()).resolves.toEqual(expect.arrayContaining([
      expect.objectContaining({ problemId: '00000000-0000-4000-8000-000000000040', readiness: 'READY' }),
    ]))
    expect(fetch).not.toHaveBeenCalled()
  })
})
