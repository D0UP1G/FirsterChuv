import { describe, expect, it, vi } from 'vitest'
import { resolveSpectatorTransport } from './transport'
import { ApiError } from '../api/client'

describe('spectator transport selection', () => {
  it('fails closed without a connected public endpoint or the explicit dev scenario', async () => {
    const transport = await resolveSpectatorTransport('')
    expect(transport.mode).toBe('http')
    await expect(transport.bracket('00000000-0000-4000-8000-000000000010')).rejects.toBeInstanceOf(ApiError)
    const onError = vi.fn()
    transport.subscribe('match', 0, { onOpen: vi.fn(), onEvent: vi.fn(), onResync: vi.fn(), onError })
    expect(onError).toHaveBeenCalledOnce()
  })

  it('uses only the explicit development scenario in development builds', async () => {
    const transport = await resolveSpectatorTransport('?scenario=public-map')
    expect(transport.mode).toBe('development-scenario')
    await expect(transport.bracket('00000000-0000-4000-8000-000000000010')).resolves.toMatchObject({ title: 'Демонстрационный блиц · данные разработки' })
  })
})
