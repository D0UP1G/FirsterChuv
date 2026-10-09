import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api } from '../api/client'
import { resolveWorkspaceTransport } from './transport'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('workspace HTTP draft transport', () => {
  it('treats a missing saved draft as empty while preserving API unavailability', async () => {
    const draft = vi.spyOn(api, 'draft')
      .mockRejectedValueOnce(new ApiError('Черновик не найден.', 404, 'not_found'))
      .mockRejectedValueOnce(new ApiError('Provider недоступен.', 503, 'integration_unavailable'))
    const transport = await resolveWorkspaceTransport(new URLSearchParams())

    await expect(transport.draft('match-1', 'problem-1', 'run-1', 'cpp20')).resolves.toBeNull()
    await expect(transport.draft('match-1', 'problem-1', 'run-1', 'cpp20'))
      .rejects.toMatchObject({ status: 503, code: 'integration_unavailable' })
    expect(draft).toHaveBeenCalledWith('match-1', 'problem-1', 'run-1', 'cpp20')
    expect(draft).toHaveBeenCalledTimes(2)
  })
})
